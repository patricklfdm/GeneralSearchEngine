package io.github.patricklfdm.generalsearch.engine;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;

final class DurableRecovery {
    private static final byte ADD = 1;
    private static final byte UPDATE = 2;
    private static final byte REMOVE = 3;

    private DurableRecovery() {
    }

    static <K, T> Result<K, T> replay(
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            List<DurableIndexDescriptor> startupIndexes,
            DurableWal wal,
            boolean recoveryBarriers
    ) {
        long recoveryStarted = System.nanoTime();
        ReplayState<K, T> state = new ReplayState<>(
                config,
                schema,
                startupIndexes);
        wal.forEachFrame(frame -> {
            try {
                state.apply(frame);
            } catch (DurabilityException failure) {
                throw failure;
            } catch (RuntimeException failure) {
                throw new DurabilityException(
                        DurabilityException.Reason.REPLAY_FAILURE,
                        frame.sequence(),
                        "durable WAL replay failed",
                        failure);
            }
        });
        if (recoveryBarriers) {
            DurableCrashHooks.reach("v4-recovery-after-replay-v1");
        }

        long rebuildStarted = System.nanoTime();
        SearchSnapshot<T> snapshot;
        try {
            List<IndexDefinition<T>> definitions = state.indexes.stream()
                    .map(descriptor -> descriptor.toDefinition(schema))
                    .toList();
            SearchSnapshot<T> empty = new SearchSnapshot<>(definitions);
            if (state.liveDocuments == 0) {
                snapshot = empty;
            } else {
                SearchSnapshotBuilder<T> builder = new SearchSnapshotBuilder<>(empty);
                for (int docId = 0; docId < state.slots.size(); docId++) {
                    T document = state.slots.get(docId);
                    if (document != null) {
                        builder.add(docId, document);
                    }
                }
                snapshot = builder.build();
            }
        } catch (RuntimeException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.INDEX_REBUILD_FAILURE,
                    "derived-index rebuild failed during durable open",
                    failure);
        }
        Duration indexRebuildDuration = elapsed(rebuildStarted);
        return new Result<>(
                snapshot,
                state.documentIds,
                state.nextDocId,
                state.lastSequence,
                wal.records(),
                elapsed(recoveryStarted),
                indexRebuildDuration);
    }

    private static Duration elapsed(long started) {
        return Duration.ofNanos(Math.max(0L, System.nanoTime() - started));
    }

    record Result<K, T>(
            SearchSnapshot<T> snapshot,
            Map<K, Integer> documentIds,
            int nextDocId,
            long sequence,
            long replayedRecords,
            Duration recoveryDuration,
            Duration indexRebuildDuration
    ) {
        Result {
            Objects.requireNonNull(snapshot, "snapshot");
            documentIds = Map.copyOf(documentIds);
            if (nextDocId < 0 || sequence < 0 || replayedRecords < 0) {
                throw new IllegalArgumentException("negative recovered state value");
            }
            Objects.requireNonNull(recoveryDuration, "recoveryDuration");
            Objects.requireNonNull(indexRebuildDuration, "indexRebuildDuration");
        }
    }

    private static final class ReplayState<K, T> {
        private final DurableStorageConfig<K, T> config;
        private final DurableCodec<K, T> codec;
        private final SearchSchema<T, K> schema;
        private final Map<K, Integer> documentIds = new HashMap<>();
        private final List<T> slots = new ArrayList<>();
        private final List<DurableIndexDescriptor> indexes;
        private int nextDocId;
        private int liveDocuments;
        private long lastSequence;

        private ReplayState(
                DurableStorageConfig<K, T> config,
                SearchSchema<T, K> schema,
                List<DurableIndexDescriptor> startupIndexes
        ) {
            this.config = config;
            this.codec = config.codec();
            this.schema = schema;
            this.indexes = new ArrayList<>(startupIndexes);
        }

        private void apply(DurableWal.Frame frame) {
            PayloadReader reader = new PayloadReader(
                    frame.sequence(), frame.payload());
            switch (frame.type()) {
                case DurableWal.SINGLE -> applyMutation(
                        decodeMutation(reader, frame.sequence()),
                        frame.sequence());
                case DurableWal.BULK -> applyBulk(reader, frame.sequence());
                case DurableWal.INDEX_CREATE -> applyCreateIndex(
                        decodeIndex(reader), frame.sequence());
                case DurableWal.INDEX_DROP -> applyDropIndex(
                        reader.readString(1024, "index field"), frame.sequence());
                default -> throw replayFailure(
                        frame.sequence(), "unknown durable WAL unit type", null);
            }
            reader.requireExhausted();
            lastSequence = frame.sequence();
        }

        private void applyBulk(PayloadReader reader, long sequence) {
            int count = reader.readInt("bulk element count");
            if (count <= 0 || count > config.maxBulkElements()) {
                throw corruptPayload(
                        sequence, "invalid persisted bulk count", null);
            }
            List<DecodedMutation<K, T>> mutations = new ArrayList<>(count);
            HashSet<K> distinct = new HashSet<>();
            for (int index = 0; index < count; index++) {
                DecodedMutation<K, T> mutation = decodeMutation(reader, sequence);
                if (!distinct.add(mutation.key())) {
                    throw replayFailure(
                            sequence, "persisted bulk contains a duplicate key", null);
                }
                mutations.add(mutation);
            }
            for (DecodedMutation<K, T> mutation : mutations) {
                applyMutation(mutation, sequence);
            }
        }

        private DecodedMutation<K, T> decodeMutation(
                PayloadReader reader,
                long sequence
        ) {
            byte operation = reader.readByte("mutation operation");
            if (operation < ADD || operation > REMOVE) {
                throw corruptPayload(sequence, "invalid mutation operation", null);
            }
            byte[] keyBytes = reader.readBytes(
                    config.maxEncodedKeyBytes(), true, "encoded key");
            K key = decodeKey(keyBytes, sequence);
            int documentLength = reader.readInt("encoded document length");
            if (operation == REMOVE) {
                if (documentLength != -1) {
                    throw corruptPayload(
                            sequence, "remove mutation contains a document", null);
                }
                return new DecodedMutation<>(operation, key, null);
            }
            if (documentLength < 0
                    || documentLength > config.maxEncodedDocumentBytes()) {
                throw corruptPayload(
                        sequence, "invalid encoded document length", null);
            }
            byte[] documentBytes = reader.readExact(
                    documentLength, "encoded document");
            T document = decodeDocument(key, documentBytes, sequence);
            return new DecodedMutation<>(operation, key, document);
        }

        private K decodeKey(byte[] encoded, long sequence) {
            try {
                K key = Objects.requireNonNull(
                        codec.decodeKey(encoded.clone()), "decoded key");
                byte[] roundTrip = Objects.requireNonNull(
                        codec.encodeKey(key), "round-trip encoded key").clone();
                if (roundTrip.length > config.maxEncodedKeyBytes()
                        || !Arrays.equals(encoded, roundTrip)) {
                    throw new IllegalArgumentException(
                            "persisted key encoding is not canonical");
                }
                return key;
            } catch (RuntimeException failure) {
                throw codecFailure(sequence, "persisted business-key decode failed", failure);
            }
        }

        private T decodeDocument(K key, byte[] encoded, long sequence) {
            try {
                T document = Objects.requireNonNull(
                        codec.decodeDocument(encoded.clone()), "decoded document");
                if (!key.equals(schema.idOf(document))) {
                    throw new IllegalArgumentException(
                            "decoded document business key does not match WAL key");
                }
                byte[] roundTrip = Objects.requireNonNull(
                        codec.encodeDocument(document),
                        "round-trip encoded document").clone();
                if (roundTrip.length > config.maxEncodedDocumentBytes()
                        || !Arrays.equals(encoded, roundTrip)) {
                    throw new IllegalArgumentException(
                            "persisted document encoding is not canonical");
                }
                return document;
            } catch (RuntimeException failure) {
                throw codecFailure(sequence, "persisted document decode failed", failure);
            }
        }

        private void applyMutation(DecodedMutation<K, T> mutation, long sequence) {
            switch (mutation.operation()) {
                case ADD -> {
                    if (documentIds.containsKey(mutation.key())) {
                        throw replayFailure(
                                sequence, "replayed add targets an existing key", null);
                    }
                    if (nextDocId == Integer.MAX_VALUE) {
                        throw replayFailure(
                                sequence, "internal document ID space is exhausted", null);
                    }
                    if (liveDocuments >= config.maxDocuments()) {
                        throw replayFailure(
                                sequence, "replayed state exceeds document limit", null);
                    }
                    int docId = nextDocId++;
                    slots.add(mutation.document());
                    documentIds.put(mutation.key(), docId);
                    liveDocuments++;
                }
                case UPDATE -> {
                    Integer docId = documentIds.get(mutation.key());
                    if (docId == null) {
                        throw replayFailure(
                                sequence, "replayed update targets a missing key", null);
                    }
                    slots.set(docId, mutation.document());
                }
                case REMOVE -> {
                    Integer docId = documentIds.remove(mutation.key());
                    if (docId != null) {
                        slots.set(docId, null);
                        liveDocuments--;
                    }
                }
                default -> throw replayFailure(
                        sequence, "invalid replay mutation", null);
            }
        }

        private DurableIndexDescriptor decodeIndex(PayloadReader reader) {
            byte kind = reader.readByte("index kind");
            String fieldName = reader.readString(1024, "index field");
            String analyzerId = reader.readStringAllowEmpty(
                    1024, "index analyzer");
            try {
                return new DurableIndexDescriptor(kind, fieldName, analyzerId);
            } catch (RuntimeException failure) {
                throw corruptPayload(
                        reader.sequence,
                        "invalid persisted index descriptor",
                        failure);
            }
        }

        private void applyCreateIndex(
                DurableIndexDescriptor descriptor,
                long sequence
        ) {
            try {
                descriptor.toDefinition(schema);
            } catch (RuntimeException failure) {
                throw replayFailure(
                        sequence, "persisted index is incompatible with schema", failure);
            }
            if (indexes.contains(descriptor)) {
                throw replayFailure(
                        sequence, "replayed index create already exists", null);
            }
            indexes.add(descriptor);
        }

        private void applyDropIndex(String fieldName, long sequence) {
            try {
                schema.requireField(fieldName);
            } catch (RuntimeException failure) {
                throw replayFailure(
                        sequence, "persisted index drop references unknown field", failure);
            }
            indexes.removeIf(index -> index.fieldName().equals(fieldName));
        }

    }

    private record DecodedMutation<K, T>(byte operation, K key, T document) {
    }

    private static final class PayloadReader {
        private final long sequence;
        private final ByteBuffer bytes;

        private PayloadReader(long sequence, byte[] bytes) {
            this.sequence = sequence;
            this.bytes = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN);
        }

        private byte readByte(String name) {
            requireRemaining(Byte.BYTES, name);
            return bytes.get();
        }

        private int readInt(String name) {
            requireRemaining(Integer.BYTES, name);
            return bytes.getInt();
        }

        private byte[] readBytes(int maximum, boolean allowEmpty, String name) {
            int length = readInt(name + " length");
            if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
                throw corruptPayload(
                        sequence, name + " has invalid length", null);
            }
            return readExact(length, name);
        }

        private byte[] readExact(int length, String name) {
            requireRemaining(length, name);
            byte[] value = new byte[length];
            bytes.get(value);
            return value;
        }

        private String readString(int maximum, String name) {
            return readString(maximum, false, name);
        }

        private String readStringAllowEmpty(int maximum, String name) {
            return readString(maximum, true, name);
        }

        private String readString(int maximum, boolean allowEmpty, String name) {
            byte[] encoded = readBytes(maximum, allowEmpty, name);
            try {
                return StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(ByteBuffer.wrap(encoded))
                        .toString();
            } catch (CharacterCodingException failure) {
                throw corruptPayload(
                        sequence, name + " is not strict UTF-8", failure);
            }
        }

        private void requireExhausted() {
            if (bytes.hasRemaining()) {
                throw corruptPayload(
                        sequence, "WAL payload contains trailing bytes", null);
            }
        }

        private void requireRemaining(int length, String name) {
            if (length < 0 || length > bytes.remaining()) {
                throw corruptPayload(sequence, name + " is truncated", null);
            }
        }
    }

    private static DurabilityException codecFailure(
            long sequence,
            String message,
            Throwable cause
    ) {
        return new DurabilityException(
                DurabilityException.Reason.CODEC_FAILURE,
                sequence,
                message,
                cause);
    }

    private static DurabilityException replayFailure(
            long sequence,
            String message,
            Throwable cause
    ) {
        return cause == null
                ? new DurabilityException(
                        DurabilityException.Reason.REPLAY_FAILURE,
                        sequence,
                        message)
                : new DurabilityException(
                        DurabilityException.Reason.REPLAY_FAILURE,
                        sequence,
                        message,
                        cause);
    }

    private static DurabilityException corruptPayload(
            long sequence,
            String message,
            Throwable cause
    ) {
        return cause == null
                ? new DurabilityException(
                        DurabilityException.Reason.CORRUPT_WAL,
                        sequence,
                        message)
                : new DurabilityException(
                        DurabilityException.Reason.CORRUPT_WAL,
                        sequence,
                        message,
                        cause);
    }
}
