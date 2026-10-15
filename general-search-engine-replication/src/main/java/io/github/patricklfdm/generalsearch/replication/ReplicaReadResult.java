package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Callback result with the actual captured policy/progress, distinct from application sequence. */
public record ReplicaReadResult<R>(R value, ReplicaReadPolicy policy,
        ReplicaReadToken progress, long applicationSequence) {
    public ReplicaReadResult {
        Objects.requireNonNull(policy, "policy");
        Objects.requireNonNull(progress, "progress");
        if (applicationSequence < 0) throw new IllegalArgumentException("negative application sequence");
    }
}
