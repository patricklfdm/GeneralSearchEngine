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
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** The actual native owner chooses entries and readiness; tests do not sequence
 * the activation or carried slot/barrier for it. No public runtime is enabled. */
class V53RoundDriverTest {
    @TempDir Path temp;
    V53NativeDispatchTest.Network network(String old)throws Exception {
        return network(old,ReplicationBounds.defaults());
    }
    V53NativeDispatchTest.Network network(String old,ReplicationBounds bounds)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        return helper.new Network(3,bounds,f->{if(old!=null)V53CarriedSlotDriverTest.prepare(f,old);});
    }
    ReplicationBounds controlBounds() {
        var b=ReplicationBounds.defaults();
        return new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
    }
    MembershipRoundDriver<?,?> driver(V53NativeDispatchTest.Network n,MembershipRoundDriver.Events callback)throws Exception {
        return new MembershipRoundDriver<>(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,n.transports.getFirst(),
                temp.resolve("round-"+UUID.randomUUID()),()->System.nanoTime()+n.offset.get(),V53NativeDispatchTest.BUDGET,2,
                builder().configuration(),n.f.request.targets().getFirst().materialization(),(event,record)->{
                    n.events.add(Map.of("node","node-1","event","ROUND_"+event,"record",record.digest(),
                            "bytes",Base64.getEncoder().encodeToString(record.bytes())));
                    if(event.equals("INSTALLED")) {
                        n.selected=record;n.ballot=object(record.value().get("ballot"));
                        n.voters=list(record.value().get("sources")).stream().map(v->Integer.parseInt(((String)object(v).get("voter")).substring(5))-1).sorted().toList();
                        try{n.f.snapshot("installed");}catch(Exception error){throw new IOException(error);}
                        Files.write(n.f.raw.resolve("selected.gsr"),record.bytes());
                    }
                    if(event.equals("SLOT_BEGIN"))n.events.add(Map.of("node","node-1","event",event,"index",record.value().get("index")));
                    callback.at(event,record);
                },(event,record,voters)->{
                    if(event.equals("FUTURE_QUORUM_COMPLETE"))n.events.add(Map.of("node","node-1","event",event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                    if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{n.f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));}
                    catch(Exception error){throw new IOException(error);}
                });
    }
    byte[] data(V53NativeDispatchTest.Network n)throws Exception {
        try(var encoder=new ReplicaApplication<>(builder().configuration(),n.f.request.targets().getFirst().materialization(),n.bounds)) {
            return MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(100,"next-slot"))));
        }
    }
    @Test void activationFreshBarrierAndSequentialDataHaveOneGuardedOwner()throws Exception {
        try(var n=network(null);var round=driver(n,MembershipRoundDriver.Events.NONE)) {
            assertEquals(MembershipRoundDriver.State.NEW,round.state());assertThrows(IllegalArgumentException.class,round::readiness);
            assertThrows(IllegalArgumentException.class,()->driver(n,MembershipRoundDriver.Events.NONE));
            var barrier=round.start();assertEquals("PUBLISH_ACK",barrier.kind());assertArrayEquals(barrier.bytes(),round.readiness().bytes());
            assertEquals(MembershipRoundDriver.State.READY,round.state());
            assertThrows(IllegalArgumentException.class,round::start);
            assertThrows(IllegalArgumentException.class,()->round.submit("INTENT",new byte[0]));
            assertThrows(IllegalArgumentException.class,()->round.submit("BARRIER",new byte[]{1}));
            var done=round.submit("DATA",data(n));assertEquals("PUBLISH_ACK",done.kind());
            assertArrayEquals(barrier.bytes(),round.readiness().bytes());
            for(int i:n.voters)assertEquals(2L,n.owners.get(i).activationContext().cut.get("index"));
            assertEquals(0L,n.owners.get(2).activationContext().cut.get("index"));
            Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","slots",2,"network",true,"autonomous",false),4096));
            Files.write(n.f.raw.resolve("round-result.json"),canonical(Map.of("status","PASS","mode","stable","internalReady",true,"publicReady",false),4096));
        }
    }
    @Test void retainedAppliedEntryCompletesBeforeFreshReadyBarrier()throws Exception {
        // This tests carried completion ordering, not a five-second RPC SLA.
        // Keep the original 180-second round and finite retry count. The failed
        // default-profile publication trace remains retained separately.
        try(var n=network("APPLIED",controlBounds());var round=driver(n,MembershipRoundDriver.Events.NONE)) {
            assertEquals("PUBLISH_ACK",round.start().kind());assertEquals(MembershipRoundDriver.State.READY,round.state());round.readiness();
            for(int i:n.voters)assertEquals(2L,n.owners.get(i).activationContext().cut.get("index"));
            Files.write(n.f.raw.resolve("carried-result.json"),canonical(Map.of("status","PASS","carried",n.selected.value().get("nextEntry"),"slots",2,"publicReady",false),4096));
            Files.write(n.f.raw.resolve("round-result.json"),canonical(Map.of("status","PASS","mode","carried-applied","internalReady",true,"publicReady",false),4096));
        }
    }
    @Test void concreteReserveAndCancelPreserveThePermanentIdentityCatalog()throws Exception {
        // Qualify control semantics with the supported caller timeout. The
        // original default-timeout failure is retained separately; this profile
        // does not establish a five-second response SLA or extend the round.
        try(var n=network(null,controlBounds());var round=driver(n,MembershipRoundDriver.Events.NONE)) {
            var sends=new ConcurrentHashMap<String,Long>();
            var durations=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            n.beforeSend.set(request->sends.putIfAbsent(request.digest(),System.nanoTime()));
            n.response.set((request,reply)->{
                var began=sends.get(request.digest());
                if(began!=null)durations.add(Map.of("request",request.digest(),"kind",request.kind(),"elapsedNanos",System.nanoTime()-began));
                return reply;
            });
            long began=System.nanoTime();
            try {
            round.start();assertThrows(IllegalArgumentException.class,()->round.submit("CONTROL",new byte[0]));
            var own=n.owners.getFirst();var context=own.activationContext();var targets=new ArrayList<Map<String,Object>>();
            for(var t:n.f.request.targets())targets.add(MembershipBootstrapSeed.identity(t.identity()));
            int port;try(var socket=new java.net.ServerSocket(0,1,java.net.InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var learner=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            targets.add(MembershipBootstrapSeed.identity(learner));
            var request=Map.of("root",context.root,"expected",context.authority(),"number",1L,"kind","ADD","target",targets);
            assertEquals("PUBLISH_ACK",round.submit("RESERVE",canonical(Map.of("request",request),8192)).kind());
            for(int i:n.voters) {
                var observed=n.owners.get(i).activationContext();assertEquals(2L,observed.catalog.get("nextOperation"));
                assertEquals(learner,observed.identities.get("node-4"));assertFalse(observed.voters().contains("node-4"));
            }
            assertEquals("PUBLISH_ACK",round.submit("CANCEL",canonical(Map.of("number",1L),8192)).kind());round.readiness();
            for(int i:n.voters) {
                var observed=n.owners.get(i).activationContext();assertEquals(3L,observed.cut.get("index"));
                assertNull(observed.catalog.get("active"));assertEquals(learner,observed.identities.get("node-4"));
                assertEquals("CANCELLED",object(list(observed.catalog.get("results")).getFirst()).get("phase"));
            }
            assertEquals(MembershipRoundDriver.State.READY,round.state());
            Files.write(n.f.raw.resolve("round-control-result.json"),canonical(Map.of("status","PASS","slots",3,"controls",List.of("RESERVE","CANCEL"),"publicReady",false),4096));
            }finally {
                Files.write(n.f.raw.resolve("round-control-timing.json"),canonical(Map.of("requestTimeoutMillis",n.bounds.requestTimeoutMillis(),
                        "roundBudgetNanos",V53NativeDispatchTest.BUDGET,"elapsedNanos",System.nanoTime()-began,"exchanges",durations),1024*1024));
            }
        }
    }
    @Test void beforeReadyFailureDoesNotRestoreReadinessFromDurablePublication()throws Exception {
        try(var n=network(null);var round=driver(n,(event,record)->{if(event.equals("BEFORE_READY"))throw new IOException("lost readiness delivery");})) {
            assertThrows(IOException.class,round::start);assertEquals(MembershipRoundDriver.State.FAILED,round.state());
            assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
            assertThrows(IllegalArgumentException.class,round::readiness);assertThrows(IllegalArgumentException.class,round::start);
            assertThrows(IllegalArgumentException.class,()->round.submit("BARRIER",new byte[0]));
        }
    }
    @Test void higherBallotAtReadyBoundaryPreventsService()throws Exception {
        try(var n=network(null);var round=driver(n,(event,record)->{if(event.equals("BEFORE_READY")) {
            var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);n.owners.getFirst().observeCurrent(higher);
        }})) {
            assertThrows(IllegalArgumentException.class,round::start);assertEquals(MembershipRoundDriver.State.FAILED,round.state());
            assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));assertThrows(IllegalArgumentException.class,round::readiness);
        }
    }
    @Test void stableSubmitCannotResetTheOriginalDeadline()throws Exception {
        try(var n=network(null);var round=driver(n,MembershipRoundDriver.Events.NONE)) {
            round.start();var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());n.offset.set(V53NativeDispatchTest.BUDGET);
            assertThrows(IllegalArgumentException.class,()->round.submit("BARRIER",new byte[0]));
            assertEquals(MembershipRoundDriver.State.FAILED,round.state());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void endedEndpointCannotRestoreReadinessFromInstalledFiles()throws Exception {
        try(var n=network(null);var round=driver(n,MembershipRoundDriver.Events.NONE)) {
            round.start();n.endpoints.getFirst().abandon(n.ballot);
            assertThrows(IllegalArgumentException.class,round::readiness);assertEquals(MembershipRoundDriver.State.FAILED,round.state());
            assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
        }
    }
    @Test void busyOwnerRefusesAnotherCallAndCloseDrainsWithoutReady()throws Exception {
        try(var n=network(null)) {
            var entered=new CountDownLatch(1);var proceed=new CountDownLatch(1);
            try(var round=driver(n,(event,record)->{if(event.equals("INSTALLED")) {
                entered.countDown();try{proceed.await();}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
            }})) {
                var result=CompletableFuture.runAsync(()->assertThrows(IOException.class,round::start));
                assertTrue(entered.await(60,TimeUnit.SECONDS));assertThrows(IllegalArgumentException.class,round::start);
                assertThrows(IllegalArgumentException.class,()->round.submit("BARRIER",new byte[0]));round.close();result.get(10,TimeUnit.SECONDS);
                assertEquals(MembershipRoundDriver.State.CLOSED,round.state());assertEquals(0L,n.owners.getFirst().activationContext().cut.get("index"));
                assertTrue(n.events.stream().noneMatch(e->e.get("event").equals("ACCEPT_PARENT_FORCED")));
            }finally{proceed.countDown();}
        }
    }
    @Test void closeDuringSlotCancelsRemoteWorkAndDoesNotAdmitAnotherCall()throws Exception {
        try(var n=network(null);var round=driver(n,(event,record)->{if(event.equals("INSTALLED"))n.holdNextQuery.set(true);})) {
            var result=CompletableFuture.runAsync(()->assertThrows(Exception.class,round::start));
            assertTrue(n.queryEntered.await(60,TimeUnit.SECONDS));round.close();result.get(10,TimeUnit.SECONDS);
            assertEquals(MembershipRoundDriver.State.CLOSED,round.state());assertThrows(IllegalArgumentException.class,round::readiness);
            assertTrue(n.events.stream().noneMatch(e->e.get("event").equals("PROOF_PARENT_FORCED")));
        }
    }
    @Test void activationUsesOuterStartInsteadOfGrantingANewDeadline()throws Exception {
        try(var n=network(null)) {
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            try(var activation=new MembershipActivationDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,n.transports.getFirst()::exchange,
                    List.of(),List.of(),temp.resolve("expired-"+UUID.randomUUID()),()->V53NativeDispatchTest.BUDGET,V53NativeDispatchTest.BUDGET,2)) {
                assertThrows(IllegalArgumentException.class,()->activation.run(0));assertEquals(0,activation.campaigns());
                assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            }
        }
    }
    @Test void closeDuringActivationPreventsALatePrepareWrite()throws Exception {
        try(var n=network(null);var round=driver(n,MembershipRoundDriver.Events.NONE)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var returned=new CountDownLatch(1);var first=new AtomicBoolean(true);
            n.beforeSend.set(request->{if(request.kind().equals("PREPARE") && first.compareAndSet(true,false)) {
                entered.countDown();try{release.await();}catch(InterruptedException error){Thread.currentThread().interrupt();}
                finally{returned.countDown();}
            }});
            var result=CompletableFuture.runAsync(()->assertThrows(Exception.class,round::start));
            try {
                assertTrue(entered.await(30,TimeUnit.SECONDS));round.close();result.get(10,TimeUnit.SECONDS);
                assertEquals(MembershipRoundDriver.State.CLOSED,round.state());
            }finally{release.countDown();}
            assertTrue(returned.await(10,TimeUnit.SECONDS));
            assertTrue(n.events.stream().noneMatch(v->v.get("node").equals("node-2") && v.get("event").equals("PROMISE_FORCED")));
            assertEquals(0L,n.owners.getFirst().activationContext().cut.get("index"));
        }
    }
}
