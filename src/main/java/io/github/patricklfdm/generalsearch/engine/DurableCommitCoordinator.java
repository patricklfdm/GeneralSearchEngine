package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.CompletionException;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.durability.DurabilityMetrics;
import io.github.patricklfdm.generalsearch.durability.DurabilityStatus;
import io.github.patricklfdm.generalsearch.durability.RecoverySource;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

final class DurableCommitCoordinator<K, T> implements AutoCloseable {
    private static final Pattern IDENTITY = Pattern.compile(
            "[a-z0-9][a-z0-9._-]{0,127}");
    private static final byte ADD = 1;
    private static final byte UPDATE = 2;
    private static final byte REMOVE = 3;

    private final DurableStorageConfig<K, T> config;
    private final DurableCodec<K, T> codec;
    private final String codecIdentity;
    private final int codecVersion;
    private final SearchSchema<T, K> schema;
    private final DurableStorageOwner storage;
    private final AtomicReference<DurabilityMetrics> metrics;
    private final ExecutorService checkpointExecutor;
    private final ExecutorService backupExecutor;
    private final DurableRecovery.Result<K, T> recoveredState;
    private final RecoverySource recoverySource;
    private final long replayedRecords;
    private final Duration recoveryDuration;
    private final Duration indexRebuildDuration;
    private final long truncatedTailBytes;
    private final long storageOpenNanos;
    private final long checkpointLoadNanos;
    private final long replayAndRebuildNanos;
    private volatile long checkpointSequence;
    private Optional<DurabilityException.Reason> lastCheckpointFailure =
            Optional.empty();
    private CompletableFuture<Void> activeCheckpoint;
    private CompletableFuture<DurableBackupResult> activeBackup;
    private long allocatedSequence;
    private long publishedSequence;
    private long forceGroups;
    private long forcedUnits;
    private int maximumForceGroupSize;
    private long walAppendForceNanos;
    private boolean terminal;
    private boolean closed;

    private DurableCommitCoordinator(
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            DurableStorageOwner.OpenResult opened,
            DurableRecovery.Result<K, T> recoveredState,
            Duration totalRecoveryDuration,
            long storageOpenNanos,
            long checkpointLoadNanos,
            long replayAndRebuildNanos,
            String codecIdentity,
            int codecVersion
    ) {
        this.config = config;
        this.codec = config.codec();
        this.codecIdentity = codecIdentity;
        this.codecVersion = codecVersion;
        this.schema = schema;
        this.storage = opened.owner();
        this.recoveredState = recoveredState;
        checkpointSequence = opened.manifest() == null
                ? 0L
                : opened.manifest().checkpointSequence();
        recoverySource = opened.fresh()
                ? RecoverySource.FRESH
                : opened.manifest() == null
                        ? RecoverySource.WAL_ONLY
                        : recoveredState.replayedRecords() == 0
                                ? RecoverySource.CHECKPOINT_ONLY
                                : RecoverySource.CHECKPOINT_AND_WAL;
        replayedRecords = opened.fresh() ? 0 : recoveredState.replayedRecords();
        recoveryDuration = opened.fresh()
                ? Duration.ZERO
                : totalRecoveryDuration;
        indexRebuildDuration = opened.fresh()
                ? Duration.ZERO
                : recoveredState.indexRebuildDuration();
        truncatedTailBytes = opened.truncatedBytes();
        this.storageOpenNanos = storageOpenNanos;
        this.checkpointLoadNanos = checkpointLoadNanos;
        this.replayAndRebuildNanos = replayAndRebuildNanos;
        allocatedSequence = recoveredState.sequence();
        publishedSequence = recoveredState.sequence();
        checkpointExecutor = Executors.newSingleThreadExecutor(task -> {
            Thread thread = new Thread(task, "gse-durable-checkpoint");
            thread.setDaemon(true);
            return thread;
        });
        backupExecutor = Executors.newSingleThreadExecutor(task -> {
            Thread thread = new Thread(task, "gse-durable-backup");
            thread.setDaemon(true);
            return thread;
        });
        metrics = new AtomicReference<>(new DurabilityMetrics(
                DurabilityStatus.OPEN,
                publishedSequence,
                checkpointSequence,
                storage.wal().generation(),
                storage.wal().records(),
                storage.wal().position(),
                storage.retainedBytes(),
                recoverySource,
                replayedRecords,
                recoveryDuration,
                indexRebuildDuration,
                lastCheckpointFailure));
    }

    private static DurabilityException.Reason reasonOf(Throwable failure) {
        Throwable candidate = failure;
        while (candidate instanceof CompletionException
                && candidate.getCause() != null) {
            candidate = candidate.getCause();
        }
        return candidate instanceof DurabilityException durability
                ? durability.reason()
                : DurabilityException.Reason.IO_FAILURE;
    }

    static <K, T> DurableCommitCoordinator<K, T> open(
            DurableStorageConfig<K, T> config,
            SnapshotEngineConfig engineConfig,
            SearchSchema<T, K> schema,
            Collection<? extends IndexDefinition<T>> startupDefinitions
    ) {
        Objects.requireNonNull(config, "storageConfig");
        Objects.requireNonNull(engineConfig, "engineConfig");
        Objects.requireNonNull(schema, "schema");
        if (config.maxBulkElements() < engineConfig.maxBatchSize()) {
            throw new IllegalArgumentException(
                    "maxBulkElements must be at least SnapshotEngineConfig.maxBatchSize");
        }
        List<DurableIndexDescriptor> indexes = startupDefinitions.stream()
                .map(DurableIndexDescriptor::from)
                .toList();
        if (new java.util.HashSet<>(indexes).size() != indexes.size()) {
            throw new DurabilityException(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "durable startup index configuration contains a duplicate");
        }
        String codecId;
        int codecVersion;
        try {
            codecId = config.codec().codecId();
            codecVersion = config.codec().codecVersion();
        } catch (RuntimeException failure) {
            throw codecFailure("codec identity lookup failed", failure);
        }
        if (codecId == null || !IDENTITY.matcher(codecId).matches()
                || codecVersion < 0) {
            throw codecFailure("codec identity changed after configuration", null);
        }
        long recoveryStarted = System.nanoTime();
        long storageOpenStarted = System.nanoTime();
        DurableStorageOwner.OpenResult opened = DurableStorageOwner.open(
                config,
                codecId,
                codecVersion,
                indexes);
        long storageOpenNanos = elapsedSince(storageOpenStarted);
        try {
            long checkpointLoadStarted = System.nanoTime();
            DurableCheckpoint.Loaded<K, T> checkpoint = opened.manifest() == null
                    ? null
                    : DurableCheckpoint.read(
                            opened.owner().directory().resolve(
                                    opened.manifest().checkpointFile()),
                            config,
                            schema,
                            opened.owner().format(),
                            opened.owner().historyId(),
                            opened.manifest());
            long checkpointLoadNanos = elapsedSince(checkpointLoadStarted);
            long replayStarted = System.nanoTime();
            DurableRecovery.Result<K, T> recovered = DurableRecovery.replay(
                    config,
                    schema,
                    indexes,
                    checkpoint,
                    opened.wals(),
                    !opened.fresh());
            long replayAndRebuildNanos = elapsedSince(replayStarted);
            opened.owner().finishRecovery();
            return new DurableCommitCoordinator<>(
                    config,
                    schema,
                    opened,
                    recovered,
                    Duration.ofNanos(Math.max(
                            0L, System.nanoTime() - recoveryStarted)),
                    storageOpenNanos,
                    checkpointLoadNanos,
                    replayAndRebuildNanos,
                    codecId,
                    codecVersion);
        } catch (IOException ioFailure) {
            DurabilityException failure = new DurabilityException(
                    DurabilityException.Reason.STORAGE_ACCESS,
                    "checkpoint recovery read failed",
                    ioFailure);
            try {
                opened.owner().close();
            } catch (RuntimeException closeFailure) {
                failure.addSuppressed(closeFailure);
            }
            throw failure;
        } catch (RuntimeException | Error failure) {
            try {
                opened.owner().close();
            } catch (RuntimeException closeFailure) {
                failure.addSuppressed(closeFailure);
            }
            throw failure;
        }
    }

    PreparedMutation prepareMutation(MutationKind kind, K id, T document) {
        Objects.requireNonNull(kind, "kind");
        Objects.requireNonNull(id, "id");
        byte[] key = canonicalKey(id);
        byte[] encodedDocument = null;
        if (kind != MutationKind.REMOVE) {
            Objects.requireNonNull(document, "document");
            encodedDocument = canonicalDocument(id, document);
        }
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                output.writeByte(switch (kind) {
                    case ADD -> ADD;
                    case UPDATE -> UPDATE;
                    case REMOVE -> REMOVE;
                });
                writeBytes(output, key);
                if (encodedDocument == null) {
                    output.writeInt(-1);
                } else {
                    writeBytes(output, encodedDocument);
                }
            }
            byte[] payload = bytes.toByteArray();
            requireFrameBound(payload.length);
            return new PreparedMutation(payload);
        } catch (IOException impossible) {
            throw new AssertionError(impossible);
        }
    }

    PreparedUnit single(PreparedMutation mutation) {
        return new PreparedUnit(DurableWal.SINGLE, mutation.payload());
    }

    PreparedUnit bulk(List<PreparedMutation> mutations) {
        List<PreparedMutation> copied = List.copyOf(mutations);
        if (copied.isEmpty()) {
            throw new IllegalArgumentException("empty bulk has no durable unit");
        }
        if (copied.size() > config.maxBulkElements()) {
            throw new DurabilityException(
                    DurabilityException.Reason.CAPACITY_EXCEEDED,
                    "bulk exceeds the configured persisted element limit");
        }
        try {
            int payloadBytes = Integer.BYTES;
            for (PreparedMutation mutation : copied) {
                payloadBytes = Math.addExact(payloadBytes, mutation.payload().length);
                requireFrameBound(payloadBytes);
            }
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(payloadBytes);
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                output.writeInt(copied.size());
                for (PreparedMutation mutation : copied) {
                    output.write(mutation.payload());
                }
            }
            return new PreparedUnit(DurableWal.BULK, bytes.toByteArray());
        } catch (ArithmeticException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.CAPACITY_EXCEEDED,
                    "encoded bulk size overflowed",
                    failure);
        } catch (IOException impossible) {
            throw new AssertionError(impossible);
        }
    }

    PreparedUnit createIndex(IndexDefinition<T> definition) {
        DurableIndexDescriptor descriptor = DurableIndexDescriptor.from(definition);
        return new PreparedUnit(
                DurableWal.INDEX_CREATE,
                encodeIndexDescriptor(descriptor));
    }

    PreparedUnit dropIndex(String fieldName) {
        return new PreparedUnit(
                DurableWal.INDEX_DROP,
                encodeString(Objects.requireNonNull(fieldName, "fieldName")));
    }

    synchronized CommitGroup commit(List<PreparedUnit> units, int liveDocuments) {
        List<PreparedUnit> copied = List.copyOf(units);
        if (copied.isEmpty()) {
            throw new IllegalArgumentException("commit group must not be empty");
        }
        ensureWritable();
        if (liveDocuments < 0 || liveDocuments > config.maxDocuments()) {
            capacityFailure("candidate exceeds the configured live-document limit");
        }
        long additionalBytes = 0;
        for (PreparedUnit unit : copied) {
            requireFrameBound(unit.payload().length);
            additionalBytes = Math.addExact(
                    additionalBytes,
                    DurableWal.FRAME_HEADER_BYTES
                            + (long) unit.payload().length
                            + DurableWal.FRAME_TRAILER_BYTES);
        }
        long retained = storage.retainedBytes();
        if (additionalBytes > config.maxRetainedBytes()
                - retained
                - DurableWal.GENERATION_HEADER_BYTES) {
            capacityFailure("commit group exceeds the configured retained-byte limit");
        }

        DurableCrashHooks.reach("v4-wal-before-sequence-v1");
        long first;
        long last;
        try {
            first = Math.incrementExact(allocatedSequence);
            last = Math.addExact(first, copied.size() - 1L);
        } catch (ArithmeticException failure) {
            terminal = true;
            publishMetrics(DurabilityStatus.FAILED);
            throw new DurabilityException(
                    DurabilityException.Reason.SEQUENCE_EXHAUSTED,
                    "durable sequence space is exhausted",
                    failure);
        }
        allocatedSequence = last;
        List<SequencedUnit> sequenced = new ArrayList<>(copied.size());
        long sequence = first;
        for (PreparedUnit unit : copied) {
            sequenced.add(new SequencedUnit(sequence++, unit));
        }
        DurableCrashHooks.reach("v4-wal-after-sequence-v1");
        try {
            long appendStarted = System.nanoTime();
            DurableWal.AppendResult append = storage.wal().appendAndForce(sequenced);
            long appendNanos = elapsedSince(appendStarted);
            forceGroups = saturatedAdd(forceGroups, 1L);
            forcedUnits = saturatedAdd(forcedUnits, copied.size());
            maximumForceGroupSize = Math.max(
                    maximumForceGroupSize, copied.size());
            walAppendForceNanos = saturatedAdd(
                    walAppendForceNanos, appendNanos);
            publishMetrics(
                    DurabilityStatus.OPEN,
                    publishedSequence,
                    append.records(),
                    append.walBytes(),
                    storage.retainedBytes());
            return new CommitGroup(first, last, copied.size());
        } catch (DurabilityException failure) {
            terminal = true;
            publishMetrics(DurabilityStatus.FAILED);
            throw failure;
        }
    }

    void beforePublication() {
        DurableCrashHooks.reach("v4-wal-before-publication-v1");
    }

    synchronized void published(CommitGroup group) {
        if (group.firstSequence() != publishedSequence + 1
                || group.lastSequence() != allocatedSequence) {
            terminal = true;
            publishMetrics(DurabilityStatus.FAILED);
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "durable publication boundary is inconsistent");
        }
        publishedSequence = group.lastSequence();
        publishMetrics(DurabilityStatus.OPEN);
        DurableCrashHooks.reach("v4-wal-after-publication-v1");
    }

    void beforeFutureCompletion() {
        DurableCrashHooks.reach("v4-wal-before-future-completion-v1");
    }

    synchronized void terminalFailure(Throwable failure) {
        if (!closed) {
            terminal = true;
            publishMetrics(DurabilityStatus.FAILED);
        }
    }

    synchronized boolean isTerminalFailure(Throwable failure) {
        return terminal;
    }

    long currentSequence() {
        return metrics.get().currentSequence();
    }

    DurableRecovery.Result<K, T> recoveredState() {
        return recoveredState;
    }

    long truncatedTailBytes() {
        return truncatedTailBytes;
    }

    void beforeReadyPublication() {
        if (recoverySource != RecoverySource.FRESH) {
            DurableCrashHooks.reach(
                    "v4-recovery-before-ready-publication-v1");
        }
    }

    DurabilityMetrics metrics() {
        return metrics.get();
    }

    synchronized DurablePerformanceSnapshot performanceSnapshot() {
        return new DurablePerformanceSnapshot(
                forceGroups,
                forcedUnits,
                maximumForceGroupSize,
                walAppendForceNanos,
                storageOpenNanos,
                checkpointLoadNanos,
                replayAndRebuildNanos);
    }

    private static long elapsedSince(long started) {
        return Math.max(0L, System.nanoTime() - started);
    }

    private static long saturatedAdd(long left, long right) {
        if (right > Long.MAX_VALUE - left) {
            return Long.MAX_VALUE;
        }
        return left + right;
    }

    synchronized boolean checkpointRequired() {
        return !closed
                && !terminal
                && (activeCheckpoint == null || activeCheckpoint.isDone())
                && storage.wal().dataBytes() >= config.checkpointWalBytes();
    }

    void validateBackupRequest(DurableBackupRequest request) {
        DurableBackupWriter.validateTarget(storage.directory(), request);
    }

    synchronized void reserveBackup(
            CompletableFuture<DurableBackupResult> result
    ) {
        Objects.requireNonNull(result, "result");
        if (closed) {
            throw operation(DurableOperationException.Reason.CLOSED, null, null);
        }
        if (activeBackup != null && !activeBackup.isDone()) {
            throw operation(DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                    null, null);
        }
        if (terminal) {
            throw operation(DurableOperationException.Reason.SOURCE_INVALID,
                    publishedSequence, null);
        }
        activeBackup = result;
        result.whenComplete((ignored, failure) -> clearBackup(result));
    }

    private synchronized void clearBackup(
            CompletableFuture<DurableBackupResult> result
    ) {
        if (activeBackup == result) {
            activeBackup = null;
        }
    }

    void rejectBackup(
            CompletableFuture<DurableBackupResult> result,
            Throwable failure
    ) {
        result.completeExceptionally(backupFailure(
                Objects.requireNonNull(failure, "failure"), currentSequence()));
    }

    void startBackup(
            DurableCheckpoint.Capture<K, T> capture,
            DurableBackupRequest request,
            CompletableFuture<DurableBackupResult> result
    ) {
        Objects.requireNonNull(capture, "capture");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(result, "result");
        DurableStorageOwner.GenerationCut cut;
        CompletableFuture<Void> sourceCheckpoint = new CompletableFuture<>();
        synchronized (this) {
            if (activeBackup != result || result.isDone()) {
                return;
            }
            if (closed) {
                result.completeExceptionally(operation(
                        DurableOperationException.Reason.CLOSED,
                        capture.sequence(), null));
                return;
            }
            if (terminal) {
                result.completeExceptionally(operation(
                        DurableOperationException.Reason.SOURCE_INVALID,
                        capture.sequence(), null));
                return;
            }
            if (activeCheckpoint != null && !activeCheckpoint.isDone()) {
                result.completeExceptionally(operation(
                        DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        capture.sequence(), null));
                return;
            }
            if (capture.sequence() != publishedSequence
                    || capture.sequence() != allocatedSequence) {
                result.completeExceptionally(operation(
                        DurableOperationException.Reason.SOURCE_INVALID,
                        capture.sequence(), null));
                return;
            }
            try {
                DurableCrashHooks.reach("v41-backup-before-writer-cut-v1");
                DurableCrashHooks.reach("v41-backup-after-b-selection-v1");
                cut = storage.cutGeneration(
                        backupWalFirstSequence(capture.sequence()),
                        config.maxRetainedBytes());
                DurableCrashHooks.reach("v41-backup-after-wal-cut-v1");
                publishMetrics(DurabilityStatus.OPEN);
                activeCheckpoint = sourceCheckpoint;
                checkpointExecutor.execute(() -> publishBackupCheckpoint(
                        capture, cut, request, result, sourceCheckpoint));
            } catch (RuntimeException failure) {
                terminal = !(failure instanceof DurabilityException durability
                        && durability.reason()
                        == DurabilityException.Reason.CAPACITY_EXCEEDED);
                lastCheckpointFailure = Optional.of(reasonOf(failure));
                publishMetrics(terminal
                        ? DurabilityStatus.FAILED
                        : DurabilityStatus.CAPACITY_BLOCKED);
                result.completeExceptionally(backupFailure(
                        failure, capture.sequence()));
            }
        }
    }

    private void publishBackupCheckpoint(
            DurableCheckpoint.Capture<K, T> capture,
            DurableStorageOwner.GenerationCut cut,
            DurableBackupRequest request,
            CompletableFuture<DurableBackupResult> result,
            CompletableFuture<Void> sourceCheckpoint
    ) {
        DurableStorageOwner.CheckpointPin pin = null;
        try {
            DurableStorageOwner.CheckpointPublication publication =
                    storage.publishCheckpoint(capture, config, schema, cut);
            DurableCrashHooks.reach(
                    "v41-backup-after-source-checkpoint-authority-v1");
            pin = storage.pinCheckpoint(publication.manifest());
            DurableCrashHooks.reach("v41-backup-after-checkpoint-pin-v1");
            synchronized (this) {
                checkpointSequence = publication.manifest().checkpointSequence();
                lastCheckpointFailure = Optional.ofNullable(
                        publication.cleanupFailure());
                activeCheckpoint = null;
                publishMetrics(terminal
                        ? DurabilityStatus.FAILED
                        : DurabilityStatus.OPEN);
            }
            sourceCheckpoint.complete(null);
            DurableStorageOwner.CheckpointPin retainedPin = pin;
            pin = null;
            backupExecutor.execute(() -> writeBackup(
                    publication.manifest(), retainedPin, request, result));
        } catch (DurableStorageOwner.CheckpointFailure wrapper) {
            DurabilityException failure = wrapper.failure();
            synchronized (this) {
                lastCheckpointFailure = Optional.of(failure.reason());
                if (wrapper.manifestReplaced()) {
                    terminal = true;
                }
                activeCheckpoint = null;
                publishMetrics(terminal
                        ? DurabilityStatus.FAILED
                        : DurabilityStatus.OPEN);
            }
            sourceCheckpoint.completeExceptionally(failure);
            result.completeExceptionally(backupFailure(
                    failure, capture.sequence()));
        } catch (RuntimeException failure) {
            synchronized (this) {
                terminal = true;
                lastCheckpointFailure = Optional.of(reasonOf(failure));
                activeCheckpoint = null;
                publishMetrics(DurabilityStatus.FAILED);
            }
            sourceCheckpoint.completeExceptionally(failure);
            result.completeExceptionally(backupFailure(
                    failure, capture.sequence()));
        } finally {
            if (pin != null) {
                pin.close();
            }
        }
    }

    private void writeBackup(
            DurableCheckpoint.Manifest manifest,
            DurableStorageOwner.CheckpointPin pin,
            DurableBackupRequest request,
            CompletableFuture<DurableBackupResult> result
    ) {
        DurableBackupResult completed = null;
        Throwable failure = null;
        try {
            completed = DurableBackupWriter.write(
                    storage.directory(), manifest.checkpointFile(),
                    storage.historyId(), manifest.checkpointSequence(), config,
                    codecIdentity, codecVersion, request);
        } catch (Throwable thrown) {
            failure = thrown;
        } finally {
            try {
                pin.close();
            } catch (Throwable closeFailure) {
                if (failure == null) {
                    failure = closeFailure;
                } else {
                    failure.addSuppressed(closeFailure);
                }
            }
        }
        if (failure == null) {
            result.complete(completed);
        } else {
            result.completeExceptionally(failure instanceof DurableOperationException
                    ? failure
                    : operation(DurableOperationException.Reason.IO_FAILURE,
                            manifest.checkpointSequence(), failure));
        }
    }

    private static DurableOperationException backupFailure(
            Throwable failure,
            long sequence
    ) {
        if (failure instanceof DurableOperationException operation) {
            return operation;
        }
        DurableOperationException.Reason reason =
                failure instanceof DurabilityException durability
                        && durability.reason()
                        == DurabilityException.Reason.CAPACITY_EXCEEDED
                ? DurableOperationException.Reason.CAPACITY_EXCEEDED
                : DurableOperationException.Reason.SOURCE_INVALID;
        return operation(reason, sequence, failure);
    }

    static long backupWalFirstSequence(long sequence) {
        try {
            return Math.incrementExact(sequence);
        } catch (ArithmeticException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.SEQUENCE_EXHAUSTED,
                    sequence,
                    "backup cannot cut a post-checkpoint WAL sequence",
                    failure);
        }
    }

    private static DurableOperationException operation(
            DurableOperationException.Reason reason,
            Long sequence,
            Throwable cause
    ) {
        return new DurableOperationException(reason,
                sequence == null
                        ? java.util.OptionalLong.empty()
                        : java.util.OptionalLong.of(sequence),
                cause);
    }

    synchronized CompletableFuture<Void> checkpoint(
            DurableCheckpoint.Capture<K, T> capture
    ) {
        if (closed) {
            return CompletableFuture.failedFuture(new DurabilityException(
                    DurabilityException.Reason.CLOSED,
                    "durable engine is closed"));
        }
        if (activeCheckpoint != null && !activeCheckpoint.isDone()) {
            return activeCheckpoint;
        }
        if (terminal) {
            return CompletableFuture.failedFuture(new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "durable writer is in terminal failed state"));
        }
        Objects.requireNonNull(capture, "capture");
        if (capture.sequence() != publishedSequence
                || capture.sequence() != allocatedSequence) {
            return CompletableFuture.failedFuture(new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "checkpoint capture is not at the published durable boundary"));
        }

        CompletableFuture<Void> result = new CompletableFuture<>();
        DurableStorageOwner.GenerationCut cut;
        try {
            cut = storage.cutGeneration(
                    Math.incrementExact(capture.sequence()),
                    config.maxRetainedBytes());
            publishMetrics(DurabilityStatus.OPEN);
            activeCheckpoint = result;
            checkpointExecutor.execute(
                    () -> publishCheckpoint(capture, cut, result));
        } catch (RuntimeException failure) {
            terminal = !(failure instanceof DurabilityException durability
                    && durability.reason()
                    == DurabilityException.Reason.CAPACITY_EXCEEDED);
            lastCheckpointFailure = Optional.of(reasonOf(failure));
            publishMetrics(terminal
                    ? DurabilityStatus.FAILED
                    : DurabilityStatus.CAPACITY_BLOCKED);
            result.completeExceptionally(failure);
        }
        return result;
    }

    private void publishCheckpoint(
            DurableCheckpoint.Capture<K, T> capture,
            DurableStorageOwner.GenerationCut cut,
            CompletableFuture<Void> result
    ) {
        try {
            DurableStorageOwner.CheckpointPublication publication =
                    storage.publishCheckpoint(capture, config, schema, cut);
            synchronized (this) {
                checkpointSequence = publication.manifest().checkpointSequence();
                lastCheckpointFailure = Optional.ofNullable(
                        publication.cleanupFailure());
                activeCheckpoint = null;
                publishMetrics(terminal
                        ? DurabilityStatus.FAILED
                        : DurabilityStatus.OPEN);
            }
            result.complete(null);
        } catch (DurableStorageOwner.CheckpointFailure wrapper) {
            DurabilityException failure = wrapper.failure();
            synchronized (this) {
                lastCheckpointFailure = Optional.of(failure.reason());
                if (wrapper.manifestReplaced()) {
                    terminal = true;
                }
                activeCheckpoint = null;
                publishMetrics(terminal
                        ? DurabilityStatus.FAILED
                        : DurabilityStatus.OPEN);
            }
            result.completeExceptionally(failure);
        } catch (RuntimeException failure) {
            synchronized (this) {
                terminal = true;
                lastCheckpointFailure = Optional.of(reasonOf(failure));
                activeCheckpoint = null;
                publishMetrics(DurabilityStatus.FAILED);
            }
            result.completeExceptionally(failure);
        }
    }

    private byte[] canonicalKey(K key) {
        try {
            byte[] encoded = copy(codec.encodeKey(key), "encoded key");
            requireLength(encoded, config.maxEncodedKeyBytes(), "encoded key");
            K decoded = Objects.requireNonNull(
                    codec.decodeKey(encoded.clone()), "decoded key");
            if (!key.equals(decoded)) {
                throw new IllegalArgumentException("decoded key does not equal input");
            }
            byte[] roundTrip = copy(codec.encodeKey(decoded), "round-trip key");
            if (!Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException("key encoding is not canonical");
            }
            return encoded;
        } catch (RuntimeException failure) {
            throw codecFailure("business-key codec validation failed", failure);
        }
    }

    private byte[] canonicalDocument(K expectedId, T document) {
        try {
            byte[] encoded = copy(codec.encodeDocument(document), "encoded document");
            requireLength(
                    encoded,
                    config.maxEncodedDocumentBytes(),
                    "encoded document");
            T decoded = Objects.requireNonNull(
                    codec.decodeDocument(encoded.clone()), "decoded document");
            if (!expectedId.equals(schema.idOf(decoded))) {
                throw new IllegalArgumentException(
                        "decoded document business key does not match encoded key");
            }
            byte[] roundTrip = copy(
                    codec.encodeDocument(decoded), "round-trip document");
            if (!Arrays.equals(encoded, roundTrip)) {
                throw new IllegalArgumentException("document encoding is not canonical");
            }
            return encoded;
        } catch (RuntimeException failure) {
            throw codecFailure("document codec validation failed", failure);
        }
    }

    private static byte[] encodeIndexDescriptor(DurableIndexDescriptor descriptor) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                output.writeByte(descriptor.kind());
                writeString(output, descriptor.fieldName());
                writeString(output, descriptor.analyzerId());
            }
            return bytes.toByteArray();
        } catch (IOException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static byte[] encodeString(String value) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (DataOutputStream output = new DataOutputStream(bytes)) {
                writeString(output, value);
            }
            return bytes.toByteArray();
        } catch (IOException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        if (encoded.length > 1024) {
            throw new IllegalArgumentException("persisted string has invalid size");
        }
        writeBytes(output, encoded);
    }

    private static void writeBytes(DataOutputStream output, byte[] value)
            throws IOException {
        output.writeInt(value.length);
        output.write(value);
    }

    private static byte[] copy(byte[] value, String name) {
        return Objects.requireNonNull(value, name).clone();
    }

    private static void requireLength(byte[] value, int maximum, String name) {
        if (value.length > maximum) {
            throw new IllegalArgumentException(name + " exceeds configured limit");
        }
    }

    private static void requireFrameBound(int payloadBytes) {
        long frameBytes = DurableWal.FRAME_HEADER_BYTES
                + (long) payloadBytes
                + DurableWal.FRAME_TRAILER_BYTES;
        if (frameBytes > DurableWal.MAX_FRAME_BYTES) {
            throw new DurabilityException(
                    DurabilityException.Reason.CAPACITY_EXCEEDED,
                    "encoded WAL frame exceeds the 256 MiB hard limit");
        }
    }

    private void capacityFailure(String message) {
        publishMetrics(DurabilityStatus.CAPACITY_BLOCKED);
        throw new DurabilityException(
                DurabilityException.Reason.CAPACITY_EXCEEDED,
                message);
    }

    private void ensureWritable() {
        if (closed) {
            throw new DurabilityException(
                    DurabilityException.Reason.CLOSED,
                    "durable engine is closed");
        }
        if (terminal) {
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "durable writer is in terminal failed state");
        }
    }

    private void publishMetrics(DurabilityStatus status) {
        publishMetrics(
                status,
                publishedSequence,
                storage.wal().records(),
                storage.wal().position(),
                storage.retainedBytes());
    }

    private void publishMetrics(
            DurabilityStatus status,
            long sequence,
            long walRecords,
            long walBytes,
            long retainedBytes
    ) {
        metrics.set(new DurabilityMetrics(
                status,
                sequence,
                checkpointSequence,
                storage.wal().generation(),
                walRecords,
                walBytes,
                retainedBytes,
                recoverySource,
                replayedRecords,
                recoveryDuration,
                indexRebuildDuration,
                lastCheckpointFailure));
    }

    private static DurabilityException codecFailure(
            String message,
            Throwable cause
    ) {
        return cause == null
                ? new DurabilityException(
                        DurabilityException.Reason.CODEC_FAILURE, message)
                : new DurabilityException(
                        DurabilityException.Reason.CODEC_FAILURE, message, cause);
    }

    @Override
    public void close() {
        CompletableFuture<Void> pendingCheckpoint;
        CompletableFuture<DurableBackupResult> pendingBackup;
        synchronized (this) {
            if (closed) {
                return;
            }
            closed = true;
            pendingCheckpoint = activeCheckpoint;
            pendingBackup = activeBackup;
            checkpointExecutor.shutdown();
        }
        if (pendingCheckpoint != null) {
            try {
                pendingCheckpoint.join();
            } catch (CompletionException ignored) {
                // The accepted checkpoint Future already carries its primary failure.
            }
        }
        if (pendingBackup != null) {
            try {
                pendingBackup.join();
            } catch (CompletionException ignored) {
                // The accepted backup Future already carries its primary failure.
            }
        }
        backupExecutor.shutdown();
        boolean interrupted = false;
        while (!checkpointExecutor.isTerminated()
                || !backupExecutor.isTerminated()) {
            try {
                checkpointExecutor.awaitTermination(1, TimeUnit.DAYS);
                backupExecutor.awaitTermination(1, TimeUnit.DAYS);
            } catch (InterruptedException failure) {
                interrupted = true;
            }
        }
        try {
            synchronized (this) {
                publishMetrics(terminal
                        ? DurabilityStatus.FAILED
                        : DurabilityStatus.CLOSED);
            }
            storage.close();
        } catch (DurabilityException failure) {
            synchronized (this) {
                terminal = true;
                DurabilityMetrics previous = metrics.get();
                publishMetrics(
                        DurabilityStatus.FAILED,
                        publishedSequence,
                        previous.walRecords(),
                        previous.walBytes(),
                        previous.retainedBytes());
            }
            throw failure;
        } finally {
            if (interrupted) {
                Thread.currentThread().interrupt();
            }
        }
    }

    enum MutationKind {
        ADD,
        UPDATE,
        REMOVE
    }

    record PreparedMutation(byte[] payload) {
        PreparedMutation {
            payload = payload.clone();
        }
    }

    record PreparedUnit(byte type, byte[] payload) {
        PreparedUnit {
            if (type < DurableWal.SINGLE || type > DurableWal.INDEX_DROP) {
                throw new IllegalArgumentException("unknown WAL unit type");
            }
            payload = payload.clone();
        }
    }

    record SequencedUnit(long sequence, PreparedUnit unit) {
        SequencedUnit {
            if (sequence <= 0) {
                throw new IllegalArgumentException("sequence must be positive");
            }
            Objects.requireNonNull(unit, "unit");
        }
    }

    record CommitGroup(long firstSequence, long lastSequence, int unitCount) {
        CommitGroup {
            if (firstSequence <= 0 || lastSequence < firstSequence || unitCount <= 0
                    || lastSequence - firstSequence + 1 != unitCount) {
                throw new IllegalArgumentException("invalid commit group");
            }
        }
    }
}
