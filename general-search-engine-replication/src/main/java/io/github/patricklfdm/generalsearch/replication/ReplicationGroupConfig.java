package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;

/** Immutable local view of the fixed V5.0 three-voter group. */
public record ReplicationGroupConfig<K, T>(
        ReplicationGroupId groupId,
        String configurationId,
        ReplicationNodeId localNodeId,
        ReplicationNodeId configuredLeaderId,
        List<ReplicationMember> members,
        Path replicaDirectory,
        DurableStorageConfig<K, T> materialization,
        ReplicationBounds bounds
) {
    private static final Pattern CONFIGURATION_ID =
            Pattern.compile("[a-z0-9][a-z0-9._-]{0,127}");

    public ReplicationGroupConfig {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(configurationId, "configurationId");
        Objects.requireNonNull(localNodeId, "localNodeId");
        Objects.requireNonNull(configuredLeaderId, "configuredLeaderId");
        Objects.requireNonNull(members, "members");
        Objects.requireNonNull(replicaDirectory, "replicaDirectory");
        Objects.requireNonNull(materialization, "materialization");
        Objects.requireNonNull(bounds, "bounds");
        if (!CONFIGURATION_ID.matcher(configurationId).matches()) {
            throw new IllegalArgumentException("invalid configuration identity");
        }
        members = List.copyOf(members);
        if (members.size() != 3) {
            throw new IllegalArgumentException("V5.0 requires exactly three voters");
        }
        var identities = new HashSet<ReplicationNodeId>();
        var endpoints = new HashSet<ReplicationEndpoint>();
        for (ReplicationMember member : members) {
            Objects.requireNonNull(member, "member");
            if (!identities.add(member.nodeId())) {
                throw new IllegalArgumentException("duplicate node identity");
            }
            if (!endpoints.add(member.endpoint())) {
                throw new IllegalArgumentException("duplicate member endpoint");
            }
        }
        if (!identities.contains(localNodeId)) {
            throw new IllegalArgumentException("local node is not a configured voter");
        }
        if (!identities.contains(configuredLeaderId)) {
            throw new IllegalArgumentException("configured leader is not a voter");
        }
        if (replicaDirectory.equals(materialization.directory())) {
            throw new IllegalArgumentException(
                    "replica authority and V4 materialization directories must differ");
        }
    }
}
