package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;

/** Exact offline same-NodeId replacement intent; a replacement begins non-voting. */
public record ReplicationReplacementPlan(
        Path operationDirectory,
        Path sourceReplicaDirectory,
        ReplicationNodeId replacementNode,
        Path absentTarget,
        String manifestDigest,
        String sourceInventoryDigest,
        String planDigest
) {
    public ReplicationReplacementPlan {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        Objects.requireNonNull(sourceReplicaDirectory, "sourceReplicaDirectory");
        Objects.requireNonNull(replacementNode, "replacementNode");
        Objects.requireNonNull(absentTarget, "absentTarget");
        ReplicaFormat.validHash(manifestDigest);
        ReplicaFormat.validHash(sourceInventoryDigest);
        ReplicaFormat.validHash(planDigest);
        if (sourceReplicaDirectory.equals(absentTarget)) {
            throw new IllegalArgumentException("replacement source and target must differ");
        }
    }
}
