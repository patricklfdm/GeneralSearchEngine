package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import java.util.UUID;

/** Immutable replicated-group identity. */
public record ReplicationGroupId(UUID value) {
    public ReplicationGroupId {
        Objects.requireNonNull(value, "value");
    }
}
