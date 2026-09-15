package fixture;

import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.replication.*;

/** Outside-artifact compile coverage of Step A's complete typed offline API. */
public final class V5AdmissionConsumer {
    private V5AdmissionConsumer() { }

    public static <K, T> ReplicationBootstrapResult bootstrap(SearchEngineBuilder<K, T> builder,
            ReplicationBootstrapRequest<K, T> request, boolean resume) {
        ReplicationBootstrapPlan plan = ReplicationStorageOperations.planBootstrap(builder, request);
        return resume ? ReplicationStorageOperations.resumeBootstrap(builder, request, plan)
                : ReplicationStorageOperations.applyBootstrap(builder, request, plan);
    }
    public static ReplicationBootstrapResult inspect(Path operation) {
        return ReplicationStorageOperations.readBootstrapResult(operation);
    }
    public static void cleanup(Path operation) {
        ReplicationCleanupPlan plan = ReplicationStorageOperations.planCleanup(operation);
        ReplicationStorageOperations.applyCleanup(plan);
    }
    public static void replace(ReplicationGroupConfig<?, ?> configuration, Path source, Path operation, boolean resume) {
        ReplicationReplacementPlan plan = ReplicationStorageOperations.planReplacement(configuration, source, operation);
        if (resume) ReplicationStorageOperations.resumeReplacement(configuration, plan);
        else ReplicationStorageOperations.applyReplacement(configuration, plan);
    }
    public static ReplicationDiagnostics diagnostics(ReplicatedSearchEngine<?, ?> engine) {
        return engine.replicationDiagnostics();
    }
    public static java.util.concurrent.CompletableFuture<Long> catchUp(ReplicatedSearchEngine<?, ?> engine, ReplicationNodeId node) {
        return engine.catchUp(node);
    }
    public static java.util.concurrent.CompletableFuture<ReplicationStatus> reconstruct(ReplicatedSearchEngine<?, ?> engine) {
        return engine.reconstructConfiguredLeader();
    }
}
