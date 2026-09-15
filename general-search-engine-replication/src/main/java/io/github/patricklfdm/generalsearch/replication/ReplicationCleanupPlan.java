package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Reviewed dependency-ordered deletion intent; apply must recheck complete ownership. */
public record ReplicationCleanupPlan(
        Path operationDirectory,
        String operationDigest,
        List<Path> deletePaths,
        String inventoryDigest,
        String planDigest
) {
    public ReplicationCleanupPlan {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        ReplicaFormat.validHash(operationDigest);
        ReplicaFormat.validHash(inventoryDigest);
        ReplicaFormat.validHash(planDigest);
        deletePaths = List.copyOf(deletePaths);
        if (deletePaths.stream().distinct().count() != deletePaths.size()) {
            throw new IllegalArgumentException("cleanup paths must be distinct");
        }
    }
}
