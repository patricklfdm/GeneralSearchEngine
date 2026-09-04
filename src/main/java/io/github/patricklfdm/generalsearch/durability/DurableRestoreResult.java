package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

/** Immutable provenance and authority summary for one completed new-history restore. */
public record DurableRestoreResult(
        Path targetDirectory,
        UUID newHistory,
        UUID sourceHistory,
        String sourceContentIdentity,
        long restoredSequence,
        long authoritativeBytes
) {
    private static final UUID ZERO_HISTORY = new UUID(0L, 0L);
    private static final Pattern CONTENT_IDENTITY = Pattern.compile(
            "gse-backup-v[12]-[0-9a-f]{64}");

    /** Normalizes the target and validates the completed restore identity. */
    public DurableRestoreResult {
        targetDirectory = Objects.requireNonNull(targetDirectory, "targetDirectory")
                .toAbsolutePath().normalize();
        newHistory = Objects.requireNonNull(newHistory, "newHistory");
        sourceHistory = Objects.requireNonNull(sourceHistory, "sourceHistory");
        sourceContentIdentity = Objects.requireNonNull(
                sourceContentIdentity, "sourceContentIdentity");
        if (newHistory.equals(ZERO_HISTORY) || sourceHistory.equals(ZERO_HISTORY)
                || newHistory.equals(sourceHistory)) {
            throw new IllegalArgumentException(
                    "restore histories must be non-zero and distinct");
        }
        if (!CONTENT_IDENTITY.matcher(sourceContentIdentity).matches()) {
            throw new IllegalArgumentException("invalid backup content identity");
        }
        if (restoredSequence < 0 || authoritativeBytes < 0) {
            throw new IllegalArgumentException(
                    "restore sequence and authoritative bytes must not be negative");
        }
    }
}
