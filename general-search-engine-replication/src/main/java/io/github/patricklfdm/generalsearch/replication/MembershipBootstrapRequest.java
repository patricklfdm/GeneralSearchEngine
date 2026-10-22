package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Pure bootstrap request. Inspection/resume will verify exact absence, codecs and ownership. */
public record MembershipBootstrapRequest<K, T>(
        ReplicationGroupId groupId, String configurationId, MembershipBootstrapSource source,
        Optional<Path> sourcePath, List<MembershipBootstrapTarget<K, T>> targets,
        Path operationDirectory, long maxSourceBytes, long maxOperationBytes) {
    public MembershipBootstrapRequest {
        Objects.requireNonNull(groupId, "groupId"); uuid(groupId.value()); Objects.requireNonNull(configurationId, "configurationId");
        require(configurationId.matches("[a-z0-9][a-z0-9._-]{0,127}"), "configuration identity");
        Objects.requireNonNull(source, "source"); Objects.requireNonNull(sourcePath, "sourcePath");
        require(sourcePath.isPresent() == (source == MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP), "bootstrap source mismatch");
        sourcePath = sourcePath.map(MembershipValidation::path); operationDirectory = path(operationDirectory);
        Objects.requireNonNull(targets, "targets"); require(targets.size() >= 3 && targets.size() <= 5, "bootstrap cardinality");
        targets = List.copyOf(targets); identities(targets.stream().map(MembershipBootstrapTarget::identity).toList(), 3, 5);
        var paths = new ArrayList<Path>(); paths.add(operationDirectory); sourcePath.ifPresent(paths::add);
        for (var target : targets) { paths.add(target.replicaDirectory()); paths.add(path(target.materialization().directory())); }
        disjoint(paths); require(maxSourceBytes > 0 && maxOperationBytes > 0, "bootstrap byte bounds");
    }
}
