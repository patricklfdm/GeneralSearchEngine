package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;
import java.util.Objects;

/**
 * Immutable request to inspect one exact offline cleanup boundary.
 *
 * @param directory explicitly named live store, staging directory, or marker path
 * @param scope authority rules used to classify the named path
 */
public record DurableCleanupRequest(Path directory, DurableCleanupScope scope) {
    /** Normalizes the named path without touching the filesystem. */
    public DurableCleanupRequest {
        directory = Objects.requireNonNull(directory, "directory")
                .toAbsolutePath().normalize();
        scope = Objects.requireNonNull(scope, "scope");
    }
}
