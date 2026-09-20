package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Offline, all-three automatic bootstrap and inventory-bound pre-commit cleanup. */
public final class AutomaticReplicationStorageOperations {
    private AutomaticReplicationStorageOperations() { }

    public static <K, T> ReplicationBootstrapPlan planBootstrap(SearchEngineBuilder<K, T> builder,
            AutomaticReplicationBootstrapRequest<K, T> request) {
        return AutomaticBootstrap.guarded(() -> AutomaticBootstrap.project(builder,request,true).summary());
    }
    public static <K, T> ReplicationBootstrapResult applyBootstrap(SearchEngineBuilder<K, T> builder,
            AutomaticReplicationBootstrapRequest<K, T> request, ReplicationBootstrapPlan plan) {
        return AutomaticBootstrap.apply(builder,request,plan,false);
    }
    public static <K, T> ReplicationBootstrapResult resumeBootstrap(SearchEngineBuilder<K, T> builder,
            AutomaticReplicationBootstrapRequest<K, T> request, ReplicationBootstrapPlan plan) {
        return AutomaticBootstrap.apply(builder,request,plan,true);
    }
    public static ReplicationBootstrapResult readBootstrapResult(Path operationDirectory) {
        return AutomaticBootstrap.readResult(operationDirectory);
    }
    public static ReplicationCleanupPlan planCleanup(Path operationDirectory) {
        return AutomaticBootstrapCleanup.plan(operationDirectory);
    }
    public static void applyCleanup(ReplicationCleanupPlan plan) {
        AutomaticBootstrapCleanup.apply(plan);
    }
}
