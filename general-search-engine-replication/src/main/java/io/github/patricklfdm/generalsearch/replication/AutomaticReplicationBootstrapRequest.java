package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Pure automatic bootstrap intent; construction neither inspects nor creates files. */
public record AutomaticReplicationBootstrapRequest<K, T>(
        ReplicationBootstrapSource source, Path sourcePath,
        List<AutomaticReplicationGroupConfig<K, T>> replicas,
        Path operationDirectory, long maxSourceBytes, long maxOperationBytes
) {
    public AutomaticReplicationBootstrapRequest {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        replicas = List.copyOf(replicas);
        if ((source == ReplicationBootstrapSource.EMPTY) != (sourcePath == null)
                || replicas.size() != 3 || maxSourceBytes <= 0 || maxSourceBytes > (1L << 40)
                || maxOperationBytes <= 0 || maxOperationBytes > (1L << 40)) {
            throw new IllegalArgumentException("invalid automatic bootstrap source, targets or bounds");
        }
        var first = replicas.getFirst();
        for (int i = 0; i < replicas.size(); i++) {
            var replica = replicas.get(i);
            if (!replica.groupId().equals(first.groupId())
                    || !replica.configurationId().equals(first.configurationId())
                    || !replica.members().equals(first.members())
                    || !replica.localNodeId().equals(first.members().get(i).nodeId())) {
                throw new IllegalArgumentException("automatic targets must agree in manifest order");
            }
        }
        if (replicas.stream().map(r -> r.replicaDirectory().toAbsolutePath().normalize())
                .distinct().count() != 3) {
            throw new IllegalArgumentException("automatic replica targets must be distinct");
        }
        // Full schema/codec identities and filesystem alias checks belong to offline admission.
    }
}
