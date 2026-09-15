package io.github.patricklfdm.generalsearch.replication;

import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

/** Consistent local snapshot and the two remote peers in manifest order. */
public record ReplicationDiagnostics(
        ReplicationGroupId groupId,
        String configurationId,
        Optional<String> manifestDigest,
        UUID incarnation,
        ReplicationStatus local,
        long recoveryFloor,
        boolean snapshotInstalling,
        List<ReplicationPeerStatus> peers,
        Optional<Instant> lastQuorumSuccess,
        Optional<ReplicationException.Reason> lastFailure
) {
    public ReplicationDiagnostics {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(configurationId, "configurationId");
        Objects.requireNonNull(manifestDigest, "manifestDigest").ifPresent(ReplicaFormat::validHash);
        Objects.requireNonNull(incarnation, "incarnation");
        Objects.requireNonNull(local, "local");
        Objects.requireNonNull(lastQuorumSuccess, "lastQuorumSuccess");
        Objects.requireNonNull(lastFailure, "lastFailure");
        peers = List.copyOf(peers);
        if (!configurationId.matches("[a-z0-9][a-z0-9._-]{0,127}")) {
            throw new IllegalArgumentException("invalid configuration identity");
        }
        if (recoveryFloor < 0 || recoveryFloor > local.appliedIndex()) {
            throw new IllegalArgumentException("recovery floor must be within the applied prefix");
        }
        if (peers.size() != 2 || peers.get(0).nodeId().equals(peers.get(1).nodeId())
                || peers.stream().anyMatch(peer -> peer.nodeId().equals(local.localNodeId()))) {
            throw new IllegalArgumentException("diagnostics require two distinct remote peers");
        }
        if (manifestDigest.isEmpty() && !incarnation.equals(new UUID(0, 0))) {
            throw new IllegalArgumentException("uninitialized diagnostics have zero incarnation");
        }
    }
}
