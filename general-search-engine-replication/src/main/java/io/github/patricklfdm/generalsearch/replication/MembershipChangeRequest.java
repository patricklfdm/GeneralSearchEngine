package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Exact desired stable target. The live current view determines whether this is a legal one-member change. */
public record MembershipChangeRequest(
        MembershipOperationId id, String expectedConfigurationDigest,
        MembershipChangeKind kind, List<MembershipIdentity> target) {
    public MembershipChangeRequest {
        Objects.requireNonNull(id, "id"); digest(expectedConfigurationDigest); Objects.requireNonNull(kind, "kind");
        target = identities(target, 3, 5);
    }
}
