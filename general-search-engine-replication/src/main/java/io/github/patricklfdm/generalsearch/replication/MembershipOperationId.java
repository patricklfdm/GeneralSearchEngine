package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** History-scoped operation number; retirement never makes a number reusable. */
public record MembershipOperationId(
        MembershipRoot root, long number) {
    public MembershipOperationId {
        Objects.requireNonNull(root, "root"); require(number > 0 && number <= MAX, "operation number");
    }
}
