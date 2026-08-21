package org.example.generalsearch.engine;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.example.generalsearch.catalog.CatalogSnapshot;
import org.example.generalsearch.catalog.CatalogSnapshotBuilder;
import org.example.generalsearch.engine.mutation.CatalogMutation;
import org.example.generalsearch.engine.mutation.MutationTask;
import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.query.SnapshotSearcher;

public final class SnapshotUpdateEngine implements ProductSearchEngine {
    private final AtomicReference<CatalogSnapshot> current =
            new AtomicReference<>(new CatalogSnapshot());
    private final BlockingQueue<MutationTask> queue;
    private final SnapshotEngineConfig config;
    private final SnapshotSearcher searcher;
    private final Thread writerThread;
    private final Object lifecycleMonitor = new Object();
    private volatile boolean accepting = true;

    public SnapshotUpdateEngine() {
        this(SnapshotEngineConfig.DEFAULT);
    }

    public SnapshotUpdateEngine(SnapshotEngineConfig config) {
        this.config = Objects.requireNonNull(config, "config");
        this.queue = new LinkedBlockingQueue<>(config.queueCapacity());
        this.searcher = new SnapshotSearcher();
        this.writerThread = new Thread(this::writerLoop, "product-snapshot-writer");
        this.writerThread.start();
    }

    @Override
    public CompletableFuture<Void> add(int docId, Product product) {
        return submit(new CatalogMutation.Add(docId, product));
    }

    @Override
    public CompletableFuture<Void> update(int docId, Product product) {
        return submit(new CatalogMutation.Update(docId, product));
    }

    @Override
    public CompletableFuture<Void> remove(int docId) {
        return submit(new CatalogMutation.Remove(docId));
    }

    @Override
    public Product get(int docId) {
        return current.get().get(docId);
    }

    @Override
    public List<Product> search(ProductFilter filter) {
        return searcher.search(current.get(), filter);
    }

    CatalogSnapshot snapshotForTesting() {
        return current.get();
    }

    private CompletableFuture<Void> submit(CatalogMutation mutation) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        MutationTask task = new MutationTask(mutation, completion);
        synchronized (lifecycleMonitor) {
            if (!accepting) {
                completion.completeExceptionally(
                        new IllegalStateException("engine is closed"));
            } else if (!queue.offer(task)) {
                completion.completeExceptionally(
                        new RejectedExecutionException("mutation queue is full"));
            }
        }
        return completion;
    }

    private void writerLoop() {
        try {
            while (accepting || !queue.isEmpty()) {
                MutationTask first;
                try {
                    first = queue.poll(100, TimeUnit.MILLISECONDS);
                } catch (InterruptedException interrupted) {
                    if (accepting) {
                        Thread.currentThread().interrupt();
                        failPending(interrupted);
                        return;
                    }
                    continue;
                }
                if (first == null) {
                    continue;
                }
                List<MutationTask> batch = collectBatch(first);
                try {
                    processBatch(batch);
                } catch (Throwable failure) {
                    batch.forEach(task -> task.completion().completeExceptionally(failure));
                    stopAfterFailure(failure);
                    return;
                }
            }
        } catch (Throwable failure) {
            stopAfterFailure(failure);
        }
    }

    private List<MutationTask> collectBatch(MutationTask first) {
        List<MutationTask> batch = new ArrayList<>(config.maxBatchSize());
        batch.add(first);
        long deadline = System.nanoTime() + config.maxBatchWait().toNanos();
        while (batch.size() < config.maxBatchSize()) {
            queue.drainTo(batch, config.maxBatchSize() - batch.size());
            if (batch.size() >= config.maxBatchSize()) {
                break;
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) {
                break;
            }
            MutationTask task;
            try {
                task = queue.poll(remaining, TimeUnit.NANOSECONDS);
            } catch (InterruptedException interrupted) {
                // close() interrupts the batch wait so the accepted partial batch can
                // be published immediately instead of waiting for the deadline.
                break;
            }
            if (task == null) {
                break;
            }
            batch.add(task);
        }
        return batch;
    }

    private void processBatch(List<MutationTask> batch) {
        CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(current.get());
        List<MutationTask> successful = new ArrayList<>(batch.size());
        for (MutationTask task : batch) {
            try {
                apply(builder, task.mutation());
                successful.add(task);
            } catch (RuntimeException failure) {
                task.completion().completeExceptionally(failure);
            }
        }
        if (successful.isEmpty()) {
            return;
        }
        current.set(builder.build());
        successful.forEach(task -> task.completion().complete(null));
    }

    private void apply(CatalogSnapshotBuilder builder, CatalogMutation mutation) {
        switch (mutation) {
            case CatalogMutation.Add add -> builder.add(add.docId(), add.product());
            case CatalogMutation.Update update -> builder.update(update.docId(), update.product());
            case CatalogMutation.Remove remove -> builder.remove(remove.docId());
        }
    }

    private void failPending(Throwable failure) {
        MutationTask task;
        while ((task = queue.poll()) != null) {
            task.completion().completeExceptionally(failure);
        }
    }

    private void stopAfterFailure(Throwable failure) {
        synchronized (lifecycleMonitor) {
            accepting = false;
        }
        failPending(failure);
    }

    @Override
    public void close() {
        boolean shouldInterrupt = false;
        synchronized (lifecycleMonitor) {
            if (accepting) {
                accepting = false;
                shouldInterrupt = true;
            }
        }
        if (shouldInterrupt) {
            writerThread.interrupt();
        }
        if (Thread.currentThread() == writerThread) {
            return;
        }
        boolean interrupted = false;
        while (writerThread.isAlive()) {
            try {
                writerThread.join();
            } catch (InterruptedException exception) {
                interrupted = true;
            }
        }
        if (interrupted) {
            Thread.currentThread().interrupt();
        }
    }
}
