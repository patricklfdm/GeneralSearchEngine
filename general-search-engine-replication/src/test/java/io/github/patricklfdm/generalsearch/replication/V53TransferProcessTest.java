package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Each case preserves one original filesystem across donor halt/SIGKILL/reopen. */
class V53TransferProcessTest {
    @TempDir Path temp;
    static final List<String> POINTS=List.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT");
    static final class Trace {
        final List<Map<String,Object>> rows=new ArrayList<>();
        synchronized void add(String event,int life,Object value){rows.add(Map.of("event",event,"life",life,"value",value));}
    }
    @Test void originalSourceSurvivesEveryTransferReplyProcessCut()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-transfer-process/run-"+UUID.randomUUID()));
        System.out.println("v53TransferProcessEvidence="+root.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        String only=System.getProperty("v53.transfer.process.case","");
        for(int size:List.of(3,4,5))for(String point:POINTS)for(String mode:List.of("halt","kill")) {
            String name=size+"-"+point+"-"+mode;if(!only.isEmpty() && !only.equals(name))continue;
            run(Files.createDirectory(root.resolve(name)),size,point,mode);cases.add(Map.of("size",size,"point",point,"mode",mode));
            System.out.println("v53TransferProcessCase="+name+" PASS");
        }
        assertFalse(cases.isEmpty(),"unknown transfer process case");
        Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-transfer-process-v1","status","PASS",
                "cases",cases,"completeMatrix",only.isEmpty(),"phase3Complete",false),65536));
    }
    void run(Path root,int size,String point,String mode)throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;Path raw=Files.createDirectory(root.resolve("history"));
        var trace=new Trace();var children=new ArrayList<Process>();var records=new ArrayList<Map<String,Object>>();boolean success=false;
        try(var group=helper.new Group(size,raw);var readers=Executors.newCachedThreadPool()) {
            var f=group.fixture;f.ownedHistory=true;var target=f.request.targets().getFirst();MembershipCapsule capsule;Decoded promise,basis;
            try(var owner=f.open(target,"transfer-fault-source")) {
                var grant=owner.beginActivation();capsule=grant.capsule;basis=grant.basis;promise=owner.promised().orElseThrow();
                Path exported=Files.createDirectory(raw.resolve("exported"));var contents=new ArrayList<Map<String,Object>>();
                try(var source=owner.exportSource(basis,BUDGET)) {
                    for(var content:source.contents()) {
                        Files.write(exported.resolve(content.digest()+".bin"),V53SourceExportTest.complete(source,content));
                        contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                    }
                }
                contents.sort(Comparator.comparing(row->(String)row.get("digest")));Files.write(raw.resolve("contents.json"),canonical(contents,65536));
            }
            f.snapshot("captured");Files.write(raw.resolve("calls.json"),canonical(f.calls,1024*1024));
            Path spec=root.resolve("spec.json");Files.write(spec,canonical(Map.of("replica",target.replicaDirectory().toString(),
                    "application",target.materialization().directory().toString(),"mode",mode,"point",point),65536));
            var receiving=resources();var lifeNow=new AtomicInteger();var bounds=V53TransferServiceTest.bound(2);
            var client=group.start(1,group::status,(event,q,a)->{
                var row=new TreeMap<String,Object>();row.put("event",event);row.put("request",V53TransferFaultsTest.encoded(q));
                if(a!=null)row.put("response",V53TransferFaultsTest.encoded(a));trace.add("CLIENT_WIRE",lifeNow.get(),row);
            },bounds,receiving);
            for(int life:List.of(1,2)) {
                lifeNow.set(life);Path dir=Files.createDirectory(root.resolve("life-"+life));Path stop=dir.resolve("stop.request");
                var opened=new CountDownLatch(1);var cut=new CountDownLatch(1);
                Process child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                        V53TransferProcessWorker.class.getName(),spec.toAbsolutePath().toString(),Integer.toString(life),stop.toAbsolutePath().toString())
                        .redirectError(dir.resolve("stderr").toFile()).start();children.add(child);
                var record=new TreeMap<String,Object>();record.put("life",life);record.put("pid",child.pid());records.add(record);
                var reader=readers.submit(()->{
                    try(var input=child.inputReader(StandardCharsets.UTF_8);var output=child.outputWriter(StandardCharsets.UTF_8);
                            var retained=Files.newBufferedWriter(dir.resolve("stdout"),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW)) {
                        String line;while((line=input.readLine())!=null) {
                            retained.write(line);retained.newLine();retained.flush();var value=object(parse(line.getBytes(StandardCharsets.UTF_8),65536));
                            String action=(String)value.get("action");trace.add("SERVER_"+action,life,value.get("value"));
                            if(action.equals("started") || action.equals("STARTED"))assertEquals(child.pid(),number(object(value.get("value")).get("pid")));
                            if(action.equals("cut")) {
                                var locked=assertThrows(ReplicationException.class,()->{try(var ignored=MembershipOwnership.own(target.replicaDirectory().resolve("replica.lock"),false)){fail("donor lock lost");}});
                                assertEquals("membership file already owned",locked.getMessage());trace.add("LOCK_HELD",life,child.pid());
                            }
                            output.write("ACK\n");output.flush();if(action.equals("OPEN"))opened.countDown();if(action.equals("cut"))cut.countDown();
                        }
                    }return null;
                });
                try {
                    assertTrue(opened.await(30,TimeUnit.SECONDS),"donor open: "+dir);long started=System.nanoTime();
                    trace.add("PULL_OPEN",life,Map.of("started",started,"budget",BUDGET));
                    MembershipSourcePull.Link link=(peer,q,kind,deadline)->{
                        trace.add("CALL",life,Map.of("request",V53TransferFaultsTest.encoded(q),"expected",kind,"deadline",deadline));
                        return client.exchange(peer,q,kind,deadline).handle((reply,failure)->{
                            if(failure!=null){var error=V53TransferFaultsTest.cause(failure);trace.add("FAILURE",life,Map.of("request",V53TransferFaultsTest.encoded(q),"reason",error instanceof MembershipTransport.Failure v?v.reason.name():error.getClass().getSimpleName()));throw new CompletionException(error);}
                            trace.add("REPLY",life,Map.of("request",V53TransferFaultsTest.encoded(q),"response",V53TransferFaultsTest.encoded(reply)));return reply;
                        });
                    };
                    try(var pull=new MembershipSourcePull(capsule,group.identities.get(1),target.identity(),object(basis.value().get("ballot")),UUID.randomUUID(),
                            receiving,bounds,link,()->{},System::nanoTime,started,BUDGET)) {
                        var fetched=readers.submit(()->pull.fetchRecord(promise.digest(),"PROMISE",v->V53RecordExchangeTest.promise(v,capsule.context,object(basis.value().get("ballot")))));
                        if(life==1) {
                            assertTrue(cut.await(30,TimeUnit.SECONDS),"donor cut: "+dir);if(mode.equals("kill"))child.destroyForcibly();
                            assertTrue(child.waitFor(15,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?73:137,child.exitValue());
                            var failure=assertThrows(ExecutionException.class,()->fetched.get(15,TimeUnit.SECONDS));
                            assertEquals(MembershipTransport.Reason.IO,assertInstanceOf(MembershipTransport.Failure.class,failure.getCause()).reason);
                        }else {
                            var received=fetched.get(30,TimeUnit.SECONDS);assertArrayEquals(promise.bytes(),received.bytes());Files.write(root.resolve("record.gsr"),received.bytes());
                            Files.writeString(stop,"stop\n");assertTrue(child.waitFor(15,TimeUnit.SECONDS));assertEquals(0,child.exitValue());
                        }
                    }
                    reader.get(10,TimeUnit.SECONDS);assertEquals("",Files.readString(dir.resolve("stderr")));
                    record.put("exit",child.exitValue());trace.add("EXIT",life,Map.of("pid",child.pid(),"exit",child.exitValue()));
                    try(var lock=MembershipOwnership.own(target.replicaDirectory().resolve("replica.lock"),false)){trace.add("LOCK_RELEASED",life,child.pid());}
                    V53MembershipTransportTest.waitFor(()->client.usage().outgoing()==0 && client.usage().sockets()==0);
                    assertEquals(0,receiving.usage().leases());trace.add("CLIENT_RELEASED",life,V53TransferFaultsTest.usage(receiving));
                    f.snapshot(life==1?"interrupted":"after");
                }finally{V53TransitionProcessTest.stop(child);}
            }
            client.close();success=true;
        }finally {
            for(var child:children)V53TransitionProcessTest.stop(child);
            Files.write(root.resolve("events.json"),canonical(trace.rows,4*1024*1024));
            Files.write(root.resolve("process.json"),canonical(Map.of("size",size,"point",point,"mode",mode,"parentPid",ProcessHandle.current().pid(),
                    "children",records,"status",success?"PASS":"FAIL","phase3Complete",false),65536));
        }
    }
}
