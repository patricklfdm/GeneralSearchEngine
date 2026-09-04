package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;

/** Bounded typed input for offline durable migration planning and application. */
public record DurableMigrationRequest<SK, ST, TK, TT>(
        Path sourceDirectory,
        DurableVerificationConfig<SK, ST> sourceConfig,
        DurableStorageConfig<TK, TT> targetConfig,
        DurableMigrationTransformDescriptor transformDescriptor,
        DurableMigrationTransform<SK, ST, TK, TT> transform,
        long maxSourceAuthoritativeBytes,
        long maxTargetAuthoritativeBytes,
        long capacitySafetyReserveBytes,
        int maxCollisionEntries,
        int maxFindings,
        int maxDiagnosticBytes
) {
    private static final int HARD_MAX_DOCUMENTS = 100_000_000;
    private static final int HARD_MAX_DIAGNOSTIC_BYTES = 1024 * 1024;

    public DurableMigrationRequest {
        sourceDirectory = Objects.requireNonNull(sourceDirectory, "sourceDirectory")
                .toAbsolutePath().normalize();
        sourceConfig = Objects.requireNonNull(sourceConfig, "sourceConfig");
        targetConfig = Objects.requireNonNull(targetConfig, "targetConfig");
        transformDescriptor = Objects.requireNonNull(
                transformDescriptor, "transformDescriptor");
        transform = Objects.requireNonNull(transform, "transform");
        positive(maxSourceAuthoritativeBytes, "maxSourceAuthoritativeBytes");
        positive(maxTargetAuthoritativeBytes, "maxTargetAuthoritativeBytes");
        positive(capacitySafetyReserveBytes, "capacitySafetyReserveBytes");
        positiveBounded(maxCollisionEntries, HARD_MAX_DOCUMENTS,
                "maxCollisionEntries");
        positiveBounded(maxFindings, HARD_MAX_DOCUMENTS, "maxFindings");
        positiveBounded(maxDiagnosticBytes, HARD_MAX_DIAGNOSTIC_BYTES,
                "maxDiagnosticBytes");
    }

    private static void positive(long value, String name) {
        if (value <= 0) {
            throw new IllegalArgumentException(name + " must be positive");
        }
    }

    private static void positiveBounded(int value, int maximum, String name) {
        if (value <= 0 || value > maximum) {
            throw new IllegalArgumentException(
                    name + " must be between 1 and " + maximum);
        }
    }
}
