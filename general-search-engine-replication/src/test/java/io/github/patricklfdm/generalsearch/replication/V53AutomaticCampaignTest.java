package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53AutomaticOwnerTest.*;

/** Conditional session tests. They qualify fresh-round orchestration, never
 * ballots or publications; native protocol evidence is qualified separately. */
class V53AutomaticCampaignTest {
    static MembershipCampaignLost lost(){return new MembershipCampaignLost(MembershipCampaignLost.Reason.HIGHER_BALLOT,"typed higher ballot");}
    static void raise(Throwable error)throws IOException {
        if(error instanceof IOException io)throw io;if(error instanceof RuntimeException runtime)throw runtime;if(error instanceof Error fatal)throw fatal;
    }
    static final class Probe implements MembershipAutomaticOwner.Session {
        final Decoded answer;
        final List<String> calls=Collections.synchronizedList(new ArrayList<>());
        final CountDownLatch entered=new CountDownLatch(1);
        final AtomicInteger closes=new AtomicInteger();
        volatile Throwable startFailure,submitFailure,heartbeatFailure;
        volatile CountDownLatch submitGate;
        volatile Runnable onClose=()->{};
        volatile int closeFailures;
        long original;
        Probe()throws Exception{answer=decode(V53FormatTest.bytes(V53FormatTest.sample("wire","PUBLISH_ACK")),"wire","PUBLISH_ACK");}
        public Decoded start(long began)throws IOException{original=began;calls.add("start");raise(startFailure);return answer;}
        public void idle(){}
        public MembershipHeartbeatRound.Contact heartbeat()throws IOException{calls.add("heartbeat");raise(heartbeatFailure);return new MembershipHeartbeatRound.Contact(Set.of("node-1","node-2"),Map.of());}
        public Decoded readiness(){calls.add("guard");return answer;}
        public Decoded submit(String kind,byte[] input)throws IOException{calls.add(kind);entered.countDown();if(submitGate!=null)await(submitGate);raise(submitFailure);return answer;}
        public void close()throws IOException{if(closes.incrementAndGet()<=closeFailures)throw new IOException("cleanup rejected");onClose.run();if(submitGate!=null)submitGate.countDown();}
    }
    static final class Fixture {
        final MembershipResources resources=new MembershipResources(512*MembershipResources.MIB);
        final AtomicLong clock=new AtomicLong(ms(100));
        MembershipAutomaticOwner owner(Probe first,MembershipAutomaticOwner.Factory next,int attempts) {
            return new MembershipAutomaticOwner(first,next,attempts,resources,bound(4),POLICY,clock::get,ms(100));
        }
    }
    @Test void startupLossDrainsBeforeOpeningFreshRoundUnderOriginalDeadline()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.startFailure=lost();
        var factoryEntered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var owner=f.owner(first,()->{assertTrue(first.closes.get()>0);factoryEntered.countDown();await(release);f.clock.set(ms(130));return second;},2)) {
            var start=owner.start();await(factoryEntered);assertEquals(MembershipAutomaticOwner.State.RESTARTING,owner.state());
            assertFalse(start.isDone());assertThrows(IllegalArgumentException.class,owner::readiness);
            release.countDown();assertSame(second.answer,start.await(5,TimeUnit.SECONDS));
            assertEquals(ms(100),first.original);assertEquals(first.original,second.original);assertEquals(2,owner.rounds());
            assertEquals(List.of(MembershipCampaignLost.Reason.HIGHER_BALLOT),owner.losses());
        }finally{release.countDown();}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void admittedMutationAndOldQueueAreRejectedNotReplayedOnNewRound()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.submitGate=new CountDownLatch(1);first.submitFailure=lost();
        try(var owner=f.owner(first,()->second,2)) {
            assertSame(first.answer,owner.start().await(5,TimeUnit.SECONDS));
            var mutation=owner.submit("DATA",new byte[]{1});await(first.entered);var queued=owner.readiness();first.submitGate.countDown();
            assertSame(first.submitFailure,assertThrows(ExecutionException.class,()->mutation.await(5,TimeUnit.SECONDS)).getCause());
            assertSame(first.submitFailure,assertThrows(ExecutionException.class,()->queued.await(5,TimeUnit.SECONDS)).getCause());
            V53MembershipTransportTest.waitFor(()->owner.rounds()==2 && owner.state()==MembershipAutomaticOwner.State.READY);
            assertSame(second.answer,owner.readiness().await(5,TimeUnit.SECONDS));
            assertEquals(List.of("start","DATA"),first.calls);assertEquals(List.of("start","guard"),second.calls);assertEquals(0,owner.pending());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void contactLossCanRestartButRetainsTheOriginalBudget()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.heartbeatFailure=new MembershipCampaignLost(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,"contact lost");
        try(var owner=f.owner(first,()->second,2)) {
            owner.start().await(5,TimeUnit.SECONDS);f.clock.set(ms(110));
            V53MembershipTransportTest.waitFor(()->owner.rounds()==2 && owner.state()==MembershipAutomaticOwner.State.READY);
            assertEquals(first.original,second.original);assertEquals(List.of("start","heartbeat"),first.calls);
            f.clock.set(ms(200));V53MembershipTransportTest.waitFor(()->owner.state()==MembershipAutomaticOwner.State.FAILED);
            assertEquals("automatic owner original deadline",owner.failure().orElseThrow().getMessage());assertEquals(2,owner.rounds());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void arbitraryMessagesNestedCausesAndIntegrityFailuresCannotAuthorizeRestart()throws Exception {
        for(Throwable error:List.of(new IOException("higher ballot observed; fresh campaign required"),new IOException("storage",lost()),
                new IllegalArgumentException("activation view changed"),new IllegalStateException("corrupt original"))) {
            var f=new Fixture();var first=new Probe();first.startFailure=error;var opens=new AtomicInteger();
            try(var owner=f.owner(first,()->{opens.incrementAndGet();return new ProbeUnchecked().value;},3)) {
                assertSame(error,assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause());
                assertEquals(0,opens.get());assertTrue(owner.losses().isEmpty());assertEquals(1,owner.rounds());
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
    static final class ProbeUnchecked {
        final Probe value;
        ProbeUnchecked(){try{value=new Probe();}catch(Exception error){throw new IllegalStateException(error);}}
    }
    @Test void cleanupFailureStopsRestartEvenIfFinalCleanupLaterSucceeds()throws Exception {
        var f=new Fixture();var first=new Probe();first.startFailure=lost();first.closeFailures=1;var opens=new AtomicInteger();
        try(var owner=f.owner(first,()->{opens.incrementAndGet();return new ProbeUnchecked().value;},2)) {
            var error=assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause();
            assertSame(first.startFailure,error);assertEquals(1,error.getSuppressed().length);assertEquals(0,opens.get());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void existingSuppressedFailureCannotBeRetried()throws Exception {
        var f=new Fixture();var first=new Probe();var error=lost();error.addSuppressed(new IOException("prior drain failed"));first.startFailure=error;
        try(var owner=f.owner(first,()->{fail("no fresh round after incomplete cleanup");return null;},2)) {
            assertSame(error,assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause());assertEquals(1,owner.rounds());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void allNewRoundsAreFiniteAndIndependentlyRecorded()throws Exception {
        var f=new Fixture();var probes=new ArrayList<Probe>();for(int i=0;i<3;i++){var p=new Probe();p.startFailure=lost();probes.add(p);}
        var next=new AtomicInteger(1);
        try(var owner=f.owner(probes.getFirst(),()->probes.get(next.getAndIncrement()),3)) {
            assertSame(probes.getLast().startFailure,assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause());
            assertEquals(3,owner.rounds());assertEquals(3,owner.losses().size());assertEquals(3,next.get());
            assertTrue(probes.stream().allMatch(p->p.original==ms(100)));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void expiredCleanupBudgetPreventsOpeningAnotherRound()throws Exception {
        var f=new Fixture();var first=new Probe();first.startFailure=lost();first.onClose=()->f.clock.set(ms(200));
        try(var owner=f.owner(first,()->{fail("original deadline expired");return null;},2)) {
            assertEquals("automatic owner original deadline",assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause().getMessage());
            assertEquals(1,owner.rounds());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void closeDuringFactoryDrainsLateSessionWithoutStartingIt()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.startFailure=lost();
        var opening=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var owner=f.owner(first,()->{opening.countDown();await(release);return second;},2);var workers=Executors.newVirtualThreadPerTaskExecutor()) {
            var start=owner.start();await(opening);var closing=workers.submit(()->{owner.close();return null;});
            try{V53MembershipTransportTest.waitFor(()->owner.state()==MembershipAutomaticOwner.State.CLOSED);release.countDown();closing.get(5,TimeUnit.SECONDS);}
            finally{release.countDown();}
            assertThrows(ExecutionException.class,()->start.await(5,TimeUnit.SECONDS));assertTrue(second.calls.isEmpty());assertTrue(second.closes.get()>0);
        }finally{release.countDown();}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void closedSessionCannotBeReusedAsAnotherCampaign()throws Exception {
        var f=new Fixture();var first=new Probe();first.startFailure=lost();
        try(var owner=f.owner(first,()->first,2)) {
            assertEquals("automatic owner must open a fresh session",assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause().getMessage());
            assertEquals(List.of("start"),first.calls);assertEquals(1,owner.rounds());
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
