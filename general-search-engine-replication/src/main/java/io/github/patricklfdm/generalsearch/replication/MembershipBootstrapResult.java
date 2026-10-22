package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Verified committed bootstrap result; constructing a value does not verify storage. */
public record MembershipBootstrapResult(
        MembershipRoot root, String planDigest, String receiptDigest,
        long applicationSequence, Path operationDirectory) {
    public MembershipBootstrapResult {
        Objects.requireNonNull(root, "root"); digest(planDigest); digest(receiptDigest); position(applicationSequence);
        operationDirectory = path(operationDirectory);
    }
}
