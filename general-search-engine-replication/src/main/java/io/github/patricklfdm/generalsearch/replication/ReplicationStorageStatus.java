package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;
import java.util.Optional;

/** Codec-free structural identity reported without opening replica authority. */
public record ReplicationStorageStatus(
        Path directory,
        boolean present,
        boolean structurallyValid,
        Optional<ReplicationGroupId> groupId,
        Optional<ReplicationNodeId> nodeId,
        String formatFamily,
        int formatMajor,
        int formatMinor
) {
    public ReplicationStorageStatus {
        Objects.requireNonNull(directory, "directory");
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(nodeId, "nodeId");
        Objects.requireNonNull(formatFamily, "formatFamily");
        if (formatMajor < 0 || formatMinor < 0) {
            throw new IllegalArgumentException("format numbers must not be negative");
        }
        if (!present && (structurallyValid || groupId.isPresent() || nodeId.isPresent())) {
            throw new IllegalArgumentException("absent storage cannot carry authority");
        }
    }
}
