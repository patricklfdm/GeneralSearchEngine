package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Immutable proof of one durably published and structurally valid backup bundle.
 *
 * @param targetDirectory finalized bundle directory
 * @param format bundle format
 * @param contentIdentity canonical content identity
 * @param sourceHistory source live-store history
 * @param sequence exact durable sequence represented by the bundle
 * @param memberCount authoritative member count, exactly three for V1.0/V1.1
 * @param totalBytes total authoritative bundle bytes
 */
public record DurableBackupResult(
        Path targetDirectory,
        DurableBackupFormat format,
        String contentIdentity,
        UUID sourceHistory,
        long sequence,
        int memberCount,
        long totalBytes
) {
    private static final Pattern CONTENT_IDENTITY = Pattern.compile(
            "gse-backup-v[12]-[0-9a-f]{64}");

    /** Normalizes and validates the successful publication proof. */
    public DurableBackupResult {
        targetDirectory = Objects.requireNonNull(targetDirectory, "targetDirectory")
                .toAbsolutePath().normalize();
        format = Objects.requireNonNull(format, "format");
        Objects.requireNonNull(contentIdentity, "contentIdentity");
        sourceHistory = Objects.requireNonNull(sourceHistory, "sourceHistory");
        String expectedPrefix = format.equals(DurableBackupFormat.V1_0)
                ? "gse-backup-v1-"
                : format.equals(DurableBackupFormat.V1_1)
                        ? "gse-backup-v2-" : "";
        if (!contentIdentity.startsWith(expectedPrefix)
                || expectedPrefix.isEmpty()
                || !CONTENT_IDENTITY.matcher(contentIdentity).matches()) {
            throw new IllegalArgumentException("unsupported backup result identity");
        }
        if (sourceHistory.getMostSignificantBits() == 0L
                && sourceHistory.getLeastSignificantBits() == 0L) {
            throw new IllegalArgumentException("sourceHistory must not be zero");
        }
        if (sequence < 0 || memberCount != 3 || totalBytes <= 0) {
            throw new IllegalArgumentException("invalid backup result bounds");
        }
    }
}
