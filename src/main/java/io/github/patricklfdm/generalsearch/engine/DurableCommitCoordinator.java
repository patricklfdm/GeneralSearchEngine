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
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
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
    private final SearchSchema<T, K> schema;
    private final DurableStorageOwner storage;
    private final AtomicReference<DurabilityMetrics> metrics;
    private long allocatedSequence;
    private long publishedSequence;
    private boolean terminal;
    private boolean closed;

    private DurableCommitCoordinator(
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            DurableStorageOwner storage
    ) {
        this.config = config;
        this.codec = config.codec();
        this.schema = schema;
        this.storage = storage;
        metrics = new AtomicReference<>(new DurabilityMetrics(
                DurabilityStatus.OPEN,
                0,
                0,
                DurableWal.GENERATION,
                0,
                storage.wal().position(),
                storage.retainedBytes(),
                RecoverySource.FRESH,
                0,
                Duration.ZERO,
                Duration.ZERO,
                Optional.empty()));
    }

    static <K, T> DurableCommitCoordinator<K, T> createFresh(
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
        DurableStorageOwner owner = DurableStorageOwner.createFresh(
                config,
                codecId,
                codecVersion,
                indexes);
        try {
            return new DurableCommitCoordinator<>(config, schema, owner);
        } catch (RuntimeException | Error failure) {
            try {
                owner.close();
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
        if (additionalBytes > config.maxRetainedBytes() - retained) {
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
            DurableWal.AppendResult append = storage.wal().appendAndForce(sequenced);
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

    DurabilityMetrics metrics() {
        return metrics.get();
    }

    synchronized CompletableFuture<Void> checkpoint() {
        if (closed) {
            return CompletableFuture.failedFuture(new DurabilityException(
                    DurabilityException.Reason.CLOSED,
                    "durable engine is closed"));
        }
        return CompletableFuture.failedFuture(new UnsupportedOperationException(
                "production checkpoints begin in V4 Phase 4"));
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
        DurabilityMetrics previous = metrics.get();
        publishMetrics(
                status,
                publishedSequence,
                previous.walRecords(),
                previous.walBytes(),
                previous.retainedBytes());
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
                0,
                DurableWal.GENERATION,
                walRecords,
                walBytes,
                retainedBytes,
                RecoverySource.FRESH,
                0,
                Duration.ZERO,
                Duration.ZERO,
                Optional.empty()));
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
    public synchronized void close() {
        if (closed) {
            return;
        }
        closed = true;
        try {
            storage.close();
            publishMetrics(DurabilityStatus.CLOSED);
        } catch (DurabilityException failure) {
            terminal = true;
            publishMetrics(DurabilityStatus.FAILED);
            throw failure;
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
