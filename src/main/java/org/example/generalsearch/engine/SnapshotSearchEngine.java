package org.example.generalsearch.engine;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.example.generalsearch.engine.mutation.MutationTask;
import org.example.generalsearch.engine.mutation.SearchMutation;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.query.SnapshotSearcher;
import org.example.generalsearch.schema.SearchSchema;
import org.example.generalsearch.storage.SearchSnapshot;
import org.example.generalsearch.storage.SearchSnapshotBuilder;

public final class SnapshotSearchEngine<K, T> implements SearchEngine<K, T> {
    private final SearchSchema<T, K> schema;
    private final AtomicReference<PublishedState<K, T>> current;
    private final BlockingQueue<MutationTask<K, T>> queue;
    private final SnapshotEngineConfig config;
    private final SnapshotSearcher<T> searcher;
    private final Thread writerThread;
    private final Object lifecycleMonitor = new Object();
    private volatile boolean accepting = true;

    public SnapshotSearchEngine(
            SearchSchema<T, K> schema,
            Collection<? extends IndexDefinition<T>> indexDefinitions
    ) {
        this(SnapshotEngineConfig.DEFAULT, schema, indexDefinitions);
    }

    public SnapshotSearchEngine(
            SnapshotEngineConfig config,
            SearchSchema<T, K> schema,
            Collection<? extends IndexDefinition<T>> indexDefinitions
    ) {
        this.config = Objects.requireNonNull(config, "config");
        this.schema = Objects.requireNonNull(schema, "schema");
        SearchSnapshot<T> emptySnapshot = new SearchSnapshot<>(indexDefinitions);
        this.current = new AtomicReference<>(
                new PublishedState<>(emptySnapshot, Map.of(), 0));
        this.queue = new LinkedBlockingQueue<>(config.queueCapacity());
        this.searcher = new SnapshotSearcher<>();
        this.writerThread = new Thread(
                this::writerLoop,
                "snapshot-search-writer-" + schema.documentType().getSimpleName()
        );
        this.writerThread.start();
    }

    @Override
    public CompletableFuture<Void> add(T document) {
        return submit(SearchMutation.add(document));
    }

    @Override
    public CompletableFuture<Void> update(T document) {
        return submit(SearchMutation.update(document));
    }

    @Override
    public CompletableFuture<Void> remove(K id) {
        return submit(SearchMutation.remove(id));
    }

    @Override
    public T get(K id) {
        Objects.requireNonNull(id, "id");
        PublishedState<K, T> state = current.get();
        Integer docId = state.documentIds().get(id);
        return docId == null ? null : state.snapshot().get(docId);
    }

    @Override
    public List<T> search(Query<T> query) {
        return searcher.search(current.get().snapshot(), query);
    }

    SearchSnapshot<T> snapshotForTesting() {
        return current.get().snapshot();
    }

    Integer internalDocIdForTesting(K id) {
        return current.get().documentIds().get(id);
    }

    private CompletableFuture<Void> submit(SearchMutation<K, T> mutation) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        MutationTask<K, T> task = new MutationTask<>(mutation, completion);
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
                MutationTask<K, T> first;
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
                List<MutationTask<K, T>> batch = collectBatch(first);
                try {
                    processBatch(batch);
                } catch (Throwable failure) {
                    batch.forEach(task ->
                            task.completion().completeExceptionally(failure));
                    stopAfterFailure(failure);
                    return;
                }
            }
        } catch (Throwable failure) {
            stopAfterFailure(failure);
        }
    }

    private List<MutationTask<K, T>> collectBatch(MutationTask<K, T> first) {
        List<MutationTask<K, T>> batch = new ArrayList<>(config.maxBatchSize());
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
            MutationTask<K, T> task;
            try {
                task = queue.poll(remaining, TimeUnit.NANOSECONDS);
            } catch (InterruptedException interrupted) {
                // close() interrupts the wait so an accepted partial batch is
                // published immediately.
                break;
            }
            if (task == null) {
                break;
            }
            batch.add(task);
        }
        return batch;
    }

    private void processBatch(List<MutationTask<K, T>> batch) {
        BatchState state = new BatchState(current.get());
        List<MutationTask<K, T>> successful = new ArrayList<>(batch.size());
        for (MutationTask<K, T> task : batch) {
            try {
                apply(state, task.mutation());
                successful.add(task);
            } catch (RuntimeException failure) {
                task.completion().completeExceptionally(failure);
            }
        }
        if (successful.isEmpty()) {
            return;
        }
        current.set(state.build());
        successful.forEach(task -> task.completion().complete(null));
    }

    private void apply(BatchState state, SearchMutation<K, T> mutation) {
        switch (mutation.type()) {
            case ADD -> state.add(mutation.document());
            case UPDATE -> state.update(mutation.document());
            case REMOVE -> state.remove(mutation.id());
        }
    }

    private void failPending(Throwable failure) {
        MutationTask<K, T> task;
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

    private final class BatchState {
        private final SearchSnapshotBuilder<T> snapshots;
        private final Map<K, Integer> documentIds;
        private int nextDocId;

        private BatchState(PublishedState<K, T> base) {
            snapshots = new SearchSnapshotBuilder<>(base.snapshot());
            documentIds = new HashMap<>(base.documentIds());
            nextDocId = base.nextDocId();
        }

        private void add(T document) {
            K id = schema.idOf(document);
            if (documentIds.containsKey(id)) {
                throw new IllegalStateException("document id already exists: " + id);
            }
            if (nextDocId < 0) {
                throw new IllegalStateException("internal document id space is exhausted");
            }
            int docId = nextDocId++;
            snapshots.add(docId, document);
            documentIds.put(id, docId);
        }

        private void update(T document) {
            K id = schema.idOf(document);
            Integer docId = documentIds.get(id);
            if (docId == null) {
                throw new IllegalStateException("document id does not exist: " + id);
            }
            snapshots.update(docId, document);
        }

        private void remove(K id) {
            Integer docId = documentIds.remove(Objects.requireNonNull(id, "id"));
            if (docId != null) {
                snapshots.remove(docId);
            }
        }

        private PublishedState<K, T> build() {
            return new PublishedState<>(snapshots.build(), documentIds, nextDocId);
        }
    }

    private record PublishedState<K, T>(
            SearchSnapshot<T> snapshot,
            Map<K, Integer> documentIds,
            int nextDocId
    ) {
        private PublishedState {
            Objects.requireNonNull(snapshot, "snapshot");
            documentIds = Map.copyOf(documentIds);
        }
    }
}
