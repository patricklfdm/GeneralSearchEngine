package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.Function;
import org.junit.jupiter.api.Test;

/** Deterministic ownership/scheduling kernel tests, not physical/public read evidence. */
class V52ReadQueueTest {
    static final ReplicaReadOptions STALE=new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,Optional.empty(),0);
    static final ReplicaReadOptions STRONG=new ReplicaReadOptions(ReplicaReadPolicy.LEADER_STRONG,Optional.empty(),0);
    static final class Tasks implements Executor {
        final Queue<Runnable> pending=new ConcurrentLinkedQueue<>();
        boolean reject;
        public void execute(Runnable task) {if(reject)throw new RejectedExecutionException();pending.add(task);}
        void drain() {for(int i=0;!pending.isEmpty();i++){assertTrue(i<1000,"unbounded redispatch");pending.remove().run();}}
    }
    static final class Fixture {
        final Object lock=new Object();
        final AtomicLong now=new AtomicLong();
        final Tasks app=new Tasks(), completions=new Tasks();
        final LinkedHashMap<Runnable,Long> alarms=new LinkedHashMap<>();
        final Semaphore permits;
        final AutomaticReadQueue<Integer,String> queue;
        AutomaticReadCut cut=new AutomaticReadCut(new ReplicationGroupId(UUID.randomUUID()),UUID.randomUUID(),"ab".repeat(32),0,7,0);
        AutomaticReplicationException.Reason rejection;
        Runnable captureHook=()->{}, registerHook=()->{};
        Fixture(int bound) {
            permits=new Semaphore(bound);
            queue=new AutomaticReadQueue<>(lock,cut,new AutomaticReadQueue.Access<>() {
                public void check(ReplicaReadOptions options,long epoch,boolean barrierReady) {if(rejection!=null)throw failure(rejection);}
                public long publishedIndex() {return cut.index();}
                public AutomaticReadCut capture(ReplicaReadOptions options,long epoch,long index) {
                    assertTrue(Thread.holdsLock(lock));captureHook.run();
                    if(options.policy()==ReplicaReadPolicy.LEADER_STRONG&&(epoch!=4||index!=cut.index()))throw failure(STALE_EPOCH);
                    return cut;
                }
                public <R> R read(AutomaticReadCut captured,Function<ReplicaReadView<Integer,String>,R> action) {
                    assertFalse(Thread.holdsLock(lock));assertEquals(cut,captured);
                    return action.apply(null); // lifetime/query delegation has separate actual-engine tests
                }
            },permits,bound,now::get,(deadline,task)->{
                alarms.put(task,deadline);registerHook.run();return ()->alarms.remove(task);
            },app,completions);
        }
        ReplicaReadOptions minimum(long index,int wait) {
            return new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,
                    Optional.of(new ReplicaReadToken(1,cut.group(),cut.history(),cut.manifest(),index)),wait);
        }
        void publish(long index) {cut=new AutomaticReadCut(cut.group(),cut.history(),cut.manifest(),index,cut.sequence(),cut.generation());queue.changed();}
        void expire(long time) {
            now.set(time);
            for(var task:List.copyOf(alarms.keySet()))if(alarms.containsKey(task)&&alarms.get(task)<=time)task.run();
        }
        void drain() {app.drain();completions.drain();}
    }
    static AutomaticReplicationException failure(AutomaticReplicationException.Reason reason) {
        return new AutomaticReplicationException(reason,AutomaticReplicationException.Outcome.NOT_APPLICABLE,Optional.empty(),reason.name());
    }
    static Throwable cause(CompletableFuture<?> future) {return assertThrows(CompletionException.class,future::join).getCause();}
    static void reason(AutomaticReplicationException.Reason reason,CompletableFuture<?> future) {
        var error=assertInstanceOf(AutomaticReplicationException.class,cause(future));assertEquals(reason,error.reason());
        assertEquals(AutomaticReplicationException.Outcome.NOT_APPLICABLE,error.outcome());
    }
    static void await(CountDownLatch latch) {
        try {assertTrue(latch.await(5,TimeUnit.SECONDS));}catch(InterruptedException e){Thread.currentThread().interrupt();throw new AssertionError(e);}
    }

    @Test void all64WaitersLeaveAnOldApiSlotAndNoApplicationTasksUntilPublication() {
        var f=new Fixture(65);var calls=new ArrayList<Integer>();var futures=new ArrayList<CompletableFuture<?>>();
        for(int i=0;i<64;i++){int n=i;futures.add(f.queue.submit(f.minimum(Long.MAX_VALUE,60000),v->{calls.add(n);return n;},100).future());}
        assertEquals(64,f.queue.counts().owned());assertEquals(64,f.alarms.size());assertEquals(0,f.app.pending.size());
        assertTrue(f.permits.tryAcquire(),"legacy API keeps its reserved admission slot");assertEquals(0,f.permits.availablePermits());
        reason(CAPACITY_EXCEEDED,f.queue.submit(STALE,v->0,100).future());f.permits.release();
        f.publish(Long.MAX_VALUE);for(int i=0;i<100;i++)f.queue.changed();
        assertEquals(1,f.app.pending.size());f.app.drain();
        assertEquals(java.util.stream.IntStream.range(0,64).boxed().toList(),calls);
        assertEquals(0,f.alarms.size());assertEquals(64,f.queue.counts().settling());
        reason(CAPACITY_EXCEEDED,f.queue.submit(STALE,v->0,100).future());
        f.completions.drain();assertTrue(futures.stream().allMatch(CompletableFuture::isDone));
        assertEquals(65,f.permits.availablePermits());assertEquals(0,f.queue.counts().owned());assertEquals(64,f.queue.counts().highWater());
    }

    @Test void anOlderUnsatisfiedMinimumDoesNotBlockEligibleFifo() {
        var f=new Fixture(5);var calls=new ArrayList<Integer>();
        var lag=f.queue.submit(f.minimum(9,10),v->{calls.add(1);return 1;},100);
        f.queue.submit(STALE,v->{calls.add(2);return 2;},100);
        f.queue.submit(f.minimum(0,10),v->{calls.add(3);return 3;},100);
        f.drain();assertEquals(List.of(2,3),calls);assertFalse(lag.future().isDone());assertEquals(1,f.alarms.size());
        f.publish(9);f.drain();assertEquals(List.of(2,3,1),calls);assertEquals(9,lag.future().join().progress().index());
        assertEquals(7,lag.future().join().applicationSequence());
    }

    @Test void identityAndStatePrecedeCapacityAndZeroWaitNeverWaitsForProgress() {
        var f=new Fixture(2);f.queue.submit(f.minimum(100,10),v->0,100);
        var bad=new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.of(new ReplicaReadToken(1,
                f.cut.group(),UUID.randomUUID(),f.cut.manifest(),0)),1);
        assertEquals(ReplicaReadException.Reason.INCOMPATIBLE_HISTORY,assertInstanceOf(ReplicaReadException.class,
                cause(f.queue.submit(bad,v->0,100).future())).reason());
        f.rejection=NOT_READY;reason(NOT_READY,f.queue.submit(STALE,v->0,100).future());f.queue.close();f.drain();
        var one=new Fixture(1);reason(CAPACITY_EXCEEDED,one.queue.submit(STALE,v->0,100).future());assertEquals(1,one.permits.availablePermits());
        var zero=new Fixture(3);var result=zero.queue.submit(zero.minimum(1,0),v->fail("behind callback"),100).future();
        assertEquals(1,zero.app.pending.size());zero.drain();
        assertEquals(ReplicaReadException.Reason.PROGRESS_NOT_REACHED,assertInstanceOf(ReplicaReadException.class,cause(result)).reason());
        assertEquals(0,zero.queue.counts().owned());
    }

    @Test void registrationRechecksPublicationAndDoesNotLoseEitherWakeupOrder() {
        for(boolean duringRegistration:List.of(false,true)) {
            var f=new Fixture(3);var options=f.minimum(1,10);
            if(duringRegistration)f.registerHook=()->f.publish(1);else f.publish(1);
            var result=f.queue.submit(options,v->42,100).future();f.drain();
            assertEquals(42,result.join().value());assertEquals(0,f.queue.counts().owned());
        }
    }

    @Test void equalityAtDeadlineExpiresBeforeCaptureAndPublicationCannotReviveIt() {
        var f=new Fixture(3);var callbacks=new AtomicInteger();
        var result=f.queue.submit(f.minimum(1,10),v->callbacks.incrementAndGet(),10).future();
        f.expire(10);f.publish(1);f.drain();reason(DEADLINE_EXCEEDED,result);assertEquals(0,callbacks.get());
        var g=new Fixture(3);g.captureHook=()->g.now.set(10);
        var delayed=g.queue.submit(STALE,v->callbacks.incrementAndGet(),10).future();g.drain();
        reason(DEADLINE_EXCEEDED,delayed);assertEquals(0,callbacks.get());assertEquals(0,g.alarms.size());
    }

    @Test void capturedCallbacksMayOutliveDeadlineAndCloseButQueuedRequestsCannot() {
        var f=new Fixture(4);var queued=new AtomicReference<CompletableFuture<ReplicaReadResult<Integer>>>();
        var captured=f.queue.submit(STALE,v->{
            queued.set(f.queue.<Integer>submit(f.minimum(2,10),w->fail("closed waiting callback"),10).future());
            f.expire(11);f.queue.close();assertEquals(1,f.queue.counts().captured());return 9;
        },10).future();f.drain();assertEquals(9,captured.join().value());
        reason(DEADLINE_EXCEEDED,queued.get());reason(CLOSED,f.queue.submit(STALE,v->0,100).future());
        assertEquals(0,f.queue.counts().owned());assertEquals(4,f.permits.availablePermits());
    }

    @Test void stateTransitionRejectsWaitersInsteadOfCarryingThemThroughRecovery() {
        for(var rejected:List.of(NOT_READY,STORAGE_FAILURE,CLOSED)) {
            var f=new Fixture(3);var result=f.queue.submit(f.minimum(1,10),v->fail("revived waiter"),100).future();
            f.rejection=rejected;f.queue.changed();f.rejection=null;f.publish(1);f.drain();reason(rejected,result);
            assertEquals(0,f.queue.counts().owned());assertEquals(0,f.alarms.size());
        }
    }

    @Test void cancellingBeforeCaptureSuppressesCallbackAndReturnsExactlyOnePermit() {
        var f=new Fixture(3);var called=new AtomicInteger();var request=f.queue.submit(STALE,v->called.incrementAndGet(),100);
        assertTrue(request.future().cancel(true));f.publish(1);f.expire(101);f.drain();
        assertEquals(0,called.get());assertTrue(request.future().isCancelled());assertEquals(3,f.permits.availablePermits());
        request.future().cancel(false);assertEquals(3,f.permits.availablePermits());
    }

    @Test void cancelledCapturedWorkRetainsItsPermitUntilWorkAndCancelHandlersBothReturn() throws Exception {
        var f=new Fixture(2);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        var cancelling=new CountDownLatch(1);var releaseHandler=new CountDownLatch(1);
        var request=f.queue.submit(STALE,v->{entered.countDown();await(release);return 1;},100);
        request.future().whenComplete((v,e)->{assertFalse(Thread.holdsLock(f.lock));cancelling.countDown();await(releaseHandler);});
        Thread application=Thread.ofPlatform().start(f.app.pending.remove());Thread canceller=null;
        try {
            await(entered);canceller=Thread.ofPlatform().start(()->request.future().cancel(true));await(cancelling);
            assertEquals(1,f.queue.counts().captured());assertEquals(0,f.alarms.size());
            release.countDown();application.join(5000);assertFalse(application.isAlive());f.completions.drain();
            assertEquals(1,f.queue.counts().owned(),"cancel completion handlers still own the permit");
            reason(CAPACITY_EXCEEDED,f.queue.submit(STALE,v->0,100).future());
        } finally {
            release.countDown();releaseHandler.countDown();application.join(5000);if(canceller!=null)canceller.join(5000);
        }
        assertTrue(request.future().isCancelled());assertEquals(0,f.queue.counts().owned());assertEquals(2,f.permits.availablePermits());
    }

    @Test void completionHandlersRunOutsideTheMonitorButKeepOriginalAdmission() {
        var f=new Fixture(2);var result=f.queue.submit(STALE,v->null,100).future();var observed=new AtomicBoolean();
        result.thenRun(()->{
            assertFalse(Thread.holdsLock(f.lock));assertEquals(1,f.queue.counts().owned());
            reason(CAPACITY_EXCEEDED,f.queue.submit(STALE,v->0,100).future());observed.set(true);
        });
        f.app.drain();assertFalse(result.isDone());f.completions.drain();
        assertTrue(observed.get());assertNull(result.join().value());assertEquals(2,f.permits.availablePermits());
    }

    @Test void strongNeedsItsOwnBarrierAndExpiredBarrierWorkCannotReleaseCapacityEarly() {
        var f=new Fixture(2);var request=f.queue.submit(STRONG,v->4,10);assertEquals(0,f.app.pending.size());
        f.expire(10);f.completions.drain();reason(DEADLINE_EXCEEDED,request.future());
        assertEquals(1,f.queue.counts().owned(),"fresh barrier still owns real work");
        request.barrier(4,0);assertEquals(0,f.queue.counts().owned());assertEquals(2,f.permits.availablePermits());
        var g=new Fixture(3);var valid=g.queue.submit(STRONG,v->5,100);valid.barrier(4,0);g.drain();assertEquals(5,valid.future().join().value());
        var fenced=g.queue.submit(STRONG,v->fail("stale strong callback"),100);fenced.barrier(7,0);g.drain();reason(STALE_EPOCH,fenced.future());
    }

    @Test void callbackFailureIsNotRetriedOrReplacedAndReleasesOwnership() {
        var f=new Fixture(3);var failure=new AssertionError("original callback");var calls=new AtomicInteger();
        var result=f.queue.submit(STALE,v->{calls.incrementAndGet();throw failure;},100).future();f.drain();
        assertSame(failure,cause(result));f.publish(1);f.drain();assertEquals(1,calls.get());
        assertEquals(0,f.queue.counts().owned());assertEquals(3,f.permits.availablePermits());
    }

    @Test void dispatchRefusalHasTypedCapacityFailureAndNoOrphanTimerOrPermit() {
        var f=new Fixture(3);f.app.reject=true;
        var result=f.queue.submit(STALE,v->fail("refused callback"),100).future();f.drain();
        reason(CAPACITY_EXCEEDED,result);assertEquals(0,f.queue.counts().marker());assertEquals(0,f.alarms.size());
        assertEquals(0,f.queue.counts().owned());assertEquals(3,f.permits.availablePermits());
    }
}
