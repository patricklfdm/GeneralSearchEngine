package io.github.patricklfdm.generalsearch.admission;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeoutException;

/** Bounded arrivals shared by the real probe and deterministic scheduling regressions. */
final class CloudWorkloadSchedule {
    interface Driver {
        long now();
        void until(long due);
        void await(CompletableFuture<Void> future, long deadline) throws Exception;
        CompletableFuture<Void> submit(int call, long nominal, long due, long dispatched);
        void missed(int call, long due, long observed, boolean pending);
    }
    record Window(long start, long end) { }
    private CloudWorkloadSchedule() { }

    static Window run(int calls, int lanes, long interval, boolean paced, long maximumNanos, Driver driver) throws Exception {
        var pending = new CompletableFuture<?>[lanes];
        long begin = driver.now(), deadline = Math.addExact(begin, maximumNanos), next = begin;
        for (int call = 0; call < calls; call++) {
            int lane = call % lanes;
            @SuppressWarnings("unchecked") var prior = (CompletableFuture<Void>) pending[lane];
            long nominal = Math.addExact(begin, Math.multiplyExact((long)call, interval));
            if (paced && prior != null) driver.await(prior, deadline);
            long due = paced ? Math.max(next, driver.now()) : nominal;
            if (due >= deadline) throw new TimeoutException("workload window deadline at call " + call);
            driver.until(due);
            long dispatched = driver.now();
            if (dispatched >= deadline) throw new TimeoutException("workload window deadline at call " + call);
            boolean busy = prior != null && !prior.isDone();
            if (!paced && (busy || dispatched - due >= interval)) {
                driver.missed(call, due, dispatched, busy);
                throw new IllegalStateException("missed arrival slot at call " + call + (busy ? ": lane still pending" : ": scheduler late"));
            }
            if (!paced && prior != null) driver.await(prior, deadline);
            pending[lane] = driver.submit(call, nominal, due, dispatched);
            next = Math.addExact(dispatched, interval);
        }
        for (var future : pending) {
            if (future != null) {
                @SuppressWarnings("unchecked") var typed = (CompletableFuture<Void>) future;
                driver.await(typed, deadline);
            }
        }
        long minimumEnd = Math.addExact(begin, Math.multiplyExact((long)calls, interval));
        long end = paced ? Math.max(minimumEnd, next) : minimumEnd;
        if (end > deadline) throw new TimeoutException("workload window deadline");
        driver.until(end);
        long finished = driver.now();
        if (finished > deadline) throw new TimeoutException("workload window deadline");
        return new Window(begin, finished);
    }
}
