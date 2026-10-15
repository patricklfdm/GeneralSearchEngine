package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import java.util.Optional;

/** Policy and bounded progress wait; zero wait still permits ordinary admission queueing. */
public record ReplicaReadOptions(ReplicaReadPolicy policy, Optional<ReplicaReadToken> minimum,
        int waitTimeoutMillis) {
    public ReplicaReadOptions {
        Objects.requireNonNull(policy, "policy");
        Objects.requireNonNull(minimum, "minimum");
        if (policy == ReplicaReadPolicy.AT_LEAST_INDEX) {
            if (minimum.isEmpty() || waitTimeoutMillis < 0 || waitTimeoutMillis > 60_000)
                throw new IllegalArgumentException("minimum read requires token and wait in [0,60000]");
        } else if (minimum.isPresent() || waitTimeoutMillis != 0) {
            throw new IllegalArgumentException("strong/stale reads require empty minimum and zero wait");
        }
    }
}
