package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;

/** Offline replicated-storage inspection and reserved group bootstrap operations. */
public final class ReplicationStorageOperations {
    private ReplicationStorageOperations() {
    }

    /**
     * Inspects a closed replica directory without application codecs or mutation.
     * An absent directory returns an absent status; invalid or owned storage throws
     * a classified {@link ReplicationException}.
     */
    public static ReplicationStorageStatus inspect(Path directory) {
        Objects.requireNonNull(directory, "directory");
        return ReplicaStore.inspect(directory);
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
                "V5.0 group bootstrap is not enabled in Phase 2");
    }
}
