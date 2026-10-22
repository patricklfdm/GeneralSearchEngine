package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Exact verified learner plan; not a general-purpose deletion capability. */
public record MembershipLearnerPlan(
        String planDigest, MembershipLearnerRequest request) {
    public MembershipLearnerPlan {
        digest(planDigest); Objects.requireNonNull(request, "request");
    }
}
