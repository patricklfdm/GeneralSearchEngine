package org.example.generalsearch.engine;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import org.example.generalsearch.engine.mutation.CreateIndexTask;
import org.example.generalsearch.engine.mutation.DropIndexTask;
import org.example.generalsearch.engine.mutation.InstallIndexTask;
import org.example.generalsearch.engine.mutation.MutationTask;
import org.example.generalsearch.engine.mutation.SearchMutation;
import org.example.generalsearch.engine.mutation.WriterTask;
import org.example.generalsearch.engine.metrics.IndexBuildFailure;
import org.example.generalsearch.engine.metrics.IndexBuildMetrics;
import org.example.generalsearch.engine.metrics.SearchEngineMetrics;
import org.example.generalsearch.index.IndexBuilder;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.IndexRegistry;
import org.example.generalsearch.index.IndexSnapshot;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.query.SnapshotSearcher;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.SearchSchema;
import org.example.generalsearch.storage.SearchSnapshot;
import org.example.generalsearch.storage.SearchSnapshotBuilder;

public final class SnapshotSearchEngine<K, T> implements SearchEngine<K, T> {
    private final SearchSchema<T, K> schema;
    private final AtomicReference<PublishedState<K, T>> current;
    private final AtomicReference<WriterMetrics> writerMetrics =
            new AtomicReference<>(WriterMetrics.empty());
    private final AtomicLong rejectedMutations = new AtomicLong();
    private final BlockingQueue<WriterTask<K, T>> queue;
    private final SnapshotEngineConfig config;
    private final SnapshotSearcher<T> searcher;
    private final ExecutorService indexBuildExecutor;
    private final Thread writerThread;
    private final Object lifecycleMonitor = new Object();

    // Accessed only by the writer thread.
    private final Map<Long, PendingIndexBuild<T>> pendingIndexBuilds = new HashMap<>();
    private final List<VersionedChange<T>> mutationJournal = new ArrayList<>();
    private long nextIndexBuildId;
    private long successfulMutations;
    private long failedMutations;
    private long indexBuildsStarted;
    private long indexBuildsSucceeded;
    private long indexBuildsFailed;
    private long indexBuildsCancelled;
    private Optional<Duration> lastSuccessfulIndexBuildDuration = Optional.empty();
    private Optional<IndexBuildFailure> lastIndexBuildFailure = Optional.empty();
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
        validateIndexDefinitions(indexDefinitions);
        SearchSnapshot<T> emptySnapshot = new SearchSnapshot<>(indexDefinitions);
        this.current = new AtomicReference<>(
                new PublishedState<>(emptySnapshot, Map.of(), 0));
        this.queue = new LinkedBlockingQueue<>(config.queueCapacity());
        this.searcher = new SnapshotSearcher<>();
        this.indexBuildExecutor = Executors.newSingleThreadExecutor(task -> {
            Thread thread = new Thread(
                    task,
                    "snapshot-index-builder-" + schema.documentType().getSimpleName()
            );
            thread.setDaemon(true);
            return thread;
        });
        this.writerThread = new Thread(
                this::writerLoop,
                "snapshot-search-writer-" + schema.documentType().getSimpleName()
        );
        this.writerThread.start();
    }

    @Override
    public CompletableFuture<Void> add(T document) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        return submit(new MutationTask<>(SearchMutation.add(document), completion));
    }

    @Override
    public CompletableFuture<Void> update(T document) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        return submit(new MutationTask<>(SearchMutation.update(document), completion));
    }

    @Override
    public CompletableFuture<Void> remove(K id) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        return submit(new MutationTask<>(SearchMutation.remove(id), completion));
    }

    @Override
    public CompletableFuture<Void> createIndex(IndexDefinition<T> definition) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        return submit(new CreateIndexTask<>(definition, completion));
    }

    @Override
    public CompletableFuture<Void> dropIndex(String fieldName) {
        CompletableFuture<Void> completion = new CompletableFuture<>();
        return submit(new DropIndexTask<>(fieldName, completion));
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

    @Override
    public SearchEngineMetrics metrics() {
        PublishedState<K, T> state = current.get();
        WriterMetrics writer = writerMetrics.get();
        long observedAt = System.nanoTime();
        List<IndexBuildMetrics> activeBuilds = writer.activeIndexBuilds().stream()
                .map(build -> new IndexBuildMetrics(
                        build.buildId(),
                        build.fieldName(),
                        build.indexType(),
                        build.baseSnapshotVersion(),
                        elapsed(build.startedNanos(), observedAt)))
                .toList();
        return new SearchEngineMetrics(
                state.snapshot().version(),
                state.snapshot().activeDocuments().cardinality(),
                state.snapshot().indexes().indexes().size(),
                queue.size(),
                config.queueCapacity(),
                writer.mutationJournalLength(),
                writer.successfulMutations(),
                writer.failedMutations() + rejectedMutations.get(),
                writer.indexBuildsStarted(),
                writer.indexBuildsSucceeded(),
                writer.indexBuildsFailed(),
                writer.indexBuildsCancelled(),
                accepting,
                writer.lastSuccessfulIndexBuildDuration(),
                writer.lastIndexBuildFailure(),
                activeBuilds
        );
    }

    SearchSnapshot<T> snapshotForTesting() {
        return current.get().snapshot();
    }

    Integer internalDocIdForTesting(K id) {
        return current.get().documentIds().get(id);
    }

    private CompletableFuture<Void> submit(WriterTask<K, T> task) {
        synchronized (lifecycleMonitor) {
            if (!accepting) {
                task.completion().completeExceptionally(
                        new IllegalStateException("engine is closed"));
                recordRejectedMutation(task);
            } else if (!queue.offer(task)) {
                task.completion().completeExceptionally(
                        new RejectedExecutionException("writer queue is full"));
                recordRejectedMutation(task);
            }
        }
        return task.completion();
    }

    private void recordRejectedMutation(WriterTask<K, T> task) {
        if (task instanceof MutationTask<?, ?>) {
            rejectedMutations.incrementAndGet();
        }
    }

    private void writerLoop() {
        WriterTask<K, T> deferred = null;
        try {
            while (accepting
                    || deferred != null
                    || !queue.isEmpty()
                    || !pendingIndexBuilds.isEmpty()) {
                WriterTask<K, T> task;
                if (deferred != null) {
                    task = deferred;
                    deferred = null;
                } else {
                    try {
                        task = queue.poll(100, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException interrupted) {
                        if (accepting) {
                            Thread.currentThread().interrupt();
                            stopAfterFailure(interrupted);
                            return;
                        }
                        continue;
                    }
                }
                if (task == null) {
                    continue;
                }

                if (task instanceof MutationTask<?, ?>) {
                    CollectedBatch<K, T> collected = collectBatch(asMutationTask(task));
                    deferred = collected.deferred();
                    try {
                        processBatch(collected.mutations());
                    } catch (Throwable failure) {
                        collected.mutations().forEach(mutation -> {
                            if (mutation.completion().completeExceptionally(failure)) {
                                failedMutations++;
                            }
                        });
                        publishWriterMetrics();
                        stopAfterFailure(failure);
                        return;
                    }
                } else {
                    processControlTask(task);
                }
            }
        } catch (Throwable failure) {
            stopAfterFailure(failure);
        } finally {
            indexBuildExecutor.shutdown();
        }
    }

    private CollectedBatch<K, T> collectBatch(MutationTask<K, T> first) {
        List<MutationTask<K, T>> batch = new ArrayList<>(config.maxBatchSize());
        batch.add(first);
        WriterTask<K, T> deferred = null;
        long deadline = System.nanoTime() + config.maxBatchWait().toNanos();
        while (batch.size() < config.maxBatchSize()) {
            WriterTask<K, T> next = queue.poll();
            if (next == null) {
                long remaining = deadline - System.nanoTime();
                if (remaining <= 0) {
                    break;
                }
                try {
                    next = queue.poll(remaining, TimeUnit.NANOSECONDS);
                } catch (InterruptedException interrupted) {
                    break;
                }
            }
            if (next == null) {
                break;
            }
            if (next instanceof MutationTask<?, ?>) {
                batch.add(asMutationTask(next));
            } else {
                deferred = next;
                break;
            }
        }
        return new CollectedBatch<>(List.copyOf(batch), deferred);
    }

    private void processBatch(List<MutationTask<K, T>> batch) {
        BatchState state = new BatchState(current.get());
        List<MutationTask<K, T>> successful = new ArrayList<>(batch.size());
        List<IndexChange<T>> changes = new ArrayList<>(batch.size());
        for (MutationTask<K, T> task : batch) {
            try {
                IndexChange<T> change = apply(state, task.mutation());
                successful.add(task);
                if (change != null) {
                    changes.add(change);
                }
            } catch (RuntimeException failure) {
                task.completion().completeExceptionally(failure);
                failedMutations++;
            }
        }
        if (successful.isEmpty()) {
            publishWriterMetrics();
            return;
        }

        PublishedState<K, T> published = state.build();
        if (!pendingIndexBuilds.isEmpty()) {
            long version = published.snapshot().version();
            changes.forEach(change ->
                    mutationJournal.add(new VersionedChange<>(version, change)));
        }
        current.set(published);
        successfulMutations += successful.size();
        publishWriterMetrics();
        successful.forEach(task -> task.completion().complete(null));
    }

    private IndexChange<T> apply(BatchState state, SearchMutation<K, T> mutation) {
        return switch (mutation.type()) {
            case ADD -> state.add(mutation.document());
            case UPDATE -> state.update(mutation.document());
            case REMOVE -> state.remove(mutation.id());
        };
    }

    private void processControlTask(WriterTask<K, T> task) {
        try {
            if (task instanceof CreateIndexTask<?, ?>) {
                processCreateIndex(asCreateIndexTask(task));
            } else if (task instanceof DropIndexTask<?, ?>) {
                processDropIndex(asDropIndexTask(task));
            } else if (task instanceof InstallIndexTask<?, ?>) {
                processInstallIndex(asInstallIndexTask(task));
            } else {
                task.completion().completeExceptionally(
                        new IllegalArgumentException("unknown writer task: " + task));
            }
        } catch (RuntimeException failure) {
            task.completion().completeExceptionally(failure);
        }
    }

    private void processCreateIndex(CreateIndexTask<K, T> task) {
        IndexDefinition<T> definition = task.definition();
        Field<T, ?> requestedField = Objects.requireNonNull(
                definition.field(),
                "index field"
        );
        Field<T, ?> schemaField = schema.requireField(requestedField.name());
        if (schemaField != requestedField) {
            throw new IllegalArgumentException(
                    "dynamic indexes require the canonical schema field: "
                            + requestedField.name());
        }

        IndexSnapshot<T> emptyIndex = Objects.requireNonNull(
                definition.createEmpty(),
                "definition.createEmpty()"
        );
        if (emptyIndex.field() != requestedField) {
            throw new IllegalArgumentException(
                    "index definition returned a snapshot for a different field");
        }
        if (current.get().snapshot().indexes()
                .contains(requestedField, emptyIndex.getClass())) {
            throw new IllegalStateException(
                    "index already exists for field: " + requestedField.name());
        }
        boolean alreadyBuilding = pendingIndexBuilds.values().stream().anyMatch(pending ->
                pending.field() == requestedField
                        && pending.indexType() == emptyIndex.getClass());
        if (alreadyBuilding) {
            throw new IllegalStateException(
                    "index build is already in progress for field: "
                            + requestedField.name());
        }

        if (nextIndexBuildId < 0) {
            throw new IllegalStateException("index build id space is exhausted");
        }
        long buildId = nextIndexBuildId++;
        SearchSnapshot<T> baseSnapshot = current.get().snapshot();
        PendingIndexBuild<T> pending = new PendingIndexBuild<>(
                buildId,
                baseSnapshot.version(),
                requestedField,
                emptyIndex.getClass(),
                System.nanoTime(),
                task.completion()
        );
        pendingIndexBuilds.put(buildId, pending);
        try {
            indexBuildExecutor.execute(() -> buildIndex(
                    buildId,
                    baseSnapshot,
                    emptyIndex,
                    task.completion()
            ));
            indexBuildsStarted++;
            publishWriterMetrics();
        } catch (RejectedExecutionException failure) {
            pendingIndexBuilds.remove(buildId);
            pruneMutationJournal();
            publishWriterMetrics();
            throw failure;
        }
    }

    private void buildIndex(
            long buildId,
            SearchSnapshot<T> baseSnapshot,
            IndexSnapshot<T> emptyIndex,
            CompletableFuture<Void> completion
    ) {
        IndexSnapshot<T> built = null;
        Throwable failure = null;
        try {
            IndexBuilder<T> builder = emptyIndex.toBuilder();
            baseSnapshot.activeDocuments().forEachSetBit(docId -> {
                T document = baseSnapshot.get(docId);
                if (document != null) {
                    builder.add(docId, document);
                }
            });
            built = builder.build();
        } catch (Throwable buildFailure) {
            failure = buildFailure;
        }

        InstallIndexTask<K, T> install = new InstallIndexTask<>(
                buildId,
                built,
                failure,
                completion
        );
        boolean interrupted = false;
        while (!indexBuildExecutor.isShutdown()) {
            try {
                if (queue.offer(install, 100, TimeUnit.MILLISECONDS)) {
                    break;
                }
            } catch (InterruptedException ignored) {
                interrupted = true;
            }
        }
        if (interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    private void validateIndexDefinitions(
            Collection<? extends IndexDefinition<T>> definitions
    ) {
        Objects.requireNonNull(definitions, "indexDefinitions");
        for (IndexDefinition<T> definition : definitions) {
            IndexDefinition<T> checked = Objects.requireNonNull(definition, "definition");
            Field<T, ?> field = Objects.requireNonNull(checked.field(), "index field");
            if (schema.requireField(field.name()) != field) {
                throw new IllegalArgumentException(
                        "indexes require canonical schema fields: " + field.name());
            }
        }
    }

    private void processInstallIndex(InstallIndexTask<K, T> task) {
        PendingIndexBuild<T> pending = pendingIndexBuilds.get(task.buildId());
        if (pending == null || pending.completion() != task.completion()) {
            return;
        }
        if (task.failure() != null) {
            pendingIndexBuilds.remove(task.buildId());
            recordIndexBuildFailure(pending, task.failure());
            pruneMutationJournal();
            publishWriterMetrics();
            pending.completion().completeExceptionally(task.failure());
            return;
        }

        try {
            IndexBuilder<T> replay = task.index().toBuilder();
            for (VersionedChange<T> versioned : mutationJournal) {
                if (versioned.version() > pending.baseVersion()) {
                    apply(replay, versioned.change());
                }
            }
            IndexSnapshot<T> caughtUp = replay.build();
            PublishedState<K, T> state = current.get();
            IndexRegistry<T> indexes = state.snapshot().indexes().withIndex(caughtUp);
            SearchSnapshot<T> snapshot = state.snapshot().withIndexes(indexes);
            current.set(new PublishedState<>(
                    snapshot,
                    state.documentIds(),
                    state.nextDocId()
            ));
            pendingIndexBuilds.remove(task.buildId());
            indexBuildsSucceeded++;
            lastSuccessfulIndexBuildDuration = Optional.of(
                    elapsed(pending.startedNanos(), System.nanoTime()));
            pruneMutationJournal();
            publishWriterMetrics();
            pending.completion().complete(null);
        } catch (RuntimeException failure) {
            pendingIndexBuilds.remove(task.buildId());
            recordIndexBuildFailure(pending, failure);
            pruneMutationJournal();
            publishWriterMetrics();
            pending.completion().completeExceptionally(failure);
        }
    }

    private void apply(IndexBuilder<T> builder, IndexChange<T> change) {
        if (change.oldDocument() == null) {
            builder.add(change.docId(), change.newDocument());
        } else if (change.newDocument() == null) {
            builder.remove(change.docId(), change.oldDocument());
        } else {
            builder.update(
                    change.docId(),
                    change.oldDocument(),
                    change.newDocument()
            );
        }
    }

    private void processDropIndex(DropIndexTask<K, T> task) {
        Field<T, ?> field = schema.requireField(task.fieldName());
        Iterator<PendingIndexBuild<T>> pending = pendingIndexBuilds.values().iterator();
        while (pending.hasNext()) {
            PendingIndexBuild<T> build = pending.next();
            if (build.field() == field) {
                pending.remove();
                indexBuildsCancelled++;
                build.completion().completeExceptionally(new IllegalStateException(
                        "index build was cancelled by dropIndex: " + task.fieldName()));
            }
        }

        PublishedState<K, T> state = current.get();
        IndexRegistry<T> indexes = state.snapshot().indexes().withoutIndexes(field);
        if (indexes != state.snapshot().indexes()) {
            SearchSnapshot<T> snapshot = state.snapshot().withIndexes(indexes);
            current.set(new PublishedState<>(
                    snapshot,
                    state.documentIds(),
                    state.nextDocId()
            ));
        }
        pruneMutationJournal();
        publishWriterMetrics();
        task.completion().complete(null);
    }

    private void recordIndexBuildFailure(
            PendingIndexBuild<T> pending,
            Throwable failure
    ) {
        Duration duration = elapsed(pending.startedNanos(), System.nanoTime());
        indexBuildsFailed++;
        lastIndexBuildFailure = Optional.of(new IndexBuildFailure(
                pending.id(),
                pending.field().name(),
                pending.indexType().getName(),
                failure.getClass().getName(),
                Optional.ofNullable(failure.getMessage()),
                duration
        ));
    }

    private void publishWriterMetrics() {
        List<ActiveIndexBuild> activeBuilds = pendingIndexBuilds.values().stream()
                .sorted(Comparator.comparingLong(PendingIndexBuild::id))
                .map(pending -> new ActiveIndexBuild(
                        pending.id(),
                        pending.field().name(),
                        pending.indexType().getName(),
                        pending.baseVersion(),
                        pending.startedNanos()))
                .toList();
        writerMetrics.set(new WriterMetrics(
                mutationJournal.size(),
                successfulMutations,
                failedMutations,
                indexBuildsStarted,
                indexBuildsSucceeded,
                indexBuildsFailed,
                indexBuildsCancelled,
                lastSuccessfulIndexBuildDuration,
                lastIndexBuildFailure,
                activeBuilds
        ));
    }

    private static Duration elapsed(long startedNanos, long finishedNanos) {
        return Duration.ofNanos(Math.max(0, finishedNanos - startedNanos));
    }

    private void pruneMutationJournal() {
        if (pendingIndexBuilds.isEmpty()) {
            mutationJournal.clear();
            return;
        }
        long oldestRequiredVersion = pendingIndexBuilds.values().stream()
                .mapToLong(PendingIndexBuild::baseVersion)
                .min()
                .orElseThrow();
        mutationJournal.removeIf(change -> change.version() <= oldestRequiredVersion);
    }

    private void failPending(Throwable failure) {
        WriterTask<K, T> task;
        while ((task = queue.poll()) != null) {
            if (task.completion().completeExceptionally(failure)
                    && task instanceof MutationTask<?, ?>) {
                failedMutations++;
            }
        }
        pendingIndexBuilds.values().forEach(pending -> {
            recordIndexBuildFailure(pending, failure);
            pending.completion().completeExceptionally(failure);
        });
        pendingIndexBuilds.clear();
        mutationJournal.clear();
        publishWriterMetrics();
    }

    private void stopAfterFailure(Throwable failure) {
        synchronized (lifecycleMonitor) {
            accepting = false;
        }
        failPending(failure);
        indexBuildExecutor.shutdownNow();
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
        indexBuildExecutor.shutdownNow();
        if (interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    @SuppressWarnings("unchecked")
    private MutationTask<K, T> asMutationTask(WriterTask<K, T> task) {
        return (MutationTask<K, T>) task;
    }

    @SuppressWarnings("unchecked")
    private CreateIndexTask<K, T> asCreateIndexTask(WriterTask<K, T> task) {
        return (CreateIndexTask<K, T>) task;
    }

    @SuppressWarnings("unchecked")
    private DropIndexTask<K, T> asDropIndexTask(WriterTask<K, T> task) {
        return (DropIndexTask<K, T>) task;
    }

    @SuppressWarnings("unchecked")
    private InstallIndexTask<K, T> asInstallIndexTask(WriterTask<K, T> task) {
        return (InstallIndexTask<K, T>) task;
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

        private IndexChange<T> add(T document) {
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
            return new IndexChange<>(docId, null, document);
        }

        private IndexChange<T> update(T document) {
            K id = schema.idOf(document);
            Integer docId = documentIds.get(id);
            if (docId == null) {
                throw new IllegalStateException("document id does not exist: " + id);
            }
            T oldDocument = Objects.requireNonNull(snapshots.get(docId));
            snapshots.update(docId, document);
            return new IndexChange<>(docId, oldDocument, document);
        }

        private IndexChange<T> remove(K id) {
            Integer docId = documentIds.remove(Objects.requireNonNull(id, "id"));
            if (docId == null) {
                return null;
            }
            T oldDocument = Objects.requireNonNull(snapshots.get(docId));
            snapshots.remove(docId);
            return new IndexChange<>(docId, oldDocument, null);
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

    private record CollectedBatch<K, T>(
            List<MutationTask<K, T>> mutations,
            WriterTask<K, T> deferred
    ) {}

    private record IndexChange<T>(int docId, T oldDocument, T newDocument) {
        private IndexChange {
            if (docId < 0) {
                throw new IllegalArgumentException("docId must not be negative");
            }
            if (oldDocument == null && newDocument == null) {
                throw new IllegalArgumentException("index change must contain a document");
            }
        }
    }

    private record VersionedChange<T>(long version, IndexChange<T> change) {}

    private record PendingIndexBuild<T>(
            long id,
            long baseVersion,
            Field<T, ?> field,
            Class<?> indexType,
            long startedNanos,
            CompletableFuture<Void> completion
    ) {}

    private record ActiveIndexBuild(
            long buildId,
            String fieldName,
            String indexType,
            long baseSnapshotVersion,
            long startedNanos
    ) {}

    private record WriterMetrics(
            int mutationJournalLength,
            long successfulMutations,
            long failedMutations,
            long indexBuildsStarted,
            long indexBuildsSucceeded,
            long indexBuildsFailed,
            long indexBuildsCancelled,
            Optional<Duration> lastSuccessfulIndexBuildDuration,
            Optional<IndexBuildFailure> lastIndexBuildFailure,
            List<ActiveIndexBuild> activeIndexBuilds
    ) {
        private WriterMetrics {
            activeIndexBuilds = List.copyOf(activeIndexBuilds);
        }

        private static WriterMetrics empty() {
            return new WriterMetrics(
                    0, 0, 0, 0, 0, 0, 0,
                    Optional.empty(), Optional.empty(), List.of());
        }
    }
}
