package io.github.patricklfdm.generalsearch.admission;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

class PerformanceTelemetryTest {
    @AfterEach
    void disable() {
        PerformanceTelemetry.configure("disabled", false);
    }

    @Test
    void aForceFinishingAfterReconfigurationDoesNotBelongToTheNewWindow() throws Exception {
        PerformanceTelemetry.configure("instrumented-a", true);
        var started = new CountDownLatch(1);
        var finish = new CountDownLatch(1);
        try (var executor = Executors.newSingleThreadExecutor()) {
            var pending = executor.submit(() -> {
                long start = System.nanoTime();
                started.countDown();
                assertTrue(finish.await(5, TimeUnit.SECONDS));
                PerformanceTelemetry.force("PROOF", start, System.nanoTime());
                return null;
            });
            try {
                assertTrue(started.await(5, TimeUnit.SECONDS));
                PerformanceTelemetry.configure("instrumented-b", true);
            } finally {
                finish.countDown();
            }
            pending.get(5, TimeUnit.SECONDS);
        }
        assertEquals(List.of(), PerformanceTelemetry.snapshot().get("forces"));
        long current = System.nanoTime();
        PerformanceTelemetry.force("ENTRY", current, System.nanoTime());
        assertEquals(1, ((List<?>) PerformanceTelemetry.snapshot().get("forces")).size());
    }

    @Test
    void reusingAWindowNameAfterDisablingDoesNotAdoptAnOldForce() {
        PerformanceTelemetry.configure("instrumented", true);
        long oldStart = System.nanoTime();
        PerformanceTelemetry.configure("disabled", false);
        PerformanceTelemetry.configure("instrumented", true);
        PerformanceTelemetry.force("PROOF", oldStart, System.nanoTime());
        assertEquals(List.of(), PerformanceTelemetry.snapshot().get("forces"));
    }

    @Test
    void aDelayedEventFromThePreviousWindowIsExcluded() {
        PerformanceTelemetry.configure("instrumented-a", true);
        long oldEvent = System.nanoTime();
        PerformanceTelemetry.configure("instrumented-b", true);
        PerformanceTelemetry.event("AFTER_PROOF_QUORUM", 10, oldEvent);
        assertEquals(List.of(), PerformanceTelemetry.snapshot().get("events"));
        PerformanceTelemetry.event("AFTER_PROOF_QUORUM", 11, System.nanoTime());
        assertEquals(1, ((List<?>) PerformanceTelemetry.snapshot().get("events")).size());
    }
}
