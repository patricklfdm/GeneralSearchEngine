package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import java.nio.file.Path;
import java.util.Objects;

/** Offline entry declarations. Disabled until durable admission/recovery qualification. */
public final class MembershipStorageOperations {
    private MembershipStorageOperations() {}
    private static UnsupportedOperationException disabled() {
        return new UnsupportedOperationException("V5.3 offline membership operations require Phase 2 qualification");
    }
    public static <K, T> MembershipBootstrapPlan planBootstrap(SearchEngineBuilder<K, T> builder,
            MembershipBootstrapRequest<K, T> request) {
        Objects.requireNonNull(builder, "builder"); Objects.requireNonNull(request, "request"); throw disabled();
    }
    public static <K, T> MembershipBootstrapResult applyBootstrap(SearchEngineBuilder<K, T> builder,
            MembershipBootstrapRequest<K, T> request, MembershipBootstrapPlan plan) {
        Objects.requireNonNull(builder, "builder"); Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan"); throw disabled();
    }
    public static <K, T> MembershipBootstrapResult resumeBootstrap(SearchEngineBuilder<K, T> builder,
            MembershipBootstrapRequest<K, T> request, MembershipBootstrapPlan plan) {
        Objects.requireNonNull(builder, "builder"); Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan"); throw disabled();
    }
    public static MembershipBootstrapResult readBootstrapResult(Path operationDirectory) {
        Objects.requireNonNull(operationDirectory, "operationDirectory"); throw disabled();
    }
    public static MembershipLearnerPlan planLearner(MembershipLearnerRequest request) {
        Objects.requireNonNull(request, "request"); throw disabled();
    }
    public static void applyLearner(MembershipLearnerPlan plan) { Objects.requireNonNull(plan, "plan"); throw disabled(); }
    public static void resumeLearner(MembershipLearnerPlan plan) { Objects.requireNonNull(plan, "plan"); throw disabled(); }
}
