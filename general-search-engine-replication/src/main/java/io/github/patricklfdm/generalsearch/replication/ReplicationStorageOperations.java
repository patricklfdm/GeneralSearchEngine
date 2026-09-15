package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Offline replicated-storage inspection and reserved group bootstrap operations. */
public final class ReplicationStorageOperations {
    private ReplicationStorageOperations() {
    }

    /**
     * Inspects a closed replica directory without application codecs or mutation.
     * An absent directory returns an absent status; invalid or owned storage throws
     * a classified {@link ReplicationException}.
     */
    public static ReplicationStorageStatus inspect(Path directory) {
        Objects.requireNonNull(directory, "directory");
        return ReplicaStore.inspect(directory);
    }

    /**
     * Legacy under-specified intent, permanently reserved. Use the typed builder
     * and {@link ReplicationBootstrapRequest} overload after Step B acceptance.
     */
    public static ReplicationBootstrapPlan planBootstrap(
            ReplicationGroupId groupId,
            String configurationId,
            ReplicationBootstrapSource source,
            Path sourcePath,
            java.util.List<Path> absentReplicaTargets
    ) {
        Objects.requireNonNull(groupId, "groupId");
        Objects.requireNonNull(configurationId, "configurationId");
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(absentReplicaTargets, "absentReplicaTargets");
        throw unavailable();
    }

    /** Legacy under-specified apply; use the typed request overload after Step B. */
    public static void applyBootstrap(ReplicationBootstrapPlan plan) {
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    /** Reserved pure planning with the complete typed application and group input. */
    public static <K, T> ReplicationBootstrapPlan planBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationBootstrapRequest<K, T> request) {
        Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        Objects.requireNonNull(request, "request");
        throw unavailable();
    }

    /** Reserved all-three preparation, durable global decision and local seal delivery. */
    public static <K, T> ReplicationBootstrapResult applyBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan plan) {
        Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    /** Reserved exact-plan recovery; a committed decision never authorizes deletion. */
    public static <K, T> ReplicationBootstrapResult resumeBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan plan) {
        Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    /** Reserved codec-free committed receipt verification under operation ownership. */
    public static ReplicationBootstrapResult readBootstrapResult(Path operationDirectory) {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        throw unavailable();
    }

    /** Reserved exact inventory planning for a provably uncommitted operation. */
    public static ReplicationCleanupPlan planCleanup(Path operationDirectory) {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        throw unavailable();
    }

    /** Reserved ownership-checked, dependency-ordered cleanup. */
    public static void applyCleanup(ReplicationCleanupPlan plan) {
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    /** Reserved non-voting replacement planning from an intact, closed source. */
    public static ReplicationReplacementPlan planReplacement(
            ReplicationGroupConfig<?, ?> configuration, Path sourceReplicaDirectory,
            Path operationDirectory) {
        Objects.requireNonNull(configuration, "configuration");
        Objects.requireNonNull(sourceReplicaDirectory, "sourceReplicaDirectory");
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        throw unavailable();
    }

    /** Reserved installation of the exact replacement plan. */
    public static void applyReplacement(
            ReplicationGroupConfig<?, ?> configuration, ReplicationReplacementPlan plan) {
        Objects.requireNonNull(configuration, "configuration");
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    /** Reserved recovery of the exact replacement plan. */
    public static void resumeReplacement(
            ReplicationGroupConfig<?, ?> configuration, ReplicationReplacementPlan plan) {
        Objects.requireNonNull(configuration, "configuration");
        Objects.requireNonNull(plan, "plan");
        throw unavailable();
    }

    private static UnsupportedOperationException unavailable() {
        return new UnsupportedOperationException(
                "Typed offline authority requires public-admission Step B; legacy bootstrap overloads remain reserved");
    }
}
