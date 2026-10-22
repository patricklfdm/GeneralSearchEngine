package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Full identity of one disk owner. This value grants no voting authority. */
public record MembershipIdentity(
        ReplicationNodeId nodeId, UUID storageId, ReplicationEndpoint endpoint) {
    public MembershipIdentity {
        Objects.requireNonNull(nodeId, "nodeId"); uuid(storageId);
        Objects.requireNonNull(endpoint, "endpoint"); host(endpoint.host());
    }
}
