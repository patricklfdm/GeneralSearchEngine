package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** One absent authority/materialization pair; existence is verified by offline admission. */
public record MembershipBootstrapTarget<K, T>(
        MembershipIdentity identity, Path replicaDirectory, DurableStorageConfig<K, T> materialization) {
    public MembershipBootstrapTarget {
        Objects.requireNonNull(identity, "identity"); replicaDirectory = path(replicaDirectory);
        Objects.requireNonNull(materialization, "materialization");
        disjoint(List.of(replicaDirectory, path(materialization.directory())));
    }
}
