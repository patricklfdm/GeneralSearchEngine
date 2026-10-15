package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class V52ApplicationWorkerTest {
    private static void await(CountDownLatch latch) {
        try { assertTrue(latch.await(5, TimeUnit.SECONDS)); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new AssertionError(e); }
    }

    @Test void coalescedReadTurnCannotConsumeOrdinaryCapacityOrStarveEitherQueue() throws Exception {
        var worker = new AutomaticApplicationWorker(4);
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        var done = new CountDownLatch(6);
        var calls = Collections.synchronizedList(new ArrayList<String>());
        var failure = new AtomicReference<Throwable>();
        worker.execute(() -> { entered.countDown(); await(release); });
        try {
            await(entered);
            for (int i = 1; i <= 4; i++) { int n = i; worker.execute(() -> { calls.add("p" + n); done.countDown(); }); }
            assertThrows(RejectedExecutionException.class, () -> worker.execute(() -> fail("over capacity")));
            worker.executeRead(() -> {
                calls.add("r1");
                try { worker.executeRead(() -> { calls.add("r2"); done.countDown(); }); }
                catch (Throwable e) { failure.set(e); }
                done.countDown();
            });
            assertThrows(RejectedExecutionException.class, () -> worker.executeRead(() -> fail("second marker")));
            release.countDown(); await(done);
            assertNull(failure.get());
            assertEquals(List.of("r1", "p1", "r2", "p2", "p3", "p4"), calls);
        } finally { release.countDown(); worker.shutdown(); assertTrue(worker.awaitTermination(5, TimeUnit.SECONDS)); }
    }

    @Test void cooperativeCloseRetainsActiveTurnAndDrainsAlreadyQueuedWork() throws Exception {
        var worker = new AutomaticApplicationWorker(4);
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        var completed = new CountDownLatch(2);
        worker.executeRead(() -> { entered.countDown(); await(release); completed.countDown(); });
        try {
            await(entered); worker.execute(completed::countDown); worker.shutdown();
            assertTrue(worker.isShutdown()); assertFalse(worker.isTerminated());
            assertFalse(worker.awaitTermination(0, TimeUnit.NANOSECONDS));
            assertThrows(RejectedExecutionException.class, () -> worker.executeRead(() -> fail("after close")));
            assertThrows(RejectedExecutionException.class, () -> worker.execute(() -> fail("after close")));
        } finally { release.countDown(); assertTrue(worker.awaitTermination(5, TimeUnit.SECONDS)); }
        assertEquals(0, completed.getCount());
    }

    @Test void noReadTrafficPreservesExistingOrdinaryFifo() throws Exception {
        var worker = new AutomaticApplicationWorker(4);
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        var calls = Collections.synchronizedList(new ArrayList<Integer>());
        worker.execute(() -> { entered.countDown(); await(release); });
        try {
            await(entered);
            for (int i = 0; i < 4; i++) { int n = i; worker.execute(() -> calls.add(n)); }
            worker.shutdown();
        } finally { release.countDown(); assertTrue(worker.awaitTermination(5, TimeUnit.SECONDS)); }
        assertEquals(List.of(0, 1, 2, 3), calls);
    }
}
