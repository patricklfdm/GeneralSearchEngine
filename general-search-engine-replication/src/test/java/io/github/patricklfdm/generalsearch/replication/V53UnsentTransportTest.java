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
import static io.github.patricklfdm.generalsearch.replication.V53MembershipTransportTest.*;

/** Original reserved-but-unwritten attempts, followed by an identical real TCP call. */
class V53UnsentTransportTest {
    @TempDir Path temp;
    private static void rejectWorkers(MembershipTransport transport)throws Exception {
        var field=MembershipTransport.class.getDeclaredField("workers");field.setAccessible(true);
        ((ExecutorService)field.get(transport)).shutdown();
    }
    @Test void refusedAndRejectedAttemptsKeepTheirOwnReleasedBuffersAcrossIdenticalRetry()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-unsent-resources/run-"+UUID.randomUUID()));
        System.out.println("v53UnsentResourceEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        String previous=System.getProperty("v53.transport.unsent");System.setProperty("v53.transport.unsent","true");
        try {
            for(String mode:List.of("refused-direct","refused-decorated","rejected-direct","rejected-decorated")) {
                Path raw=Files.createDirectory(evidence.resolve(mode));var helper=new V53MembershipTransportTest();helper.temp=temp;
                var capture=new AtomicReference<V53ResourceTransitionCapture>();
                var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>() {
                    @Override public boolean add(Map<String,Object> event){capture.get().event(size(),event);return super.add(event);}
                });
                var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var decorated=new AtomicInteger();
                try(var group=helper.new Group(3,raw)) {
                    capture.set(new V53ResourceTransitionCapture(raw,group.fixture.result.root().manifestDigest()));
                    var caller=capture.get().create(group.identities.get(0),0);var receiver=capture.get().create(group.identities.get(1),0);
                    MembershipTransport.Events clientEvents=new V53ConnectionTrace("node-1",events,wire);
                    if(mode.endsWith("decorated"))clientEvents=new V53JoiningTrace("node-1",events,wire,true).transport("unsent-test",new MembershipTransport.Events() {
                        @Override public void at(String event,Decoded request,Decoded reply){}
                        @Override public void unsent(Decoded request,UUID invocation,MembershipTransport.Reason reason) {
                            assertEquals(0,caller.usage().leases());decorated.incrementAndGet();
                        }
                    });
                    var client=group.start(0,group::status,clientEvents,bounds(1,5000,FRAME),caller);var request=group.request(0,1);
                    if(mode.startsWith("rejected"))rejectWorkers(client);
                    for(int i=0;i<2;i++) {
                        assertEquals(MembershipTransport.Reason.IO,failure(client.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
                        assertEquals(0,caller.usage().leases());assertEquals(0,client.usage().outgoing());
                    }
                    var failed=events.stream().filter(v->v.get("event").equals("NETWORK_UNSENT_FAILED")).toList();
                    assertEquals(2,failed.size());assertEquals(failed.getFirst().get("request"),failed.getLast().get("request"));
                    assertNotEquals(failed.getFirst().get("invocation"),failed.getLast().get("invocation"));
                    assertEquals(mode.endsWith("decorated")?2:0,decorated.get());
                    if(mode.startsWith("rejected")) {
                        client.close();client=group.start(0,group::status,clientEvents,bounds(1,5000,FRAME),caller);
                    }
                    var server=group.start(1,group::status,new V53ConnectionTrace("node-2",events,wire),bounds(1,5000,FRAME),receiver);
                    assertEquals("STATUS",client.exchange(group.identities.get(1),request,"STATUS",deadline()).get(10,TimeUnit.SECONDS).kind());
                    V53TransferFaultsTest.drain(server,client);
                    assertEquals(MembershipTransport.Reason.DEADLINE,failure(client.exchange(group.identities.get(1),request,"STATUS",System.nanoTime()-1)).reason);
                    client.close();assertEquals(MembershipTransport.Reason.CLOSED,failure(client.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
                    assertEquals(2,events.stream().filter(v->v.get("event").equals("NETWORK_UNSENT_FAILED")).count());
                    group.fixture.snapshot("after");
                }
                byte[] eventBytes=V53EvidenceArray.encode(events,1024*1024);Files.write(raw.resolve("events.json"),eventBytes);
                Files.write(raw.resolve("wire.json"),canonical(wire,1024*1024));capture.get().save(eventBytes);
                cases.add(Map.of("case",mode,"unsentAttempts",2,"connectedAttempts",1,"frameLifetimes",6,"storageUnchanged",true));
            }
        }finally{if(previous==null)System.clearProperty("v53.transport.unsent");else System.setProperty("v53.transport.unsent",previous);}
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-unsent-resources-v1","status","PASS","cases",cases,
                "execution","loopback-tcp-component","completeMembershipHistory",false,"phase3Complete",false),65536));
    }
    @Test void failingObserverDoesNotReplaceFailureOrLeakTheOriginalPermit()throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;var seen=new AtomicInteger();
        try(var group=helper.new Group(3)) {
            var budget=resources(MembershipResources.QUEUE_LIMIT);
            var client=group.start(0,group::status,new MembershipTransport.Events() {
                @Override public void at(String event,Decoded request,Decoded response){}
                @Override public void unsent(Decoded request,UUID invocation,MembershipTransport.Reason reason)throws IOException {
                    assertEquals(0,budget.usage().leases());seen.incrementAndGet();throw new IOException("declared observer failure");
                }
            },bounds(1,5000,FRAME),budget);
            for(int i=0;i<2;i++) {
                var error=failure(client.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline()));
                assertEquals(MembershipTransport.Reason.IO,error.reason);assertEquals(1,error.getSuppressed().length);
                assertEquals("declared observer failure",error.getSuppressed()[0].getMessage());assertEquals(0,client.usage().outgoing());
            }
            assertEquals(2,seen.get());
        }
    }
}
