package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Complete typed offline intent, in manifest member order; not permission to write. */
public record ReplicationBootstrapRequest<K, T>(
        ReplicationBootstrapSource source,
        Path sourcePath,
        List<ReplicationGroupConfig<K, T>> replicas,
        Path operationDirectory,
        long maxSourceBytes,
        long maxOperationBytes
) {
    public ReplicationBootstrapRequest {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        replicas = List.copyOf(replicas);
        if ((source == ReplicationBootstrapSource.EMPTY) != (sourcePath == null)) {
            throw new IllegalArgumentException("only backup bootstrap requires a source path");
        }
        if (replicas.size() != 3) {
            throw new IllegalArgumentException("bootstrap requires exactly three local configurations");
        }
        for (int i = 0; i < 3; i++) {
            var replica = replicas.get(i);
            var first = replicas.getFirst();
            if (!replica.groupId().equals(first.groupId())
                    || !replica.configurationId().equals(first.configurationId())
                    || !replica.configuredLeaderId().equals(first.configuredLeaderId())
                    || !replica.members().equals(first.members())
                    || !replica.localNodeId().equals(first.members().get(i).nodeId())) {
                throw new IllegalArgumentException("configurations must agree and follow manifest member order");
            }
        }
        if (replicas.stream().map(ReplicationGroupConfig::replicaDirectory).distinct().count() != 3) {
            throw new IllegalArgumentException("replica targets must be distinct");
        }
        if (maxSourceBytes <= 0 || maxSourceBytes > (1L << 40)
                || maxOperationBytes <= 0 || maxOperationBytes > (1L << 40)) {
            throw new IllegalArgumentException("bootstrap byte bounds must be between 1 and 1 TiB");
        }
        // Codec identity, full configuration and filesystem aliases are revalidated
        // by Step B planning/apply; constructing this value invokes no user codec.
    }
}
