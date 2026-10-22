package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Exact reviewed bootstrap plan. Target paths contain each authority/materialization pair in target order. */
public record MembershipBootstrapPlan(
        String planDigest, ReplicationGroupId groupId, List<Path> absentTargets, Path operationDirectory) {
    public MembershipBootstrapPlan {
        digest(planDigest); Objects.requireNonNull(groupId, "groupId"); uuid(groupId.value());
        Objects.requireNonNull(absentTargets, "absentTargets");
        require(absentTargets.size() >= 6 && absentTargets.size() <= 10 && absentTargets.size() % 2 == 0, "bootstrap directory pairs");
        absentTargets = absentTargets.stream().map(MembershipValidation::path).toList(); operationDirectory = path(operationDirectory);
        var paths = new ArrayList<>(absentTargets); paths.add(operationDirectory); disjoint(paths);
    }
}
