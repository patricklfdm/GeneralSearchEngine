package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Pure local configuration. Discovery seeds cannot assign voter rights. */
public record MembershipReplicaConfig<K, T>(
        MembershipRoot root, MembershipIdentity localIdentity, List<MembershipIdentity> seedPeers,
        Path replicaDirectory, DurableStorageConfig<K, T> materialization, ReplicationBounds bounds,
        AutomaticLeadershipPolicy leadershipPolicy) {
    public MembershipReplicaConfig {
        Objects.requireNonNull(root, "root"); Objects.requireNonNull(localIdentity, "localIdentity");
        seedPeers = identities(seedPeers, 0, 5);
        var known = new ArrayList<>(seedPeers); known.add(localIdentity);
        known.sort(Comparator.comparing(MembershipIdentity::nodeId)); identities(known, 1, 6);
        replicaDirectory = path(replicaDirectory); Objects.requireNonNull(materialization, "materialization");
        disjoint(List.of(replicaDirectory, path(materialization.directory())));
        Objects.requireNonNull(bounds, "bounds"); Objects.requireNonNull(leadershipPolicy, "leadershipPolicy");
        require(bounds.maxFrameBytes() >= 128 * 1024 && bounds.maxInFlightPerPeer() >= 2
                && bounds.snapshotChunkBytes() >= 4096
                && leadershipPolicy.heartbeatIntervalMillis() >= bounds.requestTimeoutMillis()
                && leadershipPolicy.operationTimeoutMillis() >= 2L * bounds.requestTimeoutMillis(),
                "bounds cannot support membership control and timing");
    }
}
