package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;

/** Local automatic-mode configuration. Member order fixes proposer rank, not a leader. */
public record AutomaticReplicationGroupConfig<K, T>(
        ReplicationGroupId groupId, String configurationId, ReplicationNodeId localNodeId,
        List<ReplicationMember> members, Path replicaDirectory,
        DurableStorageConfig<K, T> materialization, ReplicationBounds bounds,
        AutomaticLeadershipPolicy leadershipPolicy
) {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9._-]{0,127}");

    public AutomaticReplicationGroupConfig {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(configurationId, "configurationId");
        Objects.requireNonNull(localNodeId, "localNodeId");
        Objects.requireNonNull(replicaDirectory, "replicaDirectory");
        Objects.requireNonNull(materialization, "materialization");
        Objects.requireNonNull(bounds, "bounds");
        Objects.requireNonNull(leadershipPolicy, "leadershipPolicy");
        members = List.copyOf(members);
        if (!ID.matcher(configurationId).matches() || members.size() != 3) {
            throw new IllegalArgumentException("automatic mode requires a configuration identity and three voters");
        }
        var nodes = new HashSet<ReplicationNodeId>();
        var endpoints = new HashSet<ReplicationEndpoint>();
        for (var member : members) {
            if (!nodes.add(member.nodeId()) || !endpoints.add(member.endpoint())) {
                throw new IllegalArgumentException("duplicate automatic voter or endpoint");
            }
        }
        if (!nodes.contains(localNodeId)) throw new IllegalArgumentException("local node is not a voter");
        if (replicaDirectory.toAbsolutePath().normalize()
                .equals(materialization.directory().toAbsolutePath().normalize())) {
            throw new IllegalArgumentException("authority and materialization paths must differ");
        }
        if (bounds.maxFrameBytes() < 128 * 1024 || bounds.maxInFlightPerPeer() < 2
                || bounds.snapshotChunkBytes() < 4096
                || leadershipPolicy.heartbeatIntervalMillis() < bounds.requestTimeoutMillis()
                || leadershipPolicy.operationTimeoutMillis() < 2L * bounds.requestTimeoutMillis()) {
            throw new IllegalArgumentException("bounds cannot support automatic control and timing policy");
        }
    }
}
