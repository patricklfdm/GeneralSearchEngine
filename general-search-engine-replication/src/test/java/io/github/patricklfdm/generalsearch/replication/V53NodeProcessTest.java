package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Each test is one uninterrupted three-node history, with two real leader JVMs.
 * Followers retain their original owners throughout the leader's process death. */
class V53NodeProcessTest {
    @TempDir Path temp;
    @Test void haltThenOriginalDiskFreshBarrier()throws Exception{run("halt");}
    @Test void sigkillThenOriginalDiskFreshBarrier()throws Exception{run("kill");}
    void run(String mode)throws Exception {run(mode,"AFTER_DATA_RETURN");}
    void run(String mode,String point)throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-node-process/run-"+UUID.randomUUID())),raw=Files.createDirectory(evidence.resolve("history")),processes=Files.createDirectory(evidence.resolve("process"));
        System.out.println("v53NodeProcessEvidence="+evidence.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group")),3,false));
        f.ownedHistory=true;f.nativeApplication=true;
        for(var target:f.request.targets())try(var journal=f.open(target,"initialize-retention")){journal.initializePeerRetention();journal.initializeFutureRetention();}
        f.snapshot("before-network");
        var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var followers=new ArrayList<MembershipNodeOwner<Integer,Doc>>();var records=new ArrayList<Map<String,Object>>();var children=new ArrayList<Process>();
        Path scratch=Files.createDirectory(temp.resolve("leader-scratch")),spec=processes.resolve("spec.json");
        Files.write(spec,canonical(Map.of("nodes",f.request.targets().stream().map(t->Map.of("replica",t.replicaDirectory().toString(),"application",t.materialization().directory().toString())).toList(),"scratch",scratch.toString()),65536));
        V53NodeProcessWorker.Sink sink=(action,value)->{
            try {
                switch(action) {
                    case "event" -> events.add(object(value));
                    case "response" -> {var row=object(value);synchronized(events){wire.add(object(row.get("wire")));events.add(object(row.get("event")));}}
                    case "snapshot" -> f.snapshot((String)value);
                    case "installed" -> {var row=object(value);int number=Math.toIntExact(number(row.get("number")));Files.write(raw.resolve("selected-"+number+".gsr"),Base64.getDecoder().decode((String)row.get("bytes")));f.snapshot("installed-"+number);}
                    default -> throw new IOException("unknown observation action: "+action);
                }
            }catch(Exception error){throw new IOException(error);}
        };
        boolean success=false;
        try(var readers=Executors.newCachedThreadPool()) {
            try {
                for(int life:List.of(1,2)) {
                    var opened=new CountDownLatch(1);var proceed=new CountDownLatch(1);var cut=new CountDownLatch(1);
                    Path stdout=processes.resolve("life-"+life+".jsonl"),stderr=processes.resolve("life-"+life+".stderr");
                    Process child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                            V53NodeProcessWorker.class.getName(),spec.toAbsolutePath().toString(),Integer.toString(life),mode,point).redirectError(stderr.toFile()).start();children.add(child);
                    var row=new TreeMap<String,Object>();row.put("life",life);row.put("pid",child.pid());records.add(row);
                    var reader=readers.submit(()->{
                        try(var input=child.inputReader(StandardCharsets.UTF_8);var output=child.outputWriter(StandardCharsets.UTF_8);var retained=Files.newBufferedWriter(stdout,StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW)) {
                            String line;while((line=input.readLine())!=null) {
                                retained.write(line);retained.newLine();retained.flush();var message=object(parse(line.getBytes(StandardCharsets.UTF_8),8*1024*1024));
                                String action=(String)message.get("action");Object value=message.get("value");
                                switch(action) {
                                    case "started" -> {assertEquals(child.pid(),number(object(value).get("pid")));row.put("started",value);}
                                    case "opened" -> {assertEquals(life,number(value));opened.countDown();assertTrue(proceed.await(30,TimeUnit.SECONDS));}
                                    case "cut" -> {
                                        assertEquals(1,life);assertEquals(Map.of("name",point,"mode",mode,"pid",child.pid()),value);
                                        var locked=assertThrows(ReplicationException.class,()->{try(var ignored=MembershipOwnership.own(f.request.targets().getFirst().replicaDirectory().resolve("replica.lock"),false)){fail("live leader lock released");}});
                                        assertEquals("membership file already owned",locked.getMessage());
                                        row.put("lockHeldBeforeDeath",true);
                                    }
                                    case "closed" -> {assertEquals(2,life);assertEquals(2,number(value));row.put("drained",true);}
                                    default -> sink.accept(action,value);
                                }
                                output.write("ACK\n");output.flush();if(action.equals("cut"))cut.countDown();
                            }
                        }
                        return null;
                    });
                    assertTrue(opened.await(30,TimeUnit.SECONDS),"child open: "+stderr);
                    if(life==1)for(int index:List.of(1,2)) {
                        var target=f.request.targets().get(index);var bounds=ReplicationBounds.defaults();Path area=Files.createDirectory(temp.resolve("follower-"+index));
                        var config=new MembershipReplicaConfig<>(f.result.root(),target.identity(),f.request.targets().stream().map(MembershipBootstrapTarget::identity).filter(i->!i.equals(target.identity())).toList(),
                                target.replicaDirectory(),target.materialization(),bounds,AutomaticLeadershipPolicy.forBounds(bounds));
                        var node=new MembershipNodeOwner<>(config,builder().configuration(),area.resolve("incoming"),area.resolve("outgoing"),System::nanoTime,V53NodeOwnerNetworkTest.BUDGET,V53NodeProcessWorker.hooks(target.identity().nodeId().value(),1,sink));
                        followers.add(node);node.open();events.add(Map.of("node",target.identity().nodeId().value(),"incarnation",1,"event","NODE_OPEN"));
                    }
                    proceed.countDown();
                    if(life==1) {
                        assertTrue(cut.await(210,TimeUnit.SECONDS),"child cut: "+stderr);
                        if(mode.equals("kill"))child.destroyForcibly();
                    }
                    assertTrue(child.waitFor(210,TimeUnit.SECONDS),"child finish: "+stderr);reader.get(10,TimeUnit.SECONDS);
                    int expected=life==2?0:mode.equals("halt")?73:137;row.put("exit",child.exitValue());assertEquals(expected,child.exitValue(),Files.readString(stderr));
                    if(life==1) {
                        events.add(Map.of("node","node-1","incarnation",1,"event","NODE_CRASH"));f.snapshot("before-reopen");
                        try(var ignored=MembershipOwnership.own(f.request.targets().getFirst().replicaDirectory().resolve("replica.lock"),false)){row.put("lockReleasedAfterDeath",true);}
                    }
                }
                success=true;
            }finally {
                for(var child:children)if(child.isAlive()){child.destroyForcibly();assertTrue(child.waitFor(10,TimeUnit.SECONDS));}
                IOException closing=null;for(var node:followers.reversed())try{node.close();assertEquals(0,node.usage().leases());}catch(IOException error){if(closing==null)closing=error;else closing.addSuppressed(error);}
                Files.write(raw.resolve("events.json"),V53EvidenceArray.encode(events,16*1024*1024));Files.write(raw.resolve("wire.json"),V53EvidenceArray.encode(wire,32*1024*1024));f.snapshot("after-close");V53NativeApplicationTest.save(f);
                long barriers=events.stream().filter(v->v.get("event").equals("ROUND_SLOT_BEGIN"))
                        .map(v->decode(Base64.getDecoder().decode((String)v.get("bytes")),"records","ENTRY"))
                        .filter(v->v.value().get("kind").equals("BARRIER")).count();
                Files.write(raw.resolve("node-result.json"),canonical(Map.of("status","PARTIAL","producerPassed",success && closing==null,"coldReopens",1,"barriers",barriers,"dataCalls",2,
                        "physicalReplay",false,"processRestart",true,"phase3Complete",false,"serviceBudgetNanos",V53NodeOwnerNetworkTest.BUDGET),4096));
                Files.write(processes.resolve("result.json"),canonical(Map.of("mode",mode,"cut",point,"children",records,"status",success && closing==null?"PARTIAL":"FAIL","powerLoss",false,"phase3Complete",false),65536));
                if(closing!=null)throw closing;
            }
        }
    }
}
