package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;

/**
 * Immutable request for one full checkpoint-only backup of a live durable engine.
 *
 * @param targetDirectory absent final bundle directory
 * @param maxBundleBytes positive maximum authoritative bundle bytes
 */
public record DurableBackupRequest(Path targetDirectory, long maxBundleBytes) {
    /** Normalizes the target path and validates the explicit capacity bound. */
    public DurableBackupRequest {
        targetDirectory = Objects.requireNonNull(targetDirectory, "targetDirectory")
                .toAbsolutePath().normalize();
        if (maxBundleBytes <= 0) {
            throw new IllegalArgumentException("maxBundleBytes must be positive");
        }
    }
}
