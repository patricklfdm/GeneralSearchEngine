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

class V53RetentionQuorumTest {
    @TempDir Path temp;
    final class Group implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture fixture;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<List<String>> events=new ArrayList<>();
        final List<AtomicReference<MembershipBallotAllocator.Cut>> hooks=new ArrayList<>();
        final List<Map<String,Object>> timeline=Collections.synchronizedList(new ArrayList<>());
        Group(int size)throws Exception {
            Path raw=Files.createDirectories(Path.of("target/v53-retention-quorum/run-"+UUID.randomUUID()));
            System.out.println("v53RetentionQuorumEvidence="+raw.toAbsolutePath());
            fixture=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),size,false));
            fixture.ownedHistory=true;
            for(var target:fixture.request.targets())try(var owner=fixture.open(target,"initialize")){owner.initializePeerRetention();}
            fixture.campaign(1);fixture.publish(1,false);fixture.snapshot("before-quorum");
            for(var target:fixture.request.targets()) {
                var budget=resources();budgets.add(budget);var trace=Collections.synchronizedList(new ArrayList<String>());events.add(trace);
                var hook=new AtomicReference<MembershipBallotAllocator.Cut>(event->{});hooks.add(hook);
                owners.add(MembershipGrantJournal.openRetainingPeers(target.replicaDirectory(),target.materialization().directory(),fixture.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{trace.add(event);timeline.add(Map.of("node",target.identity().nodeId().value(),"event",event));hook.get().at(event);}));
            }
        }
        MembershipRetentionQuorum round(MembershipSourcePull.Link link,java.util.function.LongSupplier clock,long started,long limit)throws Exception {
            return new MembershipRetentionQuorum(owners.getFirst(),fixture.request.targets().getLast().identity(),fixture.ballot,budgets.getFirst(),link,clock,started,limit);
        }
        @Override public void close()throws Exception {
            for(var owner:owners)owner.close();for(var budget:budgets){assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().queued());}
            Files.write(fixture.raw.resolve("calls.json"),canonical(fixture.calls,8*1024*1024));
            Files.write(fixture.raw.resolve("events.json"),canonical(events,1024*1024));fixture.snapshot("after-quorum");
            Files.write(fixture.raw.resolve("timeline.json"),canonical(timeline,1024*1024));
        }
    }
    @Test void realNetworkQuorumsAtEveryStableSizeAndLostDurableAck()throws Exception {
        for(int size:List.of(3,4,5))for(boolean lost:size==3?List.of(false,true):List.of(false)) {
            try(var group=new Group(size)) {
                var endpoints=new ArrayList<MembershipActivationEndpoint>();var transports=new ArrayList<MembershipTransport>();
                var links=new ArrayList<AtomicReference<MembershipTransport>>();var requests=new ConcurrentHashMap<String,List<String>>();
                var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var dropped=new AtomicBoolean();
                for(int i=0;i<size;i++)links.add(new AtomicReference<>());
                try {
                    for(int i=0;i<size;i++) {
                        int local=i;
                        var endpoint=new MembershipActivationEndpoint(group.owners.get(i),group.budgets.get(i),bounds(),
                                (peer,request,kind,deadline)->links.get(local).get().exchange(peer,request,kind,deadline),List.of(),List.of(),
                                temp.resolve("endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);endpoints.add(endpoint);
                        var transport=new MembershipTransport(group.owners.get(i).activationCapsule(),group.fixture.request.targets().get(i).identity(),bounds(),group.budgets.get(i),endpoint,
                                (event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                    wire.add(V53SelectedPullTest.wire(request,response));
                                    if(lost && local==1 && dropped.compareAndSet(false,true))throw new IOException("lost durable retention ACK");
                                }});transports.add(transport);links.get(i).set(transport);
                    }
                    MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                        requests.computeIfAbsent(peer.nodeId().value(),k->Collections.synchronizedList(new ArrayList<>())).add(request.digest());
                        if(lost && peer.nodeId().value().equals("node-3"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline",null));
                        return transports.getFirst().exchange(peer,request,kind,deadline).thenApply(reply->{
                            group.timeline.add(Map.of("node",peer.nodeId().value(),"event","ACK_RECEIVED","digest",reply.digest()));return reply;});
                    };
                    try(var round=group.round(link,System::nanoTime,System.nanoTime(),BUDGET)) {
                        var permit=round.run();assertEquals(size/2+1,permit.voters().size());
                        assertEquals("queued-exact-target",permit.dispatch(()->{group.timeline.add(Map.of("node","node-1","event","DISPATCH"));return "queued-exact-target";}));
                        Files.write(group.fixture.raw.resolve("network.json"),canonical(Map.of("size",(long)size,"lostAck",lost,
                                "voters",permit.voters().stream().sorted().toList(),"intent",permit.intent()),16384));
                        for(String node:permit.voters()) {
                            int index=Integer.parseInt(node.substring(5))-1;var owner=group.owners.get(index);
                            assertEquals(1,owner.peerRetentionState().revision());
                            assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(group.fixture.request.targets().getLast().identity())));
                        }
                        if(lost){assertTrue(dropped.get());assertEquals(2,requests.get("node-2").size());assertEquals(1,new HashSet<>(requests.get("node-2")).size());}
                        group.owners.getFirst().observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",group.owners.getFirst().activationIdentity().storageId().toString()));
                        assertThrows(IllegalArgumentException.class,()->permit.dispatch(()->fail("fenced permit dispatched")));
                    }
                }finally {
                    for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();
                    Files.write(group.fixture.raw.resolve("wire.json"),canonical(wire,1024*1024));
                    Files.write(group.fixture.raw.resolve("requests.json"),canonical(new TreeMap<>(requests).entrySet().stream()
                            .map(row->Map.of("node",row.getKey(),"digests",List.copyOf(row.getValue()))).toList(),65536));
                }
            }
        }
    }
    @Test void failedQuorumExhaustsOnlyThreeIdenticalAttemptsAndNeverDispatches()throws Exception {
        try(var group=new Group(3)) {
            var sent=new TreeMap<String,List<String>>();
            MembershipSourcePull.Link failed=(peer,request,kind,deadline)->{
                sent.computeIfAbsent(peer.nodeId().value(),k->new ArrayList<>()).add(request.digest());
                return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null));
            };
            try(var round=group.round(failed,System::nanoTime,System.nanoTime(),BUDGET)) {
                var error=assertThrows(IllegalArgumentException.class,round::run);assertEquals("retention quorum unavailable",error.getMessage());
            }
            for(var row:sent.values()){assertEquals(3,row.size());assertEquals(1,new HashSet<>(row).size());}
            assertEquals(1,group.owners.getFirst().peerRetentionState().revision());
            for(var owner:group.owners.subList(1,3))assertEquals(0,owner.peerRetentionState().revision());
        }
    }
    @Test void originalDeadlineAndMalformedAcknowledgementCannotGrantPermit()throws Exception {
        for(boolean late:List.of(false,true))try(var group=new Group(3)) {
            long started=System.nanoTime();var clock=new AtomicLong(started);var count=new AtomicInteger();
            MembershipSourcePull.Link faulty=(peer,request,kind,deadline)->{
                count.incrementAndGet();
                try {
                    var owner=group.owners.get(Integer.parseInt(peer.nodeId().value().substring(5))-1);
                    var response=owner.recordPeerRetention(group.owners.getFirst().activationIdentity(),request);
                    if(late)clock.set(started+BUDGET);
                    else {var value=new TreeMap<>(response.value());var payload=new TreeMap<>(object(value.get("payload")));payload.put("intent","f".repeat(64));value.put("payload",payload);response=decode(encode("wire","RETENTION_ACK",value),"wire","RETENTION_ACK");}
                    return CompletableFuture.completedFuture(response);
                }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
            };
            try(var round=group.round(faulty,clock::get,started,BUDGET)) {assertThrows(IllegalArgumentException.class,round::run);}
            assertTrue(count.get()<=2);assertEquals(0,group.budgets.getFirst().usage().queued());
        }
    }
    @Test void duplicateAndLaterRealObservationDoNotRewriteOrRegressLedger()throws Exception {
        try(var group=new Group(3)) {
            var owner=group.owners.get(1);var local=group.owners.getFirst();var peer=group.fixture.request.targets().getLast().identity();
            var intent=local.peerRetentionIntent(peer,group.fixture.ballot);
            var request=MembershipActivation.frame("RETENTION_INTENT",local.activationContext(),local.activationIdentity(),owner.activationIdentity(),group.fixture.ballot,UUID.randomUUID(),1,intent.payload);
            var first=owner.recordPeerRetention(local.activationIdentity(),request);var before=V53ReplayFilesTest.files(group.fixture.request.targets().get(1).replicaDirectory());
            assertArrayEquals(first.bytes(),owner.recordPeerRetention(local.activationIdentity(),request).bytes());
            assertEquals(before,V53ReplayFilesTest.files(group.fixture.request.targets().get(1).replicaDirectory()));
            owner.retainPeerObservation(group.owners.getLast().floorCopyCurrent());assertEquals(2,owner.peerRetentionState().revision());
            var reply=owner.recordPeerRetention(local.activationIdentity(),request);assertEquals(2L,object(reply.value().get("payload")).get("revision"));
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer)));
            owner.observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",local.activationIdentity().storageId().toString()));
            before=V53ReplayFilesTest.files(group.fixture.request.targets().get(1).replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->owner.recordPeerRetention(local.activationIdentity(),request));
            assertEquals(before,V53ReplayFilesTest.files(group.fixture.request.targets().get(1).replicaDirectory()));
        }
    }
    @Test void closeCancelsAnExchangeReturnedAfterCancellation()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                entered.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("test release missing");}
                catch(InterruptedException e){Thread.currentThread().interrupt();throw new CompletionException(e);}return pending;
            };
            var executor=Executors.newSingleThreadExecutor();
            try(var round=group.round(link,System::nanoTime,System.nanoTime(),BUDGET)) {
                var running=executor.submit(()->{assertThrows(IllegalArgumentException.class,round::run);});
                assertTrue(entered.await(10,TimeUnit.SECONDS));round.close();release.countDown();running.get(10,TimeUnit.SECONDS);
                assertTrue(pending.isCancelled());assertEquals(0,group.budgets.getFirst().usage().queued());
            }finally{release.countDown();executor.shutdownNow();assertTrue(executor.awaitTermination(10,TimeUnit.SECONDS));}
        }
    }
    @Test void nativeFenceBeforeAckAndInvalidRequestsNeverAuthorizeDispatch()throws Exception {
        try(var group=new Group(3)) {
            var local=group.owners.getFirst();var owner=group.owners.get(1);var peer=group.fixture.request.targets().getLast().identity();
            var intent=local.peerRetentionIntent(peer,group.fixture.ballot);
            assertThrows(UnsupportedOperationException.class,()->intent.payload.put("selection","f".repeat(64)));
            assertThrows(UnsupportedOperationException.class,()->intent.lower.cut().put("index",10L));
            var original=MembershipActivation.frame("RETENTION_INTENT",local.activationContext(),local.activationIdentity(),owner.activationIdentity(),group.fixture.ballot,UUID.randomUUID(),1,intent.payload);
            var before=V53ReplayFilesTest.files(group.fixture.request.targets().get(1).replicaDirectory());
            for(String mutation:List.of("root","selection","lower","upper","peer","proposer")) {
                var value=new TreeMap<>(original.value());var payload=new TreeMap<>(object(value.get("payload")));
                switch(mutation) {
                    case "root"->value.put("root","f".repeat(64));
                    case "selection"->payload.put("selection","f".repeat(64));
                    case "lower","upper"->{var anchor=new TreeMap<>(object(payload.get(mutation)));anchor.put("catalog","f".repeat(64));payload.put(mutation,anchor);}
                    case "peer"->{var identity=new TreeMap<>(object(payload.get("peer")));identity.put("storage",UUID.randomUUID().toString());payload.put("peer",identity);}
                    case "proposer"->{var ballot=new TreeMap<>(object(value.get("ballot")));ballot.put("proposer","node-3");value.put("ballot",ballot);}
                    default->throw new AssertionError(mutation);
                }
                value.put("payload",payload);var bad=decode(encode("wire","RETENTION_INTENT",value),"wire","RETENTION_INTENT");
                assertThrows(IllegalArgumentException.class,()->owner.recordPeerRetention(local.activationIdentity(),bad),mutation);
                assertEquals(before,V53ReplayFilesTest.files(group.fixture.request.targets().get(1).replicaDirectory()),mutation);
            }
            assertThrows(IllegalArgumentException.class,()->new MembershipRetentionQuorum(local,peer,group.fixture.ballot,resources(),
                    (p,r,k,d)->fail("foreign budget performed exchange"),System::nanoTime,System.nanoTime(),BUDGET));
            group.hooks.get(1).set(event->{if(event.equals("RETENTION_PARENT_FORCED"))owner.observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",local.activationIdentity().storageId().toString()));});
            assertThrows(IllegalArgumentException.class,()->owner.recordPeerRetention(local.activationIdentity(),original));
            assertEquals(1,owner.peerRetentionState().revision());assertFalse(group.events.get(1).contains("RETENTION_ACK_BEFORE_RETURN"));
        }
    }
}
