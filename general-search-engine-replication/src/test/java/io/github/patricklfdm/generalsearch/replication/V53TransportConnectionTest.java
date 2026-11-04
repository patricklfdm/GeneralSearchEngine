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

/** Deterministic overlap of identical requests on distinct actual TCP sockets. */
class V53TransportConnectionTest {
    @TempDir Path temp;
    @Test void lateOriginalTerminalCannotBeAssignedToSuccessfulIdenticalRetry()throws Exception {run(false);}
    @Test void joiningCollectorsRetainIdentitiesThroughDecoratorsAndOldCallbacks()throws Exception {run(true);}
    private void run(boolean joining)throws Exception {
        Path evidence=Files.createDirectories(Path.of((joining?"target/v53-joining-connections/run-":"target/v53-transport-connections/run-")+UUID.randomUUID()));
        System.out.println((joining?"v53JoiningConnectionEvidence=":"v53TransportConnectionEvidence=")+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(String mode:List.of("late-handler","late-response")) {
            Path raw=Files.createDirectory(evidence.resolve(mode));var helper=new V53MembershipTransportTest();helper.temp=temp;
            var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var firstEntered=new CountDownLatch(1);var secondEntered=new CountDownLatch(1);
            var releaseFirst=new CountDownLatch(1);var releaseSecond=new CountDownLatch(1);var firstFailed=new CountDownLatch(1);
            var calls=new AtomicInteger();var firstConnection=new AtomicReference<UUID>();
            try(var group=helper.new Group(3,raw)) {
                MembershipTransport.Events receiver=joining?new V53JoiningTrace("node-2",events,wire,true).transport("connection-test",(point,q,a)->{}):
                        new V53ConnectionTrace("node-2",events,wire);
                var observation=new MembershipTransport.Events() {
                    @Override public void at(String event,Decoded request,Decoded response) {fail("connection omitted");}
                    @Override public void at(String event,Decoded request,Decoded response,MembershipTransport.Connection connection)throws IOException {
                        receiver.at(event,request,response,connection);
                        if(event.equals("AFTER_REQUEST_READ"))firstConnection.compareAndSet(null,connection.id());
                        if(mode.equals("late-response") && event.equals("BEFORE_RESPONSE_WRITE") && connection.id().equals(firstConnection.get()))
                            throw new IOException("declared loss of late original response");
                    }
                    @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason,MembershipTransport.Connection connection)throws IOException {
                        receiver.failed(outbound,request,reason,connection);
                        if(connection.id().equals(firstConnection.get()))firstFailed.countDown();
                    }
                };
                var server=group.start(1,(peer,request)->{
                    if(calls.getAndIncrement()==0) {
                        firstEntered.countDown();await(releaseFirst);
                        if(mode.equals("late-handler"))throw new IOException("declared late original handler failure");
                    }else {secondEntered.countDown();await(releaseSecond);}
                    return group.status(peer,request);
                },observation,bounds(2,2000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
                var client=group.start(0,group::status,joining?oldCollector("node-1",events,wire):new V53ConnectionTrace("node-1",events,wire),bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
                var request=group.request(0,1);long firstStart=System.nanoTime();
                var first=client.exchange(group.identities.get(1),request,"STATUS",firstStart+TimeUnit.SECONDS.toNanos(1));
                try {
                    await(firstEntered);assertEquals(MembershipTransport.Reason.DEADLINE,failure(first).reason);
                    var second=client.exchange(group.identities.get(1),request,"STATUS",deadline());await(secondEntered);
                    if(mode.equals("late-handler")) {
                        releaseSecond.countDown();assertEquals("STATUS",second.get(10,TimeUnit.SECONDS).kind());releaseFirst.countDown();await(firstFailed);
                    }else {
                        // The caller already timed out. Retain the late offered
                        // response and injected I/O terminal before allowing the
                        // successful retry to return identical response bytes.
                        releaseFirst.countDown();await(firstFailed);releaseSecond.countDown();
                        assertEquals("STATUS",second.get(10,TimeUnit.SECONDS).kind());
                    }
                }finally{releaseFirst.countDown();releaseSecond.countDown();}
                V53TransferFaultsTest.drain(server,client);group.fixture.snapshot("after");assertEquals(2,calls.get());
                var sends=events.stream().filter(v->Set.of("BEFORE_REQUEST_WRITE","NETWORK_SEND").contains(v.get("event"))).toList();
                assertEquals(2,sends.size());assertEquals(sends.getFirst().get("request"),sends.getLast().get("request"));
                assertNotEquals(sends.getFirst().get("connection"),sends.getLast().get("connection"));
            }
            Files.write(raw.resolve("events.json"),canonical(events,1024*1024));Files.write(raw.resolve("wire.json"),canonical(wire,1024*1024));
            cases.add(Map.of("case",mode,"attempts",2,"callerFailures",1,"serverFailures",1,"deliveredReplies",1,"storageUnchanged",true));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-transport-connections-v1","status","PASS","cases",cases,
                "execution","loopback-tcp-component","completeMembershipHistory",false,"phase3Complete",false),65536));
    }
    private static MembershipTransport.Events oldCollector(String node,List<Map<String,Object>> events,List<Map<String,Object>> wire) {
        return V53JoiningTrace.withFailures(node,null,events,()->true,()->true,(event,request,response)->{
            V53JoiningTrace.requestObservation(events,node,event,request);
            if(event.equals("AFTER_RESPONSE_READ"))events.add(V53JoiningTrace.connected(Map.of("node",node,"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest())));
            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                events.add(V53JoiningTrace.connected(Map.of("node",node,"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest())));
                var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",false);wire.add(V53JoiningTrace.connected(row));
            }
        });
    }

}
