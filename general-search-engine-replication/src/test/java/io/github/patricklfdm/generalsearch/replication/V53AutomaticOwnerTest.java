package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Scripted session tests qualify scheduling/lifetimes only. The final test
 * uses native bootstrap/storage/TCP, closing before any protocol request. */
class V53AutomaticOwnerTest {
    @TempDir Path temp;
    static final AutomaticLeadershipPolicy POLICY=new AutomaticLeadershipPolicy(10,30,50,40);
    static long ms(long n){return TimeUnit.MILLISECONDS.toNanos(n);}
    static void await(CountDownLatch latch)throws IOException {
        try{if(!latch.await(5,TimeUnit.SECONDS))throw new IOException("test latch deadline");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
    }
    static ReplicationBounds bound(int pending) {
        var b=ReplicationBounds.defaults();return new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),pending,
            b.maxRetryAttempts(),b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
    }
    final class Script implements MembershipAutomaticOwner.Session {
        final AtomicLong clock=new AtomicLong(ms(100));
        final List<String> calls=Collections.synchronizedList(new ArrayList<>());
        final MembershipResources resources=new MembershipResources(512*MembershipResources.MIB);
        final Decoded answer=decode(V53FormatTest.bytes(V53FormatTest.sample("wire","PUBLISH_ACK")),"wire","PUBLISH_ACK");
        final AtomicBoolean closed=new AtomicBoolean(),stale=new AtomicBoolean();
        volatile CountDownLatch holdStart,holdSubmit,holdHeartbeat;
        final CountDownLatch enteredSubmit=new CountDownLatch(1),enteredHeartbeat=new CountDownLatch(1);
        volatile IOException submitFailure,heartbeatFailure;
        volatile boolean closeFailure,ignoreClose;
        volatile byte[] submitted;
        long originalStart;
        Script()throws Exception{}
        public Decoded start(long began)throws IOException {originalStart=began;calls.add("start");if(holdStart!=null)await(holdStart);return answer;}
        public void idle(){if(stale.get())throw new IllegalArgumentException("higher original ballot");}
        public void heartbeat()throws IOException {calls.add("heartbeat");enteredHeartbeat.countDown();if(holdHeartbeat!=null)await(holdHeartbeat);if(heartbeatFailure!=null)throw heartbeatFailure;}
        public Decoded readiness(){calls.add("guard");idle();return answer;}
        public Decoded submit(String kind,byte[] bytes)throws IOException {
            calls.add(kind);enteredSubmit.countDown();if(holdSubmit!=null)await(holdSubmit);submitted=bytes.clone();
            if(submitFailure!=null)throw submitFailure;return answer;
        }
        public void close()throws IOException {
            if(closeFailure)throw new IOException("script cleanup blocked");closed.set(true);
            if(!ignoreClose)for(var latch:Arrays.asList(holdStart,holdSubmit,holdHeartbeat))if(latch!=null)latch.countDown();
        }
        MembershipAutomaticOwner owner(int pending,long budget){return new MembershipAutomaticOwner(this,resources,bound(pending),POLICY,clock::get,ms(budget));}
    }
    @Test void serialQueueCopiesInputsAndCountsExecutingCallAgainstCapacity()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);
        try(var owner=s.owner(2,100)) {
            assertSame(s.answer,owner.start().await(5,TimeUnit.SECONDS));assertEquals(ms(100),s.originalStart);
            byte[] input={1,2,3};var first=owner.submit("DATA",input);await(s.enteredSubmit);input[0]=9;
            var guard=owner.readiness();assertEquals(2,owner.pending());
            assertThrows(IllegalArgumentException.class,owner::readiness);assertFalse(first.isDone());assertFalse(guard.isDone());
            s.holdSubmit.countDown();assertSame(s.answer,first.await(5,TimeUnit.SECONDS));assertSame(s.answer,guard.await(5,TimeUnit.SECONDS));
            assertArrayEquals(new byte[]{1,2,3},s.submitted);assertEquals(List.of("start","DATA","guard"),s.calls);
            assertThrows(IllegalArgumentException.class,owner::start);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void dueHeartbeatRunsBeforeQueuedWorkWithoutCatchupBurst()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);s.holdHeartbeat=new CountDownLatch(1);
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);var data=owner.submit("DATA",new byte[]{1});await(s.enteredSubmit);
            var guard=owner.readiness();s.clock.set(ms(110));s.holdSubmit.countDown();data.await(5,TimeUnit.SECONDS);await(s.enteredHeartbeat);
            assertFalse(guard.isDone());s.clock.set(ms(150));s.holdHeartbeat.countDown();guard.await(5,TimeUnit.SECONDS);
            assertEquals(List.of("start","DATA","heartbeat","guard"),s.calls);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void timerNeverRenewsOriginalLifetimeAfterHeartbeat()throws Exception {
        var s=new Script();
        try(var owner=s.owner(2,30)) {
            owner.start().await(5,TimeUnit.SECONDS);s.clock.set(ms(110));await(s.enteredHeartbeat);
            s.clock.set(ms(130));V53MembershipTransportTest.waitFor(()->owner.state()==MembershipAutomaticOwner.State.FAILED);
            assertEquals("automatic owner original deadline",owner.failure().orElseThrow().getMessage());
            assertEquals(ms(100),s.originalStart);assertThrows(IllegalArgumentException.class,owner::readiness);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void mutationFailureRejectsQueueAndNeverAutomaticallyReplays()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);s.submitFailure=new IOException("indeterminate publication");
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);var data=owner.submit("DATA",new byte[]{1});await(s.enteredSubmit);var guard=owner.readiness();
            s.holdSubmit.countDown();assertSame(s.submitFailure,assertThrows(ExecutionException.class,()->data.await(5,TimeUnit.SECONDS)).getCause());
            assertSame(s.submitFailure,assertThrows(ExecutionException.class,()->guard.await(5,TimeUnit.SECONDS)).getCause());
            assertEquals(List.of("start","DATA"),s.calls);assertEquals(0,owner.pending());
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void idleHigherFenceStopsWithoutGivingOutCachedReadiness()throws Exception {
        var s=new Script();
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);s.stale.set(true);
            V53MembershipTransportTest.waitFor(()->owner.state()==MembershipAutomaticOwner.State.FAILED);
            assertEquals("higher original ballot",owner.failure().orElseThrow().getMessage());assertThrows(IllegalArgumentException.class,owner::readiness);
            assertEquals(List.of("start"),s.calls);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void heartbeatFailureEndsOneCampaignInsteadOfStartingAnother()throws Exception {
        var s=new Script();s.heartbeatFailure=new IOException("sample exhausted");
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);s.clock.set(ms(110));
            V53MembershipTransportTest.waitFor(()->owner.state()==MembershipAutomaticOwner.State.FAILED);
            assertSame(s.heartbeatFailure,owner.failure().orElseThrow());assertEquals(List.of("start","heartbeat"),s.calls);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void capacityFailureReturnsWaiterAndInvalidInputDoesNotKillOwner()throws Exception {
        var s=new Script();var held=new ArrayList<MembershipResources.Lease>();
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);long left=MembershipResources.QUEUE_LIMIT-s.resources.usage().queued();
            while(left>0){long size=Math.min(left,MembershipResources.Unit.CONTROL.bytes);held.add(s.resources.reserve(MembershipResources.Unit.CONTROL,"fill-"+held.size(),size));left-=size;}
            var before=s.resources.usage();assertThrows(IllegalArgumentException.class,owner::readiness);assertEquals(before,s.resources.usage());
            assertEquals(0,owner.pending());held.forEach(MembershipResources.Lease::close);held.clear();
            assertThrows(IllegalArgumentException.class,()->owner.submit("BARRIER",new byte[]{1}));assertThrows(IllegalArgumentException.class,()->owner.submit("FINAL",new byte[0]));
            assertSame(s.answer,owner.readiness().await(5,TimeUnit.SECONDS));
        }finally{held.forEach(MembershipResources.Lease::close);}
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void waitingTimeoutDoesNotCancelOrRetryAdmittedCall()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);var call=owner.submit("DATA",new byte[]{1});await(s.enteredSubmit);
            assertThrows(TimeoutException.class,()->call.await(1,TimeUnit.MILLISECONDS));assertEquals(1,owner.pending());
            s.holdSubmit.countDown();assertSame(s.answer,call.await(5,TimeUnit.SECONDS));assertEquals(List.of("start","DATA"),s.calls);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void maximumInputIsAccountedBeforeCloningAndReleasedAfterUse()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);
        try(var owner=s.owner(2,100)) {
            owner.start().await(5,TimeUnit.SECONDS);long before=s.resources.usage().queued();
            byte[] input=new byte[FRAME];input[FRAME-1]=12;var call=owner.submit("DATA",input);await(s.enteredSubmit);
            assertEquals(before+FRAME,s.resources.usage().queued());input[FRAME-1]=99;
            s.holdSubmit.countDown();call.await(5,TimeUnit.SECONDS);
            assertEquals(12,s.submitted[FRAME-1]);V53MembershipTransportTest.waitFor(()->owner.pending()==0);
            assertEquals(before,s.resources.usage().queued());
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void closeRejectsQueuedAndActiveCallsAndDrainsAllReservations()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);
        try(var owner=s.owner(2,100)) {
            assertThrows(IllegalArgumentException.class,owner::readiness);owner.start().await(5,TimeUnit.SECONDS);
            var active=owner.submit("DATA",new byte[]{1});await(s.enteredSubmit);var queued=owner.readiness();
            owner.close();assertThrows(ExecutionException.class,()->active.await(5,TimeUnit.SECONDS));assertThrows(ExecutionException.class,()->queued.await(5,TimeUnit.SECONDS));
            assertEquals(0,owner.pending());assertEquals(MembershipAutomaticOwner.State.CLOSED,owner.state());assertEquals(List.of("start","DATA"),s.calls);
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void cleanupFailureRetainsOwnerUntilExplicitSuccessfulDrain()throws Exception {
        var s=new Script();s.closeFailure=true;
        var owner=s.owner(2,100);
        assertThrows(IOException.class,owner::close);assertEquals(1,s.resources.usage().leases());
        assertThrows(IllegalArgumentException.class,()->s.owner(2,100));s.closeFailure=false;owner.close();
        assertEquals(0,s.resources.usage().leases());assertThrows(IllegalArgumentException.class,owner::start);
    }
    @Test void closeDrainTimeoutKeepsExecutingInputAndOwnerUntilWorkerEnds()throws Exception {
        var s=new Script();s.holdSubmit=new CountDownLatch(1);s.ignoreClose=true;var b=bound(2);
        var shortClose=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
            b.maxRetryAttempts(),100,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        var owner=new MembershipAutomaticOwner(s,s.resources,shortClose,POLICY,s.clock::get,ms(100));
        try {
            owner.start().await(5,TimeUnit.SECONDS);var call=owner.submit("DATA",new byte[]{1});await(s.enteredSubmit);
            assertEquals("automatic owner close drain deadline",assertThrows(IOException.class,owner::close).getMessage());
            assertEquals(3,s.resources.usage().leases());assertEquals(1,owner.pending());assertFalse(call.isDone());
            assertThrows(IllegalArgumentException.class,()->s.owner(2,100));s.holdSubmit.countDown();
            assertThrows(ExecutionException.class,()->call.await(5,TimeUnit.SECONDS));
            V53MembershipTransportTest.waitFor(()->s.resources.usage().leases()==0);owner.close();
        }finally{s.holdSubmit.countDown();owner.close();}
    }
    @Test void closingDuringActivationCannotPublishReadiness()throws Exception {
        var s=new Script();s.holdStart=new CountDownLatch(1);
        try(var owner=s.owner(2,100)) {
            var start=owner.start();owner.close();assertThrows(ExecutionException.class,()->start.await(5,TimeUnit.SECONDS));
            assertThrows(IllegalArgumentException.class,owner::readiness);assertEquals(MembershipAutomaticOwner.State.CLOSED,owner.state());
        }
        assertEquals(0,s.resources.usage().leases());
    }
    @Test void nativeOwnedAutomaticWaitCloseSendsNothingAndCannotGrant()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE);
            var owner=round.automaticOwner(AutomaticLeadershipPolicy.forBounds(n.bounds))) {
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            var start=owner.start();V53MembershipTransportTest.waitFor(()->round.state()==MembershipRoundDriver.State.WAITING);
            owner.close();assertThrows(ExecutionException.class,()->start.await(5,TimeUnit.SECONDS));
            assertEquals(MembershipRoundDriver.State.CLOSED,round.state());assertTrue(n.wire.isEmpty());
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
        }
    }
}
