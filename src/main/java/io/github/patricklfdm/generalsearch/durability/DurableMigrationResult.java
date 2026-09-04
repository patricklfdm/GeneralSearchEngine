package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

/** Completed source-preserving offline migration provenance. */
public record DurableMigrationResult(
        Path sourceDirectory,
        Path targetDirectory,
        DurableStorageFormat sourceFormat,
        DurableStorageFormat targetFormat,
        UUID sourceHistory,
        UUID targetHistory,
        long sequence,
        long nextDocId,
        int documentCount,
        String sourceAuthorityIdentity,
        String projectionDigest,
        String planDigest,
        long authoritativeBytes
) {
    private static final UUID ZERO = new UUID(0, 0);
    private static final Pattern IDENTITY = Pattern.compile(
            "[a-z0-9][a-z0-9-]{0,127}-[a-f0-9]{64}");

    public DurableMigrationResult {
        sourceDirectory = normalized(sourceDirectory, "sourceDirectory");
        targetDirectory = normalized(targetDirectory, "targetDirectory");
        sourceFormat = Objects.requireNonNull(sourceFormat, "sourceFormat");
        targetFormat = Objects.requireNonNull(targetFormat, "targetFormat");
        sourceHistory = history(sourceHistory, "sourceHistory");
        targetHistory = history(targetHistory, "targetHistory");
        if (sourceHistory.equals(targetHistory)) {
            throw new IllegalArgumentException("target history must be fresh");
        }
        if (sequence < 0 || nextDocId < 0 || documentCount < 0
                || authoritativeBytes < 0) {
            throw new IllegalArgumentException("negative migration result value");
        }
        if (documentCount > nextDocId) {
            throw new IllegalArgumentException(
                    "documentCount must not exceed nextDocId");
        }
        sourceAuthorityIdentity = identity(
                sourceAuthorityIdentity, "sourceAuthorityIdentity");
        projectionDigest = identity(projectionDigest, "projectionDigest");
        planDigest = identity(planDigest, "planDigest");
    }

    private static Path normalized(Path path, String name) {
        Path value = Objects.requireNonNull(path, name);
        Path normalized = value.toAbsolutePath().normalize();
        if (!value.equals(normalized)) {
            throw new IllegalArgumentException(name + " must be normalized and absolute");
        }
        return normalized;
    }

    private static UUID history(UUID value, String name) {
        Objects.requireNonNull(value, name);
        if (value.equals(ZERO)) {
            throw new IllegalArgumentException(name + " must be non-zero");
        }
        return value;
    }

    private static String identity(String value, String name) {
        Objects.requireNonNull(value, name);
        if (!IDENTITY.matcher(value).matches()) {
            throw new IllegalArgumentException(name + " is not canonical");
        }
        return value;
    }
}
