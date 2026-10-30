package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53HeartbeatTest.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ElectionWaitTest {
    @TempDir Path temp;
    static long millis(long n){return TimeUnit.MILLISECONDS.toNanos(n);}
    static final AutomaticLeadershipPolicy POLICY=new AutomaticLeadershipPolicy(5,15,25,20);
    final class Fixture implements AutoCloseable {
        final AtomicLong clock=new AtomicLong();final V53ActivationDriverTest.Local l;
        Fixture()throws Exception{var h=new V53ActivationDriverTest();h.temp=temp;l=h.local(clock,1000);}
        MembershipElectionWait waitFor(long budget) {
            return new MembershipElectionWait(l.owners.getFirst(),l.endpoints.getFirst(),l.budgets.getFirst(),POLICY,clock::get,(a,b)->a,0,millis(budget));
        }
        void heartbeat(long counter,boolean active)throws Exception{l.endpoints.getFirst().handle(l.group.identities.get(1),request(l,counter,active));}
        @Override public void close()throws Exception{l.close();}
    }
    static void idle(Thread worker)throws Exception {
        V53MembershipTransportTest.waitFor(()->Arrays.stream(worker.getStackTrace()).anyMatch(v->
                v.getClassName().equals("java.util.concurrent.ArrayBlockingQueue") && v.getMethodName().equals("poll")));
    }
    static Thread run(MembershipElectionWait wait,CompletableFuture<MembershipGrantJournal.DiscoveryState> result) {
        return Thread.ofPlatform().start(()->{try{result.complete(wait.await());}catch(Throwable error){result.completeExceptionally(error);}});
    }
    @Test void delayReturnsOnlyRevalidatedOriginalStateWithoutAllocatingGrant()throws Exception {
        try(var f=new Fixture();var wait=f.waitFor(100)) {
            var before=files(f.l);var state=f.l.owners.getFirst().discoveryState(f.l.budgets.getFirst());var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();
            Thread worker=run(wait,result);
            try{idle(worker);f.clock.set(millis(14));assertFalse(result.isDone());f.clock.set(millis(15));assertEquals(state,result.get(5,TimeUnit.SECONDS));}
            finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());assertEquals(before,files(f.l));assertThrows(IllegalArgumentException.class,wait::await);
        }
    }
    @Test void oldAcceptedArrivalDoesNotAcquireANewDeadlineAtPollTime()throws Exception {
        try(var f=new Fixture();var wait=f.waitFor(100)) {
            f.heartbeat(100,true);f.clock.set(millis(20));var before=files(f.l);
            var state=wait.await();assertEquals(100L,state.ballot().get("counter"));assertEquals(before,files(f.l));
        }
    }
    @Test void recentAcceptedContactPostponesOnceAndCannotOutliveParentBudget()throws Exception {
        try(var f=new Fixture();var wait=f.waitFor(20)) {
            f.clock.set(millis(10));f.heartbeat(100,true);
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try {
                idle(worker);assertFalse(result.isDone());f.clock.set(millis(20));
                var error=assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS));
                assertEquals("election wait closed/original deadline",error.getCause().getMessage());
            }finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());
        }
    }
    @Test void freshRetryDoesNotConsumeExpiredContactAsAnImmediateElection()throws Exception {
        try(var f=new Fixture();var wait=new MembershipElectionWait(f.l.owners.getFirst(),f.l.endpoints.getFirst(),f.l.budgets.getFirst(),
                POLICY,f.clock::get,(a,b)->a,0,millis(100),true)) {
            f.heartbeat(100,true);f.clock.set(millis(20));var before=files(f.l);
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try {
                idle(worker);f.clock.set(millis(34));assertFalse(result.isDone());
                f.clock.set(millis(35));assertEquals(100L,result.get(5,TimeUnit.SECONDS).ballot().get("counter"));
            }finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());assertEquals(before,files(f.l));
        }
    }
    @Test void freshRetryNewContactUsesOriginalArrivalAndOriginalParentDeadline()throws Exception {
        try(var f=new Fixture();var wait=new MembershipElectionWait(f.l.owners.getFirst(),f.l.endpoints.getFirst(),f.l.budgets.getFirst(),
                POLICY,f.clock::get,(a,b)->a,0,millis(40),true)) {
            f.heartbeat(100,true);f.clock.set(millis(20));
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try {
                idle(worker);f.clock.set(millis(30));f.heartbeat(100,true);
                V53MembershipTransportTest.waitFor(()->f.l.endpoints.getFirst().heartbeatContact().orElseThrow().receivedNanos()==millis(30));
                f.clock.set(millis(40));assertEquals("election wait closed/original deadline",assertThrows(ExecutionException.class,
                        ()->result.get(5,TimeUnit.SECONDS)).getCause().getMessage());
            }finally{wait.close();worker.join(5000);}
        }
    }
    @Test void repeatedInactiveSameBallotDoesNotKeepAnotherCandidateWaiting()throws Exception {
        try(var f=new Fixture();var wait=f.waitFor(100)) {
            f.heartbeat(100,false);var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try{idle(worker);f.clock.set(millis(10));f.heartbeat(100,false);f.clock.set(millis(15));assertEquals(100L,result.get(5,TimeUnit.SECONDS).ballot().get("counter"));}
            finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());
        }
    }
    @Test void closeWakesIdleWaitWithoutAcquiringBusyWriter()throws Exception {
        try(var f=new Fixture();var wait=f.waitFor(100)) {
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try {
                idle(worker);synchronized(f.l.owners.getFirst()) {
                    wait.close();assertThrows(ExecutionException.class,()->result.get(2,TimeUnit.SECONDS));
                }
            }finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());
        }
    }
    @Test void dueWaitChecksOriginalStorageBeforeReturningCandidate()throws Exception {
        try(var f=new Fixture();var wait=f.waitFor(100)) {
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            Path path=f.l.group.fixture.request.targets().getFirst().replicaDirectory().resolve("selector.gsr");byte[] before=Files.readAllBytes(path);
            try {
                idle(worker);byte[] bad=before.clone();bad[bad.length-1]^=1;Files.write(path,bad);f.clock.set(millis(15));
                assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS));
            }finally{Files.write(path,before);wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());
        }
    }
    @Test void jitterOutsideFrozenPolicyFailsWithoutGrant()throws Exception {
        try(var f=new Fixture()) {
            var before=files(f.l);
            for(boolean below:List.of(false,true))try(var wait=new MembershipElectionWait(f.l.owners.getFirst(),f.l.endpoints.getFirst(),f.l.budgets.getFirst(),
                    POLICY,f.clock::get,(a,b)->below?a-1:b+1,0,millis(100))) {
                assertEquals("election jitter outside policy",assertThrows(IllegalArgumentException.class,wait::await).getMessage());
            }
            assertEquals(before,files(f.l));
        }
    }
    @Test void nativeAutomaticEntryStillDiscoversAndPublishesFreshBarrierBeforeData()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            var sent=Collections.synchronizedList(new ArrayList<String>());n.beforeSend.set(r->sent.add(r.kind()));
            assertThrows(IllegalArgumentException.class,round::readiness);
            var barrier=round.startAutomatic(POLICY,(a,b)->a);assertEquals(MembershipRoundDriver.State.READY,round.state());
            assertEquals(List.of("STATUS_PROBE","STATUS_PROBE","PREPARE"),sent.subList(0,3));assertArrayEquals(barrier.bytes(),round.readiness().bytes());
            assertEquals("PUBLISH_ACK",round.submit("DATA",helper.data(n)).kind());assertArrayEquals(barrier.bytes(),round.readiness().bytes());
            Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","slots",2,"network",true,"autonomous",false),4096));
            Files.write(n.f.raw.resolve("round-result.json"),canonical(Map.of("status","PASS","mode","stable","internalReady",true,"publicReady",false),4096));
        }
    }
    @Test void closingAutomaticRoundDuringWaitCannotAllocateOrSend()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            var result=CompletableFuture.runAsync(()->assertThrows(Exception.class,()->round.startAutomatic(AutomaticLeadershipPolicy.forBounds(n.bounds))));
            V53MembershipTransportTest.waitFor(()->round.state()==MembershipRoundDriver.State.WAITING);
            round.close();result.get(10,TimeUnit.SECONDS);assertEquals(MembershipRoundDriver.State.CLOSED,round.state());
            assertTrue(n.wire.isEmpty());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            assertThrows(IllegalArgumentException.class,round::readiness);
        }
    }
}
