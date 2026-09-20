package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Declaration-only automatic storage operations; every entry rejects before IO in Phase 1. */
public final class AutomaticReplicationStorageOperations {
    private AutomaticReplicationStorageOperations() { }

    public static <K, T> ReplicationBootstrapPlan planBootstrap(SearchEngineBuilder<K, T> builder,
            AutomaticReplicationBootstrapRequest<K, T> request) {
        throw AutomaticFoundation.unavailable();
    }
    public static <K, T> ReplicationBootstrapResult applyBootstrap(SearchEngineBuilder<K, T> builder,
            AutomaticReplicationBootstrapRequest<K, T> request, ReplicationBootstrapPlan plan) {
        throw AutomaticFoundation.unavailable();
    }
    public static <K, T> ReplicationBootstrapResult resumeBootstrap(SearchEngineBuilder<K, T> builder,
            AutomaticReplicationBootstrapRequest<K, T> request, ReplicationBootstrapPlan plan) {
        throw AutomaticFoundation.unavailable();
    }
    public static ReplicationBootstrapResult readBootstrapResult(Path operationDirectory) {
        throw AutomaticFoundation.unavailable();
    }
    public static ReplicationCleanupPlan planCleanup(Path operationDirectory) {
        throw AutomaticFoundation.unavailable();
    }
    public static void applyCleanup(ReplicationCleanupPlan plan) {
        throw AutomaticFoundation.unavailable();
    }
}
