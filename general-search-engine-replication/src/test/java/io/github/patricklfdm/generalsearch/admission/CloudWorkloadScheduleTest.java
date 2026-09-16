package io.github.patricklfdm.generalsearch.admission;

import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;

class CloudWorkloadScheduleTest {
    private static final long MS = 1_000_000L;

    /** Virtual completions reproduce the CI trace without timing-sensitive sleeps. */
    private static final class Clock implements CloudWorkloadSchedule.Driver {
        long now;
        int slowCall = 5, pauseAfter = -1, missed = -1, maximumPending;
        long duration = 222*MS, pause;
        final List<Integer> calls = new ArrayList<>();
        final List<Long> dispatched = new ArrayList<>();
        final Map<CompletableFuture<Void>,Long> pending = new LinkedHashMap<>();
        public long now() { return now; }
        void advance(long target) {
            now = Math.max(now, target);
            pending.forEach((future, end) -> { if (end <= now) future.complete(null); });
        }
        public void until(long due) {
            advance(due);
            if (calls.size() == pauseAfter) { advance(now+pause); pauseAfter = -1; }
        }
        public void await(CompletableFuture<Void> future, long deadline) throws Exception {
            long end = pending.get(future);
            if (end > deadline) { advance(deadline); throw new TimeoutException("test window deadline"); }
            advance(end); future.get();
        }
        public CompletableFuture<Void> submit(int call, long nominal, long due, long issued) {
            assertEquals(now, issued); assertTrue(nominal <= due && due <= issued);
            calls.add(call); dispatched.add(issued);
            var future = new CompletableFuture<Void>();
            pending.put(future, issued+(call == slowCall ? duration : 0)); advance(now);
            maximumPending = Math.max(maximumPending, (int)pending.keySet().stream().filter(f -> !f.isDone()).count());
            return future;
        }
        public void missed(int call, long due, long observed, boolean pending) { missed = call; }
    }

    @Test void localOverrunPreservesDropBeforeCreateWithoutSkipping() throws Exception {
        var clock = new Clock();
        var window = CloudWorkloadSchedule.run(10,1,200*MS,true,20_000*MS,clock);
        assertEquals(java.util.stream.IntStream.range(0,10).boxed().toList(), clock.calls);
        assertEquals(1222*MS, clock.dispatched.get(6)); // INDEX_DROP after 222-ms REMOVE_ALL.
        assertEquals(1422*MS, clock.dispatched.get(7)); // INDEX_CREATE keeps its place.
        assertEquals(2022*MS, window.end()); assertEquals(-1, clock.missed);
        assertEquals(1, clock.maximumPending);
    }

    @Test void fixedRateOverrunStopsAtFirstMissInsteadOfRunningCreate() {
        var clock = new Clock();
        var failure = assertThrows(IllegalStateException.class,
                () -> CloudWorkloadSchedule.run(10,1,200*MS,false,3000*MS,clock));
        assertTrue(failure.getMessage().contains("call 6: lane still pending"));
        assertEquals(List.of(0,1,2,3,4,5),clock.calls); assertEquals(6, clock.missed);
    }

    @Test void localSchedulerPauseDoesNotProduceCatchupBurst() throws Exception {
        var clock = new Clock(); clock.duration = 0; clock.pauseAfter = 2; clock.pause = 350*MS;
        CloudWorkloadSchedule.run(10,1,200*MS,true,20_000*MS,clock);
        assertEquals(10,clock.calls.size()); assertEquals(750*MS,clock.dispatched.get(2));
        for (int i=1;i<clock.dispatched.size();i++)
            assertTrue(clock.dispatched.get(i)-clock.dispatched.get(i-1)>=200*MS);
    }

    @Test void fixedRateSchedulerPauseFailsBeforeSubmittingLateCall() {
        var clock = new Clock(); clock.pauseAfter = 2; clock.pause = 350*MS;
        var failure = assertThrows(IllegalStateException.class,
                () -> CloudWorkloadSchedule.run(10,1,200*MS,false,3000*MS,clock));
        assertTrue(failure.getMessage().contains("call 2: scheduler late"));
        assertEquals(List.of(0,1),clock.calls);
    }

    @Test void pacedFourLaneDelayKeepsOrderAndBoundedConcurrency() throws Exception {
        var clock = new Clock(); clock.slowCall = 0; clock.duration = 900*MS;
        CloudWorkloadSchedule.run(12,4,200*MS,true,20_000*MS,clock);
        assertEquals(java.util.stream.IntStream.range(0,12).boxed().toList(),clock.calls);
        assertEquals(900*MS,clock.dispatched.get(4)); assertEquals(1100*MS,clock.dispatched.get(5));
        assertTrue(clock.maximumPending<=4);
    }

    @Test void pacedWindowStillHasAHardDeadline() {
        var clock = new Clock(); clock.slowCall=0; clock.duration=21_000*MS;
        assertThrows(TimeoutException.class,
                () -> CloudWorkloadSchedule.run(10,1,200*MS,true,20_000*MS,clock));
        assertEquals(List.of(0),clock.calls); assertEquals(20_000*MS,clock.now);
    }

    @Test void healthyAndSustainedCloudRatesRemainFixed() throws Exception {
        for (int lanes : List.of(1,4)) {
            var clock = new Clock(); clock.duration=0;
            long interval=(lanes==1?100:50)*MS;
            var window=CloudWorkloadSchedule.run(20,lanes,interval,false,20*interval+1000*MS,clock);
            for (int i=0;i<20;i++) assertEquals(i*interval,clock.dispatched.get(i));
            assertEquals(20*interval,window.end()); assertEquals(-1,clock.missed);
        }
    }
}
