package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static org.junit.jupiter.api.Assertions.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;

class V51CheckpointAwaitTest {
    static final long SECOND=TimeUnit.SECONDS.toNanos(1),PAUSE=TimeUnit.MILLISECONDS.toNanos(250);
    static AutomaticReplicationException capacity() {return failure(CAPACITY_EXCEEDED,NOT_APPLICABLE);}
    static AutomaticReplicationException failure(AutomaticReplicationException.Reason reason,
            AutomaticReplicationException.Outcome outcome) {
        return new AutomaticReplicationException(reason,outcome,Optional.empty(),"checkpoint test rejection");
    }
    static final class Clock {
        long now;final List<Long> sleeps=new ArrayList<>();
        void sleep(long nanos) {sleeps.add(nanos);now+=nanos;}
        int await(Supplier<CompletableFuture<Void>> checkpoint,long budget) throws Exception {
            return V51CheckpointAwait.await(checkpoint,()->now,this::sleep,budget);
        }
    }
    @Test void immediateSuccessNeedsNoPause() throws Exception {
        var clock=new Clock();assertEquals(1,clock.await(()->CompletableFuture.completedFuture(null),SECOND));
        assertTrue(clock.sleeps.isEmpty());
    }
    @Test void onlyCompletedCapacityRefusalsWaitForActualSuccess() throws Exception {
        var clock=new Clock();var calls=new AtomicInteger();
        assertEquals(3,clock.await(()->calls.incrementAndGet()<3
                ?CompletableFuture.failedFuture(capacity()):CompletableFuture.completedFuture(null),SECOND));
        assertEquals(3,calls.get());assertEquals(List.of(PAUSE,PAUSE),clock.sleeps);
    }
    @Test void permanentCapacityPressureExhaustsOneFixedDeadlineWithDiagnostics() {
        var clock=new Clock();var calls=new AtomicInteger();var rejection=capacity();
        var error=assertThrows(TimeoutException.class,()->clock.await(()->{
            calls.incrementAndGet();return CompletableFuture.failedFuture(rejection);
        },SECOND));
        assertEquals(4,calls.get());assertEquals(SECOND,clock.now);
        assertEquals(List.of(PAUSE,PAUSE,PAUSE,PAUSE),clock.sleeps);
        assertTrue(error.getMessage().contains("4 attempt(s)"));assertSame(rejection,error.getCause().getCause());
    }
    @Test void everyOtherReasonAndOutcomeFailsWithoutRetry() {
        for(var reason:AutomaticReplicationException.Reason.values())
            for(var outcome:AutomaticReplicationException.Outcome.values()) {
                if(reason==CAPACITY_EXCEEDED&&outcome==NOT_APPLICABLE)continue;
                var clock=new Clock();var calls=new AtomicInteger();var rejection=failure(reason,outcome);
                var error=assertThrows(ExecutionException.class,()->clock.await(()->{
                    calls.incrementAndGet();return CompletableFuture.failedFuture(rejection);
                },SECOND));
                assertSame(rejection,error.getCause());assertEquals(1,calls.get());assertTrue(clock.sleeps.isEmpty());
            }
    }
    @Test void unknownSynchronousAndCancelledFailuresAreNotRetried() {
        var clock=new Clock();var calls=new AtomicInteger();var unknown=new IllegalStateException("unknown");
        var error=assertThrows(ExecutionException.class,()->clock.await(()->{
            calls.incrementAndGet();return CompletableFuture.failedFuture(unknown);
        },SECOND));
        assertSame(unknown,error.getCause());assertEquals(1,calls.get());
        var synchronous=capacity();calls.set(0);
        assertSame(synchronous,assertThrows(AutomaticReplicationException.class,()->clock.await(()->{
            calls.incrementAndGet();throw synchronous;
        },SECOND)));
        assertEquals(1,calls.get());calls.set(0);
        var cancelled=new CompletableFuture<Void>();cancelled.cancel(false);
        assertThrows(CancellationException.class,()->clock.await(()->{calls.incrementAndGet();return cancelled;},SECOND));
        assertEquals(1,calls.get());assertTrue(clock.sleeps.isEmpty());
    }
    @Test void missingResponseTimesOutWithoutAnotherInvocation() {
        var clock=new Clock();var calls=new AtomicInteger();var pending=new CompletableFuture<Void>();
        assertThrows(TimeoutException.class,()->clock.await(()->{calls.incrementAndGet();return pending;},1));
        assertEquals(1,calls.get());assertFalse(pending.isDone());assertTrue(clock.sleeps.isEmpty());
    }
    @Test void submissionAndPausesShareTheDeadline() {
        var clock=new Clock();var calls=new AtomicInteger();
        assertThrows(TimeoutException.class,()->clock.await(()->{
            calls.incrementAndGet();clock.now+=SECOND-100;return CompletableFuture.failedFuture(capacity());
        },SECOND));
        assertEquals(1,calls.get());assertEquals(List.of(100L),clock.sleeps);assertEquals(SECOND,clock.now);
        var slow=new Clock();
        assertThrows(TimeoutException.class,()->slow.await(()->{
            slow.now+=SECOND;return CompletableFuture.completedFuture(null);
        },SECOND));
        assertTrue(slow.sleeps.isEmpty());
    }
    @Test void expiredBudgetNeverInvokesCheckpoint() {
        var calls=new AtomicInteger();
        assertThrows(TimeoutException.class,()->new Clock().await(()->{
            calls.incrementAndGet();return CompletableFuture.completedFuture(null);
        },0));
        assertEquals(0,calls.get());
    }
    @Test void interruptionStopsWaitingAndPreservesFlag() {
        var calls=new AtomicInteger();
        try {
            assertThrows(InterruptedException.class,()->V51CheckpointAwait.await(()->{
                calls.incrementAndGet();return CompletableFuture.failedFuture(capacity());
            },()->0,nanos->{throw new InterruptedException("stop");},SECOND));
            assertEquals(1,calls.get());assertTrue(Thread.currentThread().isInterrupted());
            assertThrows(InterruptedException.class,()->new Clock().await(()->{
                calls.incrementAndGet();return CompletableFuture.completedFuture(null);
            },SECOND));
            assertEquals(1,calls.get());assertTrue(Thread.currentThread().isInterrupted());
        } finally {Thread.interrupted();}
    }
}
