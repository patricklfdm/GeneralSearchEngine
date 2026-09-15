package io.github.patricklfdm.generalsearch.replication;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** Last bounded peer observation; reachability is not a lease or quorum evidence. */
public record ReplicationPeerStatus(
        ReplicationNodeId nodeId,
        boolean reachable,
        long durableIndex,
        long matchIndex,
        long appliedIndex,
        Optional<Instant> observedAt
) {
    public ReplicationPeerStatus {
        Objects.requireNonNull(nodeId, "nodeId");
        Objects.requireNonNull(observedAt, "observedAt");
        if (durableIndex < 0 || matchIndex < 0 || appliedIndex < 0
                || matchIndex > durableIndex || appliedIndex > durableIndex) {
            throw new IllegalArgumentException("invalid peer LogIndex ordering");
        }
        if (observedAt.isEmpty() && (reachable || durableIndex != 0 || matchIndex != 0 || appliedIndex != 0)) {
            throw new IllegalArgumentException("unobserved peer must have no claimed progress or reachability");
        }
    }
}
