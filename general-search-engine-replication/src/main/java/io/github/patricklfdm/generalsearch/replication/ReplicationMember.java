package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Immutable member declaration in the fixed three-voter configuration. */
public record ReplicationMember(ReplicationNodeId nodeId, ReplicationEndpoint endpoint) {
    public ReplicationMember {
        Objects.requireNonNull(nodeId, "nodeId");
        Objects.requireNonNull(endpoint, "endpoint");
    }
}
