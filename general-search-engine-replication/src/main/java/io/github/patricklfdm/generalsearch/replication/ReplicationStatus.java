package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Immutable role and progress snapshot; indices are not application sequences. */
public record ReplicationStatus(
        ReplicationNodeId localNodeId,
        ReplicaRole role,
        ReplicaState state,
        boolean writeQuorumAvailable,
        long promisedEpoch,
        long activeEpoch,
        long lastLogIndex,
        long commitIndex,
        long appliedIndex,
        long applicationSequence,
        long retainedLogBytes,
        int pendingClientOperations
) {
    public ReplicationStatus {
        Objects.requireNonNull(localNodeId, "localNodeId");
        Objects.requireNonNull(role, "role");
        Objects.requireNonNull(state, "state");
        if (promisedEpoch < 0 || activeEpoch < 0 || lastLogIndex < 0
                || commitIndex < 0 || appliedIndex < 0 || applicationSequence < 0
                || retainedLogBytes < 0 || pendingClientOperations < 0) {
            throw new IllegalArgumentException("replication counters must not be negative");
        }
        if (activeEpoch > promisedEpoch || appliedIndex > commitIndex
                || commitIndex > lastLogIndex) {
            throw new IllegalArgumentException("invalid replication progress ordering");
        }
    }
}
