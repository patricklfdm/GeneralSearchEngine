package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Real TCP faults against one original admitted source per stable size.
 * Clock advancement is explicit fault injection, not measured wall time. */
class V53TransferFaultsTest {
    @TempDir Path temp;
    static final List<String> CASES=List.of("lost-offer","lost-data","lost-commit","exhausted-offer",
            "expired-active","expired-completed","closed-active","changed-completed","owner-closed-completed");
    static final class Trace {
        final String name;
        final List<Map<String,Object>> events=new ArrayList<>();
        int drops;
        Trace(String name){this.name=name;}
        synchronized void add(String event,Object... fields) {
            var row=new TreeMap<String,Object>();row.put("event",event);
            for(int i=0;i<fields.length;i+=2)row.put((String)fields[i],fields[i+1]);events.add(row);
        }
        synchronized void wire(String side,String event,Decoded request,Decoded response)throws IOException {
            add(event,"side",side,"request",encoded(request));
            if(response!=null)events.getLast().put("response",encoded(response));
            String wanted=switch(name){case "lost-offer","exhausted-offer"->"SOURCE_OFFER";
                case "lost-data"->"CHUNK";case "lost-commit"->"TRANSFER_COMMIT";default->"";};
            if(side.equals("server") && event.equals("BEFORE_RESPONSE_WRITE") && response.kind().equals(wanted)
                    && (drops==0 || name.equals("exhausted-offer"))) {
                drops++;add("DROP","request",encoded(request),"response",encoded(response));
                throw new IOException("declared lost TCP response");
            }
        }
    }
    static String encoded(Decoded frame){return Base64.getEncoder().encodeToString(frame.bytes());}
    static void drain(MembershipTransport server,MembershipTransport client)throws Exception {
        V53MembershipTransportTest.waitFor(()->server.usage().incoming()==0 && server.usage().sockets()==0
                && client.usage().outgoing()==0 && client.usage().sockets()==0);
    }
    static Throwable cause(Throwable failure) {
        while(failure instanceof CompletionException || failure instanceof ExecutionException)failure=failure.getCause();return failure;
    }
    static Map<String,Object> usage(MembershipResources resources) {
        var u=resources.usage();var counts=new TreeMap<String,Object>();u.counts().forEach((key,value)->counts.put(key.name(),value));
        return Map.of("leases",u.leases(),"metadata",u.metadata(),"staging",u.staging(),"queued",u.queued(),"counts",counts);
    }
    @Test void publicBootstrapTcpFaultsAtAllStableSizes()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-transfer-faults/run-"+UUID.randomUUID()));
        System.out.println("v53TransferFaultEvidence="+evidence.toAbsolutePath());var profiles=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))profiles.add(profile(evidence,size));
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-transfer-faults-v1","status","PASS",
                "profiles",profiles,"network",true,"publicRuntime",false,"phase3Complete",false),65536));
    }
    Map<String,Object> profile(Path evidence,int size)throws Exception {
        Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
        var summaries=new ArrayList<Map<String,Object>>();var current=new AtomicReference<Trace>();var serving=new AtomicReference<MembershipTransferService>();
        try(var group=helper.new Group(size,raw)) {
            var fixture=group.fixture;fixture.ownedHistory=true;var receiving=resources();
            try(var owner=fixture.open(fixture.request.targets().getFirst(),"transfer-fault-source")) {
                var original=owner.beginActivation();var promise=owner.promised().orElseThrow();var ballot=object(original.basis.value().get("ballot"));
                Path captured=Files.createDirectory(raw.resolve("captured"));
                for(var target:fixture.request.targets())V53JournalApplicationTest.copy(target.replicaDirectory(),captured.resolve(target.identity().nodeId().value()));
                var contents=new ArrayList<Map<String,Object>>();Path exported=Files.createDirectory(raw.resolve("exported"));
                try(var export=owner.exportSource(original.basis,BUDGET)) {
                    for(var content:export.contents()) {
                        Files.write(exported.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));
                        contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                    }
                }
                contents.sort(Comparator.comparing(row->(String)row.get("digest")));Files.write(raw.resolve("contents.json"),canonical(contents,65536));
                var bounds=V53TransferServiceTest.bound(2);
                var server=group.start(0,(peer,q)->serving.get().handle(peer,q),(event,q,a)->{
                    var trace=current.get();if(trace!=null)trace.wire("server",event,q,a);
                },bounds,fixture.resources);
                var client=group.start(1,group::status,(event,q,a)->{
                    var trace=current.get();if(trace!=null)trace.wire("client",event,q,a);
                },bounds,receiving);
                Path cases=Files.createDirectory(raw.resolve("cases"));
                for(String name:CASES) {
                    Path output=Files.createDirectory(cases.resolve(name));var trace=new Trace(name);current.set(trace);
                    long started=System.nanoTime();var offset=new AtomicLong();var last=new AtomicReference<Decoded>();
                    var baseline=usage(fixture.resources);var clientBaseline=usage(receiving);
                    var service=new MembershipTransferService(owner,ballot,fixture.resources,bounds,
                            ()->owner.checkActivation(original.basis,null,false),()->System.nanoTime()+offset.get(),started,BUDGET);
                    serving.set(service);boolean success=false;
                    MembershipSourcePull.Link link=(peer,q,kind,deadline)->{
                        trace.add("CALL","request",encoded(q),"expected",kind,"deadline",deadline);last.set(q);
                        return client.exchange(peer,q,kind,deadline).handle((reply,failure)->{
                            if(failure!=null){var error=cause(failure);trace.add("FAILURE","request",encoded(q),"reason",
                                    error instanceof MembershipTransport.Failure f?f.reason.name():error.getClass().getSimpleName());throw new CompletionException(error);}
                            trace.add("REPLY","request",encoded(q),"response",encoded(reply));return reply;
                        });
                    };
                    try(service) {
                        trace.add("OPEN","started",started,"budget",BUDGET,"maximumAttempts",Math.min(3,bounds.maxRetryAttempts()),"source",original.basis.digest());
                        if(name.endsWith("-active")) {
                            var q=decode(encode("wire","CHUNK",Map.of("root",original.capsule.context.root,"view",original.capsule.context.authority(),
                                    "ballot",ballot,"sender",MembershipBootstrapSeed.identity(group.identities.get(1)),"recipient",MembershipBootstrapSeed.identity(original.owner),
                                    "trace",UUID.randomUUID().toString(),"sequence",1L,"payload",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST",
                                            "offset",0L,"digest",promise.digest(),"bytes",""))),"wire","CHUNK");
                            assertEquals("SOURCE_OFFER",link.exchange(original.owner,q,"SOURCE_OFFER",started+BUDGET).get(15,TimeUnit.SECONDS).kind());
                        }else {
                            try(var pull=new MembershipSourcePull(original.capsule,group.identities.get(1),original.owner,ballot,UUID.randomUUID(),receiving,
                                    bounds,link,()->{},System::nanoTime,started,BUDGET)) {
                                if(name.equals("exhausted-offer"))assertThrows(MembershipTransport.Failure.class,
                                        ()->pull.fetchRecord(promise.digest(),"PROMISE",v->V53RecordExchangeTest.promise(v,original.capsule.context,ballot)));
                                else {
                                    var result=pull.fetchRecord(promise.digest(),"PROMISE",v->V53RecordExchangeTest.promise(v,original.capsule.context,ballot));
                                    assertArrayEquals(promise.bytes(),result.bytes());Files.write(output.resolve("record.gsr"),result.bytes());
                                }
                            }
                        }
                        drain(server,client);var originalLast=last.get();
                        if(name.startsWith("expired")) {offset.set(BUDGET);trace.add("EXPIRE","offset",BUDGET);}
                        else if(name.equals("closed-active")){service.close();trace.add("CLOSE_SERVICE");}
                        else if(name.equals("owner-closed-completed")){owner.close();trace.add("CLOSE_OWNER");}
                        else if(name.equals("changed-completed")) {
                            var value=new TreeMap<>(originalLast.value());var payload=new TreeMap<>(object(value.get("payload")));payload.put("digest","0".repeat(64));value.put("payload",payload);
                            var changed=decode(encode("wire",originalLast.kind(),value),"wire",originalLast.kind());trace.add("CHANGE_RETRY");
                            assertEquals(MembershipTransport.Reason.IO,V53MembershipTransportTest.failure(link.exchange(original.owner,changed,changed.kind(),started+BUDGET)).reason);
                        }
                        if(name.contains("active") || name.contains("completed")) {
                            String answer=originalLast.kind().equals("CHUNK")?"SOURCE_OFFER":"TRANSFER_COMMIT";
                            assertEquals(MembershipTransport.Reason.IO,V53MembershipTransportTest.failure(link.exchange(original.owner,originalLast,answer,started+BUDGET)).reason);
                            if(name.startsWith("expired")) {
                                offset.set(0);trace.add("RESET_CLOCK");
                                assertEquals(MembershipTransport.Reason.IO,V53MembershipTransportTest.failure(link.exchange(original.owner,originalLast,answer,started+BUDGET)).reason);
                            }
                        }
                        drain(server,client);trace.add("BEFORE_CLOSE","usage",V53TransferServiceTest.observed(service.usage()));
                        assertEquals(name.equals("exhausted-offer")?Math.min(3,bounds.maxRetryAttempts()):name.startsWith("lost-")?1:0,trace.drops);
                        success=true;
                    }finally {
                        drain(server,client);trace.add("AFTER_CLOSE","usage",V53TransferServiceTest.observed(service.usage()));
                        Files.write(output.resolve("events.json"),canonical(trace.events,1024*1024));
                        Files.write(output.resolve("result.json"),canonical(Map.of("case",name,"status",success?"PASS":"FAIL","drops",trace.drops,
                                "baseline",baseline,"after",usage(fixture.resources),"clientBaseline",clientBaseline,"clientAfter",usage(receiving)),65536));
                    }
                    assertEquals(new MembershipTransferService.Usage(0,0,0,true),service.usage());
                    if(!name.equals("owner-closed-completed"))assertEquals(baseline,usage(fixture.resources));
                    assertEquals(clientBaseline,usage(receiving));
                    summaries.add(Map.of("case",name,"size",size));System.out.println("v53TransferFaultCase="+size+"/"+name+" PASS");
                }
                current.set(null);for(var transport:group.transports)transport.close();
            }
            fixture.snapshot("after");Files.write(raw.resolve("calls.json"),canonical(fixture.calls,1024*1024));
        }
        return Map.of("size",size,"cases",summaries);
    }
}
