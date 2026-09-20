package io.github.patricklfdm.generalsearch.replication;

import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

/** Consistent local observations. Neither leader hints nor timestamps establish a quorum. */
public record AutomaticReplicationStatus(
        ReplicationNodeId localNodeId, AutomaticReplicationState state,
        Optional<ReplicationNodeId> observedLeader, Optional<ReplicationNodeId> promisedLeader,
        long promisedEpoch, UUID promisedIncarnation, long activeEpoch,
        long provenIndex, long appliedIndex, long applicationSequence, int pendingOperations,
        Optional<Instant> lastQuorumSuccess, List<ReplicationPeerStatus> peers
) {
    private static final UUID ZERO = new UUID(0, 0);

    public AutomaticReplicationStatus {
        Objects.requireNonNull(localNodeId, "localNodeId");
        Objects.requireNonNull(state, "state");
        Objects.requireNonNull(observedLeader, "observedLeader");
        Objects.requireNonNull(promisedLeader, "promisedLeader");
        Objects.requireNonNull(promisedIncarnation, "promisedIncarnation");
        Objects.requireNonNull(lastQuorumSuccess, "lastQuorumSuccess");
        peers = List.copyOf(peers);
        var nodes = new HashSet<ReplicationNodeId>();
        nodes.add(localNodeId);
        if (peers.size() != 2 || peers.stream().anyMatch(peer -> !nodes.add(peer.nodeId()))) {
            throw new IllegalArgumentException("status requires two distinct peers excluding self");
        }
        if (observedLeader.filter(node -> !nodes.contains(node)).isPresent()
                || promisedLeader.filter(node -> !nodes.contains(node)).isPresent()
                || promisedEpoch < 0 || activeEpoch < 0 || activeEpoch > promisedEpoch
                || provenIndex < 0 || appliedIndex < 0 || appliedIndex > provenIndex
                || applicationSequence < 0 || pendingOperations < 0) {
            throw new IllegalArgumentException("invalid automatic status identity or progress");
        }
        if (promisedEpoch <= 1 ? promisedLeader.isPresent() || !ZERO.equals(promisedIncarnation)
                : promisedLeader.isEmpty() || ZERO.equals(promisedIncarnation)) {
            throw new IllegalArgumentException("promise must bind a real campaign or genesis");
        }
        if ((state == AutomaticReplicationState.LEADER_READY) != (activeEpoch > 0)
                || activeEpoch > 0 && (activeEpoch != promisedEpoch
                || !promisedLeader.equals(Optional.of(localNodeId)))) {
            throw new IllegalArgumentException("active leadership must match the local promise");
        }
        if (state == AutomaticReplicationState.STOPPED && (promisedEpoch != 0
                || provenIndex != 0 || appliedIndex != 0 || applicationSequence != 0
                || pendingOperations != 0 || observedLeader.isPresent() || lastQuorumSuccess.isPresent()
                || peers.stream().anyMatch(peer -> peer.observedAt().isPresent()))) {
            throw new IllegalArgumentException("stopped handle cannot claim initialized progress");
        }
    }
}
