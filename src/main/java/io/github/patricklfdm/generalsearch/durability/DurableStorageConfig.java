package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;
import java.util.regex.Pattern;

/** Immutable local durable-storage identity and safety bounds. */
public final class DurableStorageConfig<K, T> {
    /** Default maximum encoded business-key size: one MiB. */
    public static final int DEFAULT_MAX_ENCODED_KEY_BYTES = 1024 * 1024;
    /** Default maximum encoded document size: 64 MiB. */
    public static final int DEFAULT_MAX_ENCODED_DOCUMENT_BYTES = 64 * 1024 * 1024;
    /** Default maximum element count in one persisted bulk. */
    public static final int DEFAULT_MAX_BULK_ELEMENTS = 100_000;
    /** Default maximum live-document count. */
    public static final int DEFAULT_MAX_DOCUMENTS = 10_000_000;
    /** Default automatic-checkpoint WAL threshold: 256 MiB. */
    public static final long DEFAULT_CHECKPOINT_WAL_BYTES = 256L * 1024 * 1024;
    /** Default retained engine-owned byte limit: eight GiB. */
    public static final long DEFAULT_MAX_RETAINED_BYTES = 8L * 1024 * 1024 * 1024;

    static final int HARD_MAX_ENCODED_KEY_BYTES = 64 * 1024 * 1024;
    static final int HARD_MAX_ENCODED_DOCUMENT_BYTES = 256 * 1024 * 1024;
    static final int HARD_MAX_BULK_ELEMENTS = 1_000_000;
    static final int HARD_MAX_DOCUMENTS = 100_000_000;
    static final long HARD_MAX_CHECKPOINT_WAL_BYTES = 1024L * 1024 * 1024 * 1024;
    static final long HARD_MAX_RETAINED_BYTES = 16L * 1024 * 1024 * 1024 * 1024;

    private static final Pattern IDENTITY = Pattern.compile(
            "[a-z0-9][a-z0-9._-]{0,127}");

    private final Path directory;
    private final String storageIdentity;
    private final String schemaIdentity;
    private final DurableCodec<K, T> codec;
    private final int maxEncodedKeyBytes;
    private final int maxEncodedDocumentBytes;
    private final int maxBulkElements;
    private final int maxDocuments;
    private final long checkpointWalBytes;
    private final long maxRetainedBytes;

    private DurableStorageConfig(Builder<K, T> builder) {
        directory = builder.directory;
        storageIdentity = requireIdentity(
                builder.storageIdentity, "storageIdentity");
        schemaIdentity = requireIdentity(builder.schemaIdentity, "schemaIdentity");
        codec = builder.codec;
        String codecId;
        int codecVersion;
        try {
            codecId = codec.codecId();
            codecVersion = codec.codecVersion();
        } catch (RuntimeException failure) {
            throw new IllegalArgumentException("codec identity lookup failed", failure);
        }
        requireIdentity(codecId, "codec.codecId()");
        if (codecVersion < 0) {
            throw new IllegalArgumentException("codec version must not be negative");
        }
        maxEncodedKeyBytes = positiveBounded(
                builder.maxEncodedKeyBytes,
                HARD_MAX_ENCODED_KEY_BYTES,
                "maxEncodedKeyBytes");
        maxEncodedDocumentBytes = positiveBounded(
                builder.maxEncodedDocumentBytes,
                HARD_MAX_ENCODED_DOCUMENT_BYTES,
                "maxEncodedDocumentBytes");
        maxBulkElements = positiveBounded(
                builder.maxBulkElements,
                HARD_MAX_BULK_ELEMENTS,
                "maxBulkElements");
        maxDocuments = positiveBounded(
                builder.maxDocuments,
                HARD_MAX_DOCUMENTS,
                "maxDocuments");
        checkpointWalBytes = positiveBounded(
                builder.checkpointWalBytes,
                HARD_MAX_CHECKPOINT_WAL_BYTES,
                "checkpointWalBytes");
        maxRetainedBytes = positiveBounded(
                builder.maxRetainedBytes,
                HARD_MAX_RETAINED_BYTES,
                "maxRetainedBytes");
        if (maxRetainedBytes <= checkpointWalBytes) {
            throw new IllegalArgumentException(
                    "maxRetainedBytes must exceed checkpointWalBytes");
        }
    }

    /** Starts a configuration builder for a local directory and explicit codec. */
    public static <K, T> Builder<K, T> builder(
            Path directory,
            DurableCodec<K, T> codec
    ) {
        return new Builder<>(directory, codec);
    }

    public Path directory() {
        return directory;
    }

    public String storageIdentity() {
        return storageIdentity;
    }

    public String schemaIdentity() {
        return schemaIdentity;
    }

    public DurableCodec<K, T> codec() {
        return codec;
    }

    public int maxEncodedKeyBytes() {
        return maxEncodedKeyBytes;
    }

    public int maxEncodedDocumentBytes() {
        return maxEncodedDocumentBytes;
    }

    public int maxBulkElements() {
        return maxBulkElements;
    }

    public int maxDocuments() {
        return maxDocuments;
    }

    public long checkpointWalBytes() {
        return checkpointWalBytes;
    }

    public long maxRetainedBytes() {
        return maxRetainedBytes;
    }

    /** Mutable builder with frozen safe defaults and explicit persisted identities. */
    public static final class Builder<K, T> {
        private final Path directory;
        private final DurableCodec<K, T> codec;
        private String storageIdentity;
        private String schemaIdentity;
        private int maxEncodedKeyBytes = DEFAULT_MAX_ENCODED_KEY_BYTES;
        private int maxEncodedDocumentBytes = DEFAULT_MAX_ENCODED_DOCUMENT_BYTES;
        private int maxBulkElements = DEFAULT_MAX_BULK_ELEMENTS;
        private int maxDocuments = DEFAULT_MAX_DOCUMENTS;
        private long checkpointWalBytes = DEFAULT_CHECKPOINT_WAL_BYTES;
        private long maxRetainedBytes = DEFAULT_MAX_RETAINED_BYTES;

        private Builder(Path directory, DurableCodec<K, T> codec) {
            this.directory = Objects.requireNonNull(directory, "directory");
            this.codec = Objects.requireNonNull(codec, "codec");
        }

        public Builder<K, T> storageIdentity(String value) {
            storageIdentity = value;
            return this;
        }

        public Builder<K, T> schemaIdentity(String value) {
            schemaIdentity = value;
            return this;
        }

        public Builder<K, T> maxEncodedKeyBytes(int value) {
            maxEncodedKeyBytes = value;
            return this;
        }

        public Builder<K, T> maxEncodedDocumentBytes(int value) {
            maxEncodedDocumentBytes = value;
            return this;
        }

        public Builder<K, T> maxBulkElements(int value) {
            maxBulkElements = value;
            return this;
        }

        public Builder<K, T> maxDocuments(int value) {
            maxDocuments = value;
            return this;
        }

        public Builder<K, T> checkpointWalBytes(long value) {
            checkpointWalBytes = value;
            return this;
        }

        public Builder<K, T> maxRetainedBytes(long value) {
            maxRetainedBytes = value;
            return this;
        }

        /** Validates identities and hard bounds and returns an immutable value. */
        public DurableStorageConfig<K, T> build() {
            return new DurableStorageConfig<>(this);
        }
    }

    private static String requireIdentity(String value, String name) {
        if (value == null || !IDENTITY.matcher(value).matches()) {
            throw new IllegalArgumentException(
                    name + " must match [a-z0-9][a-z0-9._-]{0,127}");
        }
        return value;
    }

    private static int positiveBounded(int value, int maximum, String name) {
        if (value <= 0 || value > maximum) {
            throw new IllegalArgumentException(
                    name + " must be between 1 and " + maximum);
        }
        return value;
    }

    private static long positiveBounded(long value, long maximum, String name) {
        if (value <= 0 || value > maximum) {
            throw new IllegalArgumentException(
                    name + " must be between 1 and " + maximum);
        }
        return value;
    }
}
