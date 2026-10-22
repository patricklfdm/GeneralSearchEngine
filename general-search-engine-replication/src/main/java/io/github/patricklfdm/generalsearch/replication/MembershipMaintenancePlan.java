package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Observation only. Drain must revalidate a fresh surviving majority and current configuration. */
public record MembershipMaintenancePlan(
        MembershipRoot root, String configurationDigest, ReplicationNodeId target,
        UUID nonce, ReplicaReadToken observedCut, List<ReplicationNodeId> readySurvivors) {
    public MembershipMaintenancePlan {
        Objects.requireNonNull(root, "root"); digest(configurationDigest); Objects.requireNonNull(target, "target");
        uuid(nonce); token(root, observedCut); Objects.requireNonNull(readySurvivors, "readySurvivors");
        require(readySurvivors.size() >= 2 && readySurvivors.size() <= 4, "survivor cardinality");
        readySurvivors = List.copyOf(readySurvivors);
        ReplicationNodeId previous = null;
        for (var node : readySurvivors) {
            require(!node.equals(target) && (previous == null || previous.compareTo(node) < 0), "invalid survivor set");
            previous = node;
        }
    }
}
