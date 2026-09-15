package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;
import java.util.UUID;

/** Compact projection of committed bootstrap evidence; sequence is the genesis base. */
public record ReplicationBootstrapResult(
        Path operationDirectory,
        ReplicationBootstrapPlan plan,
        String manifestDigest,
        String genesisDigest,
        UUID applicationHistory,
        long applicationSequence,
        String receiptDigest
) {
    public ReplicationBootstrapResult {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        Objects.requireNonNull(plan, "plan");
        ReplicaFormat.validHash(manifestDigest);
        ReplicaFormat.validHash(genesisDigest);
        ReplicaFormat.validHash(receiptDigest);
        Objects.requireNonNull(applicationHistory, "applicationHistory");
        if (applicationHistory.equals(new UUID(0, 0))
                || applicationSequence < 0 || applicationSequence == Long.MAX_VALUE) {
            throw new IllegalArgumentException("bootstrap requires nonzero history and a continuable base sequence");
        }
    }
}
