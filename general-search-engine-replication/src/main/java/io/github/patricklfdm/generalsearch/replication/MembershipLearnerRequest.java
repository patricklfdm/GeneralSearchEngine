package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Learner staging request; its identity must later match a certified reservation. */
public record MembershipLearnerRequest(
        MembershipRoot root, MembershipIdentity identity, MembershipChangeRequest change,
        Path replicaDirectory, Path operationDirectory) {
    public MembershipLearnerRequest {
        Objects.requireNonNull(root, "root"); Objects.requireNonNull(identity, "identity"); Objects.requireNonNull(change, "change");
        require(root.equals(change.id().root()) && change.kind() != MembershipChangeKind.REMOVE
                && change.target().contains(identity), "learner outside requested history/target");
        replicaDirectory = path(replicaDirectory); operationDirectory = path(operationDirectory);
        disjoint(List.of(replicaDirectory, operationDirectory));
    }
}
