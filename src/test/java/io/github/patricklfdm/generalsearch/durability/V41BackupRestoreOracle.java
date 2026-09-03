package io.github.patricklfdm.generalsearch.durability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/** Independent Phase 1 model; it deliberately does not call production recovery. */
final class V41BackupRestoreOracle {
    private static final byte[] DOMAIN =
            "gse-backup-content-v1\0".getBytes(StandardCharsets.US_ASCII);

    record SourceState(
            UUID history,
            String storageIdentity,
            String schemaIdentity,
            String codecIdentity,
            int codecVersion,
            long sequence,
            long nextDocId,
            Map<String, String> documents,
            List<String> durableIndexes
    ) {
        SourceState {
            Objects.requireNonNull(history, "history");
            Objects.requireNonNull(storageIdentity, "storageIdentity");
            Objects.requireNonNull(schemaIdentity, "schemaIdentity");
            Objects.requireNonNull(codecIdentity, "codecIdentity");
            documents = Map.copyOf(new LinkedHashMap<>(documents));
            durableIndexes = List.copyOf(durableIndexes);
            if (sequence < 0 || nextDocId < 0 || codecVersion < 0) {
                throw new IllegalArgumentException("negative source field");
            }
        }

        SourceState add(String key, String value) {
            if (sequence == Long.MAX_VALUE || nextDocId == Long.MAX_VALUE) {
                throw new IllegalStateException("source sequence or document id exhausted");
            }
            Map<String, String> updated = new LinkedHashMap<>(documents);
            updated.put(key, value);
            return new SourceState(
                    history,
                    storageIdentity,
                    schemaIdentity,
                    codecIdentity,
                    codecVersion,
                    sequence + 1,
                    nextDocId + 1,
                    updated,
                    durableIndexes);
        }
    }

    record Backup(
            SourceState captured,
            byte[] metadata,
            byte[] checkpoint,
            String contentIdentity
    ) {
        Backup {
            metadata = metadata.clone();
            checkpoint = checkpoint.clone();
        }

        @Override
        public byte[] metadata() {
            return metadata.clone();
        }

        @Override
        public byte[] checkpoint() {
            return checkpoint.clone();
        }
    }

    record RestoredState(
            UUID newHistory,
            UUID sourceHistory,
            String sourceContentIdentity,
            long sequence,
            long nextDocId,
            Map<String, String> documents,
            List<String> durableIndexes
    ) {
        RestoredState {
            documents = Map.copyOf(documents);
            durableIndexes = List.copyOf(durableIndexes);
        }
    }

    Backup backup(SourceState source) {
        Objects.requireNonNull(source, "source");
        if (source.sequence() == Long.MAX_VALUE) {
            throw new IllegalStateException("cannot cut the required post-checkpoint WAL");
        }
        byte[] metadata = canonicalMetadata(source);
        byte[] checkpoint = canonicalCheckpoint(source);
        return new Backup(source, metadata, checkpoint,
                contentIdentity(source, metadata, checkpoint));
    }

    RestoredState restore(Backup backup, UUID newHistory, String expectedStorage,
                          String expectedSchema, String expectedCodec, int expectedVersion) {
        Objects.requireNonNull(backup, "backup");
        Objects.requireNonNull(newHistory, "newHistory");
        SourceState source = backup.captured();
        if (newHistory.equals(new UUID(0, 0)) || newHistory.equals(source.history())) {
            throw new IllegalArgumentException("restore requires a distinct non-zero history");
        }
        if (!source.storageIdentity().equals(expectedStorage)
                || !source.schemaIdentity().equals(expectedSchema)
                || !source.codecIdentity().equals(expectedCodec)
                || source.codecVersion() != expectedVersion) {
            throw new IllegalArgumentException("semantic identity mismatch");
        }
        String recomputed = contentIdentity(
                source, backup.metadata(), backup.checkpoint());
        if (!recomputed.equals(backup.contentIdentity())) {
            throw new IllegalArgumentException("backup content identity mismatch");
        }
        return new RestoredState(
                newHistory,
                source.history(),
                backup.contentIdentity(),
                source.sequence(),
                source.nextDocId(),
                source.documents(),
                source.durableIndexes());
    }

    private static byte[] canonicalMetadata(SourceState state) {
        return String.join("\n",
                "gse-durable-metadata-model-v1",
                state.history().toString(),
                state.storageIdentity(),
                state.schemaIdentity(),
                state.codecIdentity(),
                Integer.toString(state.codecVersion()),
                String.join(",", state.durableIndexes()),
                "").getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] canonicalCheckpoint(SourceState state) {
        List<String> lines = new ArrayList<>();
        lines.add("gse-durable-checkpoint-model-v1");
        lines.add(state.history().toString());
        lines.add(Long.toString(state.sequence()));
        lines.add(Long.toString(state.nextDocId()));
        state.documents().entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> lines.add(entry.getKey() + "=" + entry.getValue()));
        lines.add("");
        return String.join("\n", lines).getBytes(StandardCharsets.UTF_8);
    }

    private static String contentIdentity(SourceState state, byte[] metadata,
                                          byte[] checkpoint) {
        MessageDigest digest = sha256();
        digest.update(DOMAIN);
        update(digest, state.history().toString());
        update(digest, state.storageIdentity());
        update(digest, state.schemaIdentity());
        update(digest, state.codecIdentity());
        update(digest, Integer.toString(state.codecVersion()));
        update(digest, Long.toString(state.sequence()));
        member(digest, "gse-backup-checkpoint", checkpoint);
        member(digest, "gse-backup-metadata", metadata);
        return "gse-backup-v1-" + HexFormat.of().formatHex(digest.digest());
    }

    private static void member(MessageDigest digest, String name, byte[] bytes) {
        update(digest, name);
        update(digest, Long.toUnsignedString(bytes.length));
        digest.update(sha256().digest(bytes));
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        digest.update((byte) (bytes.length >>> 24));
        digest.update((byte) (bytes.length >>> 16));
        digest.update((byte) (bytes.length >>> 8));
        digest.update((byte) bytes.length);
        digest.update(bytes);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }
}
