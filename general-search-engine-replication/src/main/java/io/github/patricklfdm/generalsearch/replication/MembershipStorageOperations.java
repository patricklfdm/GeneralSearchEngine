package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import java.nio.file.Path;
import java.util.Objects;

/** Offline original bootstrap planning, recovery and result inspection. Learner entry remains disabled. */
public final class MembershipStorageOperations {
    private MembershipStorageOperations() {}
    private static UnsupportedOperationException disabled() {
        return new UnsupportedOperationException("V5.3 learner operations require Phase 3 qualification");
    }
    /** Persist one reviewed typed plan and history; voter directories remain absent. */
    public static <K, T> MembershipBootstrapPlan planBootstrap(SearchEngineBuilder<K, T> builder,
            MembershipBootstrapRequest<K, T> request) {
        Objects.requireNonNull(builder, "builder"); Objects.requireNonNull(request, "request");
        var captured = builder.configuration();
        return AdmissionBootstrap.guarded(() -> MembershipBootstrapCoordinator.plan(captured, request, e -> {}));
    }
    /** Prepare every original voter, force the global decision and deliver local seals. */
    public static <K, T> MembershipBootstrapResult applyBootstrap(SearchEngineBuilder<K, T> builder,
            MembershipBootstrapRequest<K, T> request, MembershipBootstrapPlan plan) {
        Objects.requireNonNull(builder, "builder"); Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan");
        var captured = builder.configuration();
        return AdmissionBootstrap.guarded(() -> MembershipBootstrapCoordinator.apply(captured, request, plan, false, e -> {}));
    }
    /** Recover the exact original plan, preserving completed voters and their live stores. */
    public static <K, T> MembershipBootstrapResult resumeBootstrap(SearchEngineBuilder<K, T> builder,
            MembershipBootstrapRequest<K, T> request, MembershipBootstrapPlan plan) {
        Objects.requireNonNull(builder, "builder"); Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan");
        var captured = builder.configuration();
        return AdmissionBootstrap.guarded(() -> MembershipBootstrapCoordinator.apply(captured, request, plan, true, e -> {}));
    }
    /** Read original completed authority without claiming current runtime readiness. */
    public static MembershipBootstrapResult readBootstrapResult(Path operationDirectory) {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        return AdmissionBootstrap.guarded(() -> MembershipBootstrapCoordinator.readResult(operationDirectory));
    }
    public static MembershipLearnerPlan planLearner(MembershipLearnerRequest request) {
        Objects.requireNonNull(request, "request"); throw disabled();
    }
    public static void applyLearner(MembershipLearnerPlan plan) { Objects.requireNonNull(plan, "plan"); throw disabled(); }
    public static void resumeLearner(MembershipLearnerPlan plan) { Objects.requireNonNull(plan, "plan"); throw disabled(); }
}
