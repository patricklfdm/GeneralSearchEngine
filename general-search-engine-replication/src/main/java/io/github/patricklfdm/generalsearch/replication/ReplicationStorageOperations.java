package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;

/** Declaration-only offline replicated-storage operations. */
public final class ReplicationStorageOperations {
    private ReplicationStorageOperations() {
    }

    public static ReplicationStorageStatus inspect(Path directory) {
        Objects.requireNonNull(directory, "directory");
        throw unavailable();
    }

    public static ReplicationBootstrapPlan planBootstrap(
            ReplicationGroupId groupId,
            String configurationId,
            ReplicationBootstrapSource source,
            Path sourcePath,
            java.util.List<Path> absentReplicaTargets
    ) {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(configurationId, "configurationId");
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(absentReplicaTargets, "absentReplicaTargets");
        throw unavailable();
    }

    public static void applyBootstrap(ReplicationBootstrapPlan plan) {
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    private static UnsupportedOperationException unavailable() {
        return new UnsupportedOperationException(
                "V5.0 replicated storage is not enabled in Phase 1");
    }
}
