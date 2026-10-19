package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V52ReadQueueTest.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;

/** Exhaustive boundary variants at a controlled scheduler; separate from physical process evidence. */
class V52ReadLifecycleTest {
    @Test void allZeroAndPositiveBoundRelationsUseTheActualCutWithoutExtraWork() {
        for(int wait:List.of(0,60000))for(long minimum:List.of(6L,7L,8L)) {
            var f=new Fixture(4);f.publish(7);var calls=new AtomicInteger();
            var result=f.queue.submit(f.minimum(minimum,wait),v->calls.incrementAndGet(),10).future();f.drain();
            if(minimum<=7) {
                assertEquals(7,result.join().progress().index());assertEquals(1,calls.get());
            } else if(wait==0) {
                assertEquals(ReplicaReadException.Reason.PROGRESS_NOT_REACHED,
                        assertInstanceOf(ReplicaReadException.class,cause(result)).reason());
            } else {
                assertFalse(result.isDone());assertEquals(0,f.app.pending.size());assertEquals(1,f.alarms.size());
                f.expire(10);f.drain();reason(DEADLINE_EXCEEDED,result);
            }
            assertEquals(minimum<=7?1:0,calls.get());assertEquals(7,f.cut.index());
            assertEquals(4,f.permits.availablePermits());assertEquals(0,f.alarms.size());
        }
    }

    @Test void eachIdentityMismatchRejectsBeforeAllocatingEvenWithNoReadSlots() {
        var f=new Fixture(1);var cut=f.cut;
        for(var token:List.of(
                new ReplicaReadToken(1,new ReplicationGroupId(UUID.randomUUID()),cut.history(),cut.manifest(),0),
                new ReplicaReadToken(1,cut.group(),UUID.randomUUID(),cut.manifest(),0),
                new ReplicaReadToken(1,cut.group(),cut.history(),"cd".repeat(32),0))) {
            var result=f.queue.submit(new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.of(token),60000),
                    v->fail("foreign history callback"),100).future();
            assertEquals(ReplicaReadException.Reason.INCOMPATIBLE_HISTORY,
                    assertInstanceOf(ReplicaReadException.class,cause(result)).reason());
            assertEquals(0,f.queue.counts().owned());assertTrue(f.alarms.isEmpty());assertTrue(f.app.pending.isEmpty());
        }
        assertEquals(1,f.permits.availablePermits());
    }

    @Test void defaultAndSmallAdmissionCapsDoNotDependOnTheNumericTokenBound() {
        for(int pending:List.of(1,4,65,10000)) {
            var f=new Fixture(pending);int limit=Math.min(64,pending-1);var futures=new ArrayList<CompletableFuture<?>>();
            for(int i=0;i<limit;i++)futures.add(f.queue.submit(f.minimum(Long.MAX_VALUE,60000),v->null,100).future());
            assertEquals(limit,f.queue.counts().owned());assertEquals(limit,f.alarms.size());assertEquals(0,f.app.pending.size());
            reason(CAPACITY_EXCEEDED,f.queue.submit(STALE,v->fail("excess callback"),100).future());
            assertTrue(f.permits.tryAcquire());f.permits.release();
            f.publish(Long.MAX_VALUE);f.drain();assertTrue(futures.stream().allMatch(CompletableFuture::isDone));
            assertEquals(pending,f.permits.availablePermits());assertEquals(0,f.queue.counts().owned());assertTrue(f.alarms.isEmpty());
        }
    }

    @Test void cancellingWaitingOrReadyAndClosingWaitingCannotBeRevivedByProgress() {
        for(boolean waiting:List.of(false,true))for(boolean close:List.of(false,true)) {
            var f=new Fixture(4);var calls=new AtomicInteger();
            var result=f.queue.submit(waiting?f.minimum(1,60000):STALE,v->calls.incrementAndGet(),100).future();
            if(close)f.queue.close();else assertTrue(result.cancel(true));
            f.publish(1);f.expire(101);f.drain();
            if(close)reason(CLOSED,result);else assertTrue(result.isCancelled());
            assertEquals(0,calls.get());assertEquals(4,f.permits.availablePermits());assertEquals(0,f.queue.counts().owned());
        }
    }

    @Test void aLaterStateFailureCannotInvalidateTheAlreadyCapturedCallback() {
        for(var reason:List.of(NOT_READY,STALE_EPOCH,STORAGE_FAILURE,CLOSED)) {
            var f=new Fixture(3);var request=f.queue.submit(STRONG,v->{
                f.rejection=reason;f.queue.changed();f.expire(101);return 7;
            },100);request.barrier(4,0);f.drain();
            assertEquals(7,request.future().join().value());assertEquals(ReplicaReadPolicy.LEADER_STRONG,request.future().join().policy());
            reason(reason,f.queue.submit(STALE,v->fail("new capture after failure"),200).future());
            assertEquals(3,f.permits.availablePermits());
        }
    }

    @Test void publicationExactlyAtDeadlineAndDelayedTimerBothLoseToCaptureCheck() {
        for(boolean timerDelivered:List.of(false,true)) {
            var f=new Fixture(4);var result=f.queue.submit(f.minimum(1,60000),v->fail("expired capture"),10).future();
            if(timerDelivered)f.expire(10);else f.now.set(10);
            f.publish(1);f.drain();reason(DEADLINE_EXCEEDED,result);
            f.now.set(11);f.publish(2);f.drain();reason(DEADLINE_EXCEEDED,result);
            assertEquals(4,f.permits.availablePermits());assertTrue(f.alarms.isEmpty());
        }
    }

    @Test void cancellationDuringAnAlreadyCompletedHandlerCannotReleaseItsOwnership() throws Exception {
        var f=new Fixture(2);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        var result=f.queue.submit(STALE,v->null,100).future();result.thenRun(()->{entered.countDown();await(release);});
        f.app.drain();Thread completion=Thread.ofPlatform().start(f.completions::drain);
        try {
            await(entered);assertFalse(result.cancel(true));assertEquals(1,f.queue.counts().settling());
            reason(CAPACITY_EXCEEDED,f.queue.submit(STALE,v->fail("handler owns slot"),100).future());
        } finally {release.countDown();completion.join(5000);}
        assertFalse(completion.isAlive());assertEquals(2,f.permits.availablePermits());assertEquals(0,f.queue.counts().owned());
    }
}
