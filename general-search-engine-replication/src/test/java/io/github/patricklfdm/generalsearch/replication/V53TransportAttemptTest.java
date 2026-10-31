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

/** Actual failed TCP attempts and exact retries; no membership/quorum claim. */
class V53TransportAttemptTest {
    @TempDir Path temp;
    @Test void originalFailuresAndIdenticalRetriesRetainTerminalObservations()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-transport-attempts/run-"+UUID.randomUUID()));
        System.out.println("v53TransportAttemptEvidence="+evidence.toAbsolutePath());
        var cases=new ArrayList<Map<String,Object>>();
        for(boolean scoped:List.of(false,true))for(String mode:List.of("handler-io","handler-protocol","send-guard")) {
            String name=(scoped?"scoped-":"old-")+mode;Path raw=Files.createDirectory(evidence.resolve(name));
            var helper=new V53MembershipTransportTest();helper.temp=temp;
            var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var handling=new AtomicInteger();
            try(var group=helper.new Group(3,raw)) {
                var server=group.start(1,(peer,request)->{
                    if(handling.getAndIncrement()==0 && !mode.equals("send-guard")) {
                        if(mode.equals("handler-protocol"))throw new IllegalArgumentException("declared handler context refusal");
                        throw new IOException("declared handler I/O failure");
                    }
                    return group.status(peer,request);
                },trace("node-2",scoped,events,wire),bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
                var client=group.start(0,group::status,trace("node-1",scoped,events,wire),
                        bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
                var request=group.request(0,1);long end=deadline();
                var pending=client.exchange(group.identities.get(1),request,"STATUS",end,()->{
                    if(mode.equals("send-guard"))throw new IOException("declared pre-write revocation");
                });
                assertEquals(MembershipTransport.Reason.IO,failure(pending).reason);
                assertEquals(1,events.stream().filter(row->"NETWORK_ATTEMPT_FAILED".equals(row.get("event")) && "OUTBOUND".equals(row.get("direction"))).count());
                var reply=client.exchange(group.identities.get(1),request,"STATUS",end).get(10,TimeUnit.SECONDS);
                assertArrayEquals(group.status(group.identities.getFirst(),request).bytes(),reply.bytes());
                V53TransferFaultsTest.drain(server,client);group.fixture.snapshot("after");
                assertEquals(mode.equals("send-guard")?1:2,handling.get());
            }
            Files.write(raw.resolve("events.json"),canonical(events,1024*1024));
            Files.write(raw.resolve("wire.json"),canonical(wire,1024*1024));
            cases.add(Map.of("case",name,"failedWrites",1,"successfulReplies",1,"storageUnchanged",true));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-transport-attempts-v1","status","PASS",
                "cases",cases,"network",true,"phase3Complete",false,"completeMembershipHistory",false),65536));
    }
    private static MembershipTransport.Events trace(String node,boolean scoped,List<Map<String,Object>> events,List<Map<String,Object>> wire) {
        if(scoped)return new V53JoiningTrace(node,events,wire).transport("attempt-test",(event,request,response)->{});
        return V53JoiningTrace.withFailures(node,null,events,()->true,(event,request,response)->{
            V53JoiningTrace.requestObservation(events,node,event,request);
            if(event.equals("AFTER_RESPONSE_READ"))events.add(Map.of("node",node,"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest()));
            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                events.add(Map.of("node",node,"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest()));
                var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",false);wire.add(row);
            }
        });
    }
    @Test void observerFailureCannotReplacePrimaryFailureOrLeakCapacity()throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;var observed=new AtomicInteger();
        var observer=new MembershipTransport.Events() {
            @Override public void at(String event,Decoded request,Decoded response) {}
            @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason)throws IOException {
                observed.incrementAndGet();throw new IOException("observer unavailable");
            }
        };
        try(var group=helper.new Group(3)) {
            var server=group.start(1,(peer,request)->{throw new IOException("handler failed");},observer,
                    bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var client=group.start(0,group::status,observer,bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var error=failure(client.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline()));
            assertEquals(MembershipTransport.Reason.IO,error.reason);assertEquals(1,error.getSuppressed().length);
            assertEquals("observer unavailable",error.getSuppressed()[0].getMessage());
            V53TransferFaultsTest.drain(server,client);assertEquals(2,observed.get());
        }
    }
    @Test void preflightRejectionDoesNotInventAnAttemptedWrite()throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;var observed=new AtomicInteger();
        var observer=new MembershipTransport.Events() {
            @Override public void at(String event,Decoded request,Decoded response){observed.incrementAndGet();}
            @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason){observed.incrementAndGet();}
        };
        try(var group=helper.new Group(3)) {
            var client=group.start(0,group::status,observer,bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            assertEquals(MembershipTransport.Reason.DEADLINE,failure(client.exchange(group.identities.get(1),group.request(0,1),"STATUS",System.nanoTime()-1)).reason);
            assertEquals(0,observed.get());
        }
    }
    @Test void observedDeadlineAndCloseKeepTheirOriginalClassification()throws Exception {
        for(boolean close:List.of(false,true)) {
            var helper=new V53MembershipTransportTest();helper.temp=temp;var arrived=new CountDownLatch(1);var release=new CountDownLatch(1);
            var failures=new ArrayList<MembershipTransport.Reason>();
            var observer=new MembershipTransport.Events() {
                @Override public void at(String event,Decoded request,Decoded response) {}
                @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason){if(outbound)failures.add(reason);}
            };
            try(var group=helper.new Group(3)) {
                var server=group.start(1,(peer,request)->{arrived.countDown();await(release);return group.status(peer,request);},MembershipTransport.Events.NONE,
                        bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
                var client=group.start(0,group::status,observer,bounds(1,close?5000:250,FRAME),resources(MembershipResources.QUEUE_LIMIT));
                var pending=client.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline());
                try {
                    await(arrived);if(close)client.close();
                    var reason=close?MembershipTransport.Reason.CLOSED:MembershipTransport.Reason.DEADLINE;
                    assertEquals(reason,failure(pending).reason);assertEquals(List.of(reason),failures);
                }finally{release.countDown();}
                V53TransferFaultsTest.drain(server,client);
            }
        }
    }
}
