package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Immutable summary of an offline bootstrap plan; typed apply verifies its full binding. */
public record ReplicationBootstrapPlan(
        ReplicationGroupId groupId,
        String configurationId,
        ReplicationBootstrapSource source,
        Path sourcePath,
        List<Path> absentReplicaTargets,
        String planDigest
) {
    public ReplicationBootstrapPlan {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(configurationId, "configurationId");
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(absentReplicaTargets, "absentReplicaTargets");
        Objects.requireNonNull(planDigest, "planDigest");
        absentReplicaTargets = List.copyOf(absentReplicaTargets);
        if (absentReplicaTargets.size() != 3
                || absentReplicaTargets.stream().distinct().count() != 3) {
            throw new IllegalArgumentException(
                    "bootstrap requires three distinct replica targets");
        }
        if (source == ReplicationBootstrapSource.VERIFIED_V44_BACKUP
                && sourcePath == null) {
            throw new IllegalArgumentException("V4.4 backup source path is required");
        }
        if (source == ReplicationBootstrapSource.EMPTY && sourcePath != null) {
            throw new IllegalArgumentException("empty bootstrap has no source path");
        }
        if (planDigest.isBlank()) {
            throw new IllegalArgumentException("plan digest must be non-blank");
        }
    }
}
