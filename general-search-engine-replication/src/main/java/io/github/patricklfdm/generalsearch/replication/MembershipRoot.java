package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Immutable history identity; the manifest digest is the embedded ROOT checksum. */
public record MembershipRoot(
        ReplicationGroupId groupId, UUID historyId, String manifestDigest) {
    public MembershipRoot {
        Objects.requireNonNull(groupId, "groupId"); uuid(groupId.value()); uuid(historyId); digest(manifestDigest);
    }
}
