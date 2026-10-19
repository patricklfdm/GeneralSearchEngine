package io.github.patricklfdm.generalsearch.replication;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;

/** One application thread, bounded ordinary queue and one coalesced explicit-read turn. */
final class AutomaticApplicationWorker extends AbstractExecutorService {
    private final Object lock = new Object();
    private final int capacity;
    private final ArrayDeque<Runnable> ordinary = new ArrayDeque<>();
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(1, 1, 0, TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(1), task -> Thread.ofPlatform().daemon()
                    .name("gse-automatic-application").unstarted(task));
    private Runnable read;
    private boolean running, closed, preferRead;

    AutomaticApplicationWorker(int capacity) {
        if (capacity < 1) throw new IllegalArgumentException("application queue capacity");
        this.capacity = capacity;
    }

    @Override public void execute(Runnable task) {
        java.util.Objects.requireNonNull(task);
        synchronized (lock) {
            if (closed || ordinary.size() == capacity) throw new RejectedExecutionException("application queue unavailable");
            ordinary.addLast(task);
            start();
        }
    }

    void executeRead(Runnable task) {
        java.util.Objects.requireNonNull(task);
        synchronized (lock) {
            if (closed || read != null) throw new RejectedExecutionException("application read turn unavailable");
            read = task;
            start();
        }
    }

    private void start() {
        if (!running) { running = true; worker.execute(this::turn); }
    }

    private void turn() {
        Runnable task;
        synchronized (lock) {
            if (read == null && ordinary.isEmpty()) {
                running = false;
                if (closed) worker.shutdown();
                return;
            }
            if (read != null && (ordinary.isEmpty() || preferRead)) {
                task = read; read = null; preferRead = false;
            } else { task = ordinary.removeFirst(); preferRead = true; }
        }
        try { task.run(); }
        finally {
            synchronized (lock) {
                running = false;
                if (!ordinary.isEmpty() || read != null) start();
                else if (closed) worker.shutdown();
            }
        }
    }

    @Override public void shutdown() {
        synchronized (lock) { closed = true; if (!running) worker.shutdown(); }
    }

    @Override public List<Runnable> shutdownNow() {
        synchronized (lock) {
            closed = true;
            var pending = new ArrayList<>(ordinary); ordinary.clear();
            if (read != null) { pending.add(read); read = null; }
            worker.shutdownNow();
            return pending;
        }
    }

    @Override public boolean isShutdown() { synchronized (lock) { return closed; } }
    @Override public boolean isTerminated() { return worker.isTerminated(); }
    @Override public boolean awaitTermination(long time, TimeUnit unit) throws InterruptedException {
        return worker.awaitTermination(time, unit);
    }
}
