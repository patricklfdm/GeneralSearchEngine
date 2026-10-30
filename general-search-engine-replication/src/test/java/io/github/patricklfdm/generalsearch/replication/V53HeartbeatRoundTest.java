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

class V53HeartbeatRoundTest {
    @TempDir Path temp;
    /** Component fixture has a genuinely installed selection. Only the native
     * round integration below establishes a fresh-barrier readiness guard. */
    final class Fixture implements AutoCloseable {
        final V53ActivationDriverTest.Local local;
        final MembershipActivationDriver activation;
        final AtomicLong clock=new AtomicLong();
        final List<Decoded> requests=Collections.synchronizedList(new ArrayList<>());
        final List<Long> deadlines=Collections.synchronizedList(new ArrayList<>());
        final AtomicReference<MembershipSourcePull.Link> link=new AtomicReference<>();
        Fixture()throws Exception {
            var helper=new V53ActivationDriverTest();helper.temp=temp;local=helper.local(clock,1000);
            activation=local.driver(2);activation.run();link.set((p,r,k,d)->local.deliver(0,p,r,k,d));
        }
        void guard()throws IOException {
            var owner=local.owners.getFirst();owner.checkActivation(owner.originalBasis().orElseThrow(),activation.selection(),true);
        }
        MembershipHeartbeatRound pulse()throws Exception {
            return new MembershipHeartbeatRound(local.owners.getFirst(),local.budgets.getFirst(),local.bound,
                (p,r,k,d)->{requests.add(r);deadlines.add(d);return link.get().exchange(p,r,k,d);},this::guard,clock::get,0,BUDGET);
        }
        CompletableFuture<Decoded> ack(MembershipIdentity peer,Decoded request) {
            return CompletableFuture.completedFuture(MembershipHeartbeat.answer(local.group.capsule.context,peer,local.group.identities.getFirst(),request));
        }
        MembershipIdentity first(){return local.group.identities.get(1);}
        @Override public void close()throws Exception{activation.close();local.close();}
    }
    @Test void majorityDoesNotWaitForUnresponsivePeerAndReleasesItsFuture()throws Exception {
        try(var f=new Fixture()) {
            var slow=new CompletableFuture<Decoded>();f.link.set((p,r,k,d)->p.equals(f.first())?f.ack(p,r):slow);
            var usage=f.local.budgets.getFirst().usage();
            try(var round=f.pulse()) {
                var result=round.run();assertEquals(Set.of("node-1","node-2"),result.responding());
                assertEquals(Set.of("node-2"),result.hints().keySet());assertTrue(slow.isCancelled());
                assertThrows(IllegalArgumentException.class,round::run);
            }
            assertEquals(2,f.requests.size());assertEquals(usage,f.local.budgets.getFirst().usage());f.guard();
        }
    }
    @Test void lostResponsesRetryIdenticalBytesUnderOneDeadline()throws Exception {
        try(var f=new Fixture()) {
            var count=new AtomicInteger();var slow=new CompletableFuture<Decoded>();
            f.link.set((p,r,k,d)->!p.equals(f.first())?slow:count.incrementAndGet()<3?
                    CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null)):f.ack(p,r));
            try(var round=f.pulse()){assertEquals(Set.of("node-1","node-2"),round.run().responding());}
            var attempts=f.requests.stream().filter(v->object(v.value().get("recipient")).get("node").equals("node-2")).toList();
            assertEquals(3,attempts.size());assertEquals(1,attempts.stream().map(Decoded::digest).distinct().count());
            assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));assertTrue(slow.isCancelled());
        }
    }
    @Test void exhaustedPeersFailWithoutResettingTheSamplingBudget()throws Exception {
        try(var f=new Fixture()) {
            f.link.set((p,r,k,d)->CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.DEADLINE,"missing",null)));
            var usage=f.local.budgets.getFirst().usage();
            try(var round=f.pulse()) {assertEquals("heartbeat majority unavailable",assertThrows(IllegalArgumentException.class,round::run).getMessage());}
            assertEquals(6,f.requests.size());assertEquals(2,f.requests.stream().map(Decoded::digest).distinct().count());
            assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));assertEquals(usage,f.local.budgets.getFirst().usage());
        }
    }
    @Test void capacityPeerIsNotRetriedWhenAnotherPeerCompletesMajority()throws Exception {
        try(var f=new Fixture()) {
            f.link.set((p,r,k,d)->p.equals(f.first())?CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"busy",null)):f.ack(p,r));
            try(var round=f.pulse()){assertEquals(Set.of("node-1","node-3"),round.run().responding());}
            assertEquals(2,f.requests.size());
        }
    }
    @Test void malformedCorrelatedReplyCannotBecomeAHeartbeatOrBeRetried()throws Exception {
        try(var f=new Fixture()) {
            var slow=new CompletableFuture<Decoded>();f.link.set((p,r,k,d)->{
                if(!p.equals(f.first()))return slow;
                var value=new TreeMap<>(f.ack(p,r).join().value());value.put("sequence",99L);
                return CompletableFuture.completedFuture(decode(encode("wire","HEARTBEAT_ACK",value),"wire","HEARTBEAT_ACK"));
            });
            try(var round=f.pulse()){assertThrows(IllegalArgumentException.class,round::run);}
            assertEquals(2,f.requests.size());assertTrue(slow.isCancelled());
        }
    }
    @Test void verifiedHigherRejectFencesBeforeQueuedMajorityCanReturn()throws Exception {
        try(var f=new Fixture()) {
            f.link.set((p,r,k,d)->p.equals(f.first())?f.ack(p,r):CompletableFuture.completedFuture(V53ActivationDriverTest.reject(r,"STALE_EPOCH",true,false)));
            try(var round=f.pulse()){assertThrows(IllegalArgumentException.class,round::run);}
            assertThrows(IllegalArgumentException.class,f::guard);
        }
    }
    @Test void foreignHigherRejectCannotChangeRootFence()throws Exception {
        try(var f=new Fixture()) {
            var slow=new CompletableFuture<Decoded>();f.link.set((p,r,k,d)->p.equals(f.first())?
                CompletableFuture.completedFuture(V53ActivationDriverTest.reject(r,"STALE_EPOCH",true,true)):slow);
            try(var round=f.pulse()){assertThrows(IllegalArgumentException.class,round::run);}
            f.guard();assertTrue(slow.isCancelled());
        }
    }
    @Test void lateAuthenticatedHigherReplyStillFencesAfterLocalCompletion()throws Exception {
        try(var f=new Fixture()) {
            var late=new CompletableFuture<Decoded>(){@Override public boolean cancel(boolean interrupt){return false;}};
            var sent=new AtomicReference<Decoded>();f.link.set((p,r,k,d)->{
                if(p.equals(f.first()))return f.ack(p,r);sent.set(r);return late;
            });
            var usage=f.local.budgets.getFirst().usage();
            try(var round=f.pulse()){round.run();}f.guard();
            late.complete(V53ActivationDriverTest.reject(sent.get(),"STALE_EPOCH",true,false));
            assertThrows(IllegalArgumentException.class,f::guard);assertEquals(usage,f.local.budgets.getFirst().usage());
        }
    }
    @Test void closeCancelsAllPendingPeersAndWakesTheRunner()throws Exception {
        try(var f=new Fixture();var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var waiting=new CountDownLatch(2);var pending=Collections.synchronizedList(new ArrayList<CompletableFuture<Decoded>>());
            f.link.set((p,r,k,d)->{var future=new CompletableFuture<Decoded>();pending.add(future);waiting.countDown();return future;});
            var usage=f.local.budgets.getFirst().usage();
            try(var round=f.pulse()) {
                var work=executor.submit(round::run);assertTrue(waiting.await(5,TimeUnit.SECONDS));round.close();
                assertThrows(ExecutionException.class,()->work.get(5,TimeUnit.SECONDS));
            }
            assertTrue(pending.stream().allMatch(CompletableFuture::isCancelled));assertEquals(usage,f.local.budgets.getFirst().usage());
        }
    }
    @Test void idleHigherFenceCancelsPendingPeersWhileWriterIsHeld()throws Exception {
        try(var f=new Fixture();var round=f.pulse()) {
            var waiting=new CountDownLatch(2);var cancelled=new CountDownLatch(2);var pending=new ArrayList<CompletableFuture<Decoded>>();
            var result=new CompletableFuture<Throwable>();
            f.link.set((p,r,k,d)->{
                var future=new CompletableFuture<Decoded>();pending.add(future);waiting.countDown();
                future.whenComplete((reply,error)->{if(future.isCancelled())cancelled.countDown();});return future;
            });
            Thread runner=Thread.ofPlatform().start(()->{try{round.run();result.complete(null);}catch(Throwable error){result.complete(error);}});
            try {
                assertTrue(waiting.await(10,TimeUnit.SECONDS));
                V53MembershipTransportTest.waitFor(()->Arrays.stream(runner.getStackTrace()).anyMatch(frame->
                        frame.getClassName().equals("java.util.concurrent.ArrayBlockingQueue") && frame.getMethodName().equals("poll")));
                synchronized(f.local.owners.getFirst()) {
                    var higher=new TreeMap<>(object(f.requests.getFirst().value().get("ballot")));
                    higher.put("counter",number(higher.get("counter"))+1);f.local.owners.getFirst().observeCurrent(higher);
                    assertTrue(cancelled.await(3,TimeUnit.SECONDS),"idle heartbeat waited for the writer/deadline before cancelling fenced requests");
                }
            }finally{round.close();runner.join(10_000);}
            assertFalse(runner.isAlive());assertNotNull(result.get(1,TimeUnit.SECONDS));
        }
    }
    @Test void replyAfterOriginalDeadlineDoesNotBecomeContact()throws Exception {
        try(var f=new Fixture()) {
            f.link.set((p,r,k,d)->{var answer=f.ack(p,r);f.clock.set(BUDGET);return answer;});
            try(var round=f.pulse()){assertThrows(IllegalArgumentException.class,round::run);}
            assertEquals(1,f.requests.size());
        }
    }
    @Test void capacityFailureBeforeFanoutDoesNotLeakReservationsOrSend()throws Exception {
        try(var f=new Fixture()) {
            // The first peer reservation fits; the second must fail and unwind
            // the partial fanout before any request is sent.
            var budget=f.local.budgets.getFirst();long held=MembershipResources.QUEUE_LIMIT-budget.usage().queued()-200_000;
            var leases=new ArrayList<MembershipResources.Lease>();
            try {
                while(held>0){long bytes=Math.min(held,MembershipResources.Unit.CONTROL.bytes);leases.add(budget.reserve(MembershipResources.Unit.CONTROL,"fill-"+leases.size(),bytes));held-=bytes;}
                var usage=budget.usage();try(var round=f.pulse()){assertThrows(IllegalArgumentException.class,round::run);}
                assertTrue(f.requests.isEmpty());assertEquals(usage,budget.usage());
            }finally{leases.forEach(MembershipResources.Lease::close);}
        }
    }
    @Test void advertisedProgressRemainsAHintWithoutChangingTheOwnedCut()throws Exception {
        try(var f=new Fixture()) {
            var owner=f.local.owners.getFirst();var cut=owner.activationContext().cut;
            var slow=new CompletableFuture<Decoded>();
            f.link.set((p,r,k,d)->{
                if(!p.equals(f.first()))return slow;
                var value=new TreeMap<>(f.ack(p,r).join().value());var ahead=new TreeMap<>(cut);
                ahead.put("index",100L);ahead.put("entry","0".repeat(64));value.put("payload",Map.of("cut",ahead));
                return CompletableFuture.completedFuture(decode(encode("wire","HEARTBEAT_ACK",value),"wire","HEARTBEAT_ACK"));
            });
            try(var round=f.pulse()){assertEquals(100L,round.run().hints().get("node-2").get("index"));}
            assertEquals(cut,owner.activationContext().cut);f.guard();assertTrue(slow.isCancelled());
        }
    }
    @Test void requestEncodingFailureReturnsItsPreallocatedReservation()throws Exception {
        try(var f=new Fixture()) {
            var b=f.local.bound;var tiny=new ReplicationBounds(64,b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                    b.maxRetryAttempts(),b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
            var budget=f.local.budgets.getFirst();var before=budget.usage();
            try(var round=new MembershipHeartbeatRound(f.local.owners.getFirst(),budget,tiny,
                    (p,r,k,d)->{fail("oversized heartbeat must not send");return null;},f::guard,f.clock::get,0,BUDGET)) {
                assertEquals("heartbeat request header capacity",assertThrows(IllegalArgumentException.class,round::run).getMessage());
            }
            assertEquals(before,budget.usage());
        }
    }
    @Test void nativeReadyRoundSamplesWithoutWritingOrReusingContactAsReadiness()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            assertThrows(IllegalArgumentException.class,round::heartbeat);
            var barrier=round.start();var files=new ArrayList<Map<String,String>>();
            for(var target:n.f.request.targets())files.add(V53ReplayFilesTest.files(target.replicaDirectory()));
            n.f.snapshot("heartbeat-before");n.events.add(Map.of("node","node-1","event","HEARTBEAT_BEGIN"));
            n.beforeSend.set(request->{if(request.kind().equals("HEARTBEAT"))n.events.add(Map.of("node","node-1","event","HEARTBEAT_SEND",
                    "bytes",Base64.getEncoder().encodeToString(request.bytes())));});
            var contact=round.heartbeat();assertTrue(contact.responding().size()>=2);
            var hints=contact.hints().entrySet().stream().sorted(Map.Entry.comparingByKey())
                    .map(v->Map.of("node",v.getKey(),"cut",v.getValue())).toList();
            n.events.add(Map.of("node","node-1","event","HEARTBEAT_CONTACT","responding",contact.responding().stream().sorted().toList(),"hints",hints));
            n.f.snapshot("heartbeat-after");
            for(int i=0;i<files.size();i++)assertEquals(files.get(i),V53ReplayFilesTest.files(n.f.request.targets().get(i).replicaDirectory()));
            assertArrayEquals(barrier.bytes(),round.readiness().bytes());
            assertEquals("PUBLISH_ACK",round.submit("DATA",helper.data(n)).kind());
            assertArrayEquals(barrier.bytes(),round.readiness().bytes());
            var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);n.owners.getFirst().observeCurrent(higher);
            assertThrows(IllegalArgumentException.class,round::readiness);assertEquals(MembershipRoundDriver.State.FAILED,round.state());
            Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","slots",2,"network",true,"autonomous",false),4096));
            Files.write(n.f.raw.resolve("round-result.json"),canonical(Map.of("status","PASS","mode","stable","internalReady",true,"publicReady",false),4096));
        }
    }
}
