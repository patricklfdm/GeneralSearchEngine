package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.regex.Pattern;

/** Expected typed identities and bounded decode limits for semantic backup verification. */
public record DurableVerificationConfig<K, T>(
        String storageIdentity,
        String schemaIdentity,
        DurableCodec<K, T> codec,
        int codecVersion,
        int maxEncodedKeyBytes,
        int maxEncodedDocumentBytes,
        int maxDocuments
) {
    private static final Pattern IDENTITY = Pattern.compile(
            "[a-z0-9][a-z0-9._-]{0,127}");

    /** Validates all identities and hard resource bounds without touching storage. */
    public DurableVerificationConfig {
        storageIdentity = requireIdentity(storageIdentity, "storageIdentity");
        schemaIdentity = requireIdentity(schemaIdentity, "schemaIdentity");
        codec = Objects.requireNonNull(codec, "codec");
        requireIdentity(codecId(codec), "codec.codecId()");
        if (codecVersion < 0) {
            throw new IllegalArgumentException("codecVersion must not be negative");
        }
        bounded(maxEncodedKeyBytes, 64 * 1024 * 1024,
                "maxEncodedKeyBytes");
        bounded(maxEncodedDocumentBytes, 256 * 1024 * 1024,
                "maxEncodedDocumentBytes");
        bounded(maxDocuments, 100_000_000, "maxDocuments");
    }

    private static String codecId(DurableCodec<?, ?> codec) {
        try {
            return codec.codecId();
        } catch (RuntimeException failure) {
            throw new IllegalArgumentException("codec identity lookup failed", failure);
        }
    }

    private static String requireIdentity(String value, String name) {
        Objects.requireNonNull(value, name);
        if (!IDENTITY.matcher(value).matches()) {
            throw new IllegalArgumentException(
                    name + " must match [a-z0-9][a-z0-9._-]{0,127}");
        }
        return value;
    }

    private static void bounded(int value, int maximum, String name) {
        if (value <= 0 || value > maximum) {
            throw new IllegalArgumentException(
                    name + " must be between 1 and " + maximum);
        }
    }
}
