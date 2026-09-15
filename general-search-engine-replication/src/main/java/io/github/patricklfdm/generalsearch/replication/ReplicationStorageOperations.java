package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Offline replicated-storage inspection, typed bootstrap, cleanup and replacement. */
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
        Path manifest = directory.resolve("manifest.gsr");
        if (java.nio.file.Files.exists(manifest, java.nio.file.LinkOption.NOFOLLOW_LINKS)) {
            return AdmissionBootstrap.guarded(() -> {
                byte[] bytes = AdmissionPaths.read(manifest, AdmissionFormat.META);
                if (bytes.length >= ReplicaFormat.HEADER_BYTES && java.nio.ByteBuffer.wrap(bytes, 6, 2).getShort() == 1) {
                    Path normalized = AdmissionPaths.safe(directory);
                    try (var owner = AdmissionPaths.own(normalized.resolve("replica.lock"), false)) {
                        var view = AdmissionNode.read(normalized, 1L << 40);
                        return new ReplicationStorageStatus(normalized, true, true,
                                java.util.Optional.of(view.plan().manifest().group().groupId()), java.util.Optional.of(view.node()),
                                "gse-replicated", 1, 1);
                    }
                }
                return ReplicaStore.inspect(directory);
            });
        }
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

    /** Performs pure planning with the complete typed application and group input. */
    public static <K, T> ReplicationBootstrapPlan planBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationBootstrapRequest<K, T> request) {
        Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        Objects.requireNonNull(request, "request");
        return AdmissionBootstrap.plan(applicationBuilder, request);
    }

    /** Performs all-three preparation, durable global decision and local seal delivery. */
    public static <K, T> ReplicationBootstrapResult applyBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan plan) {
        Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan");
        return AdmissionBootstrap.apply(applicationBuilder, request, plan, false);
    }

    /** Performs exact-plan recovery; a committed decision never authorizes deletion. */
    public static <K, T> ReplicationBootstrapResult resumeBootstrap(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan plan) {
        Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(plan, "plan");
        return AdmissionBootstrap.apply(applicationBuilder, request, plan, true);
    }

    /** Performs codec-free committed receipt verification under operation ownership. */
    public static ReplicationBootstrapResult readBootstrapResult(Path operationDirectory) {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        return AdmissionBootstrap.readResult(operationDirectory);
    }

    /** Performs exact inventory planning for a provably uncommitted operation. */
    public static ReplicationCleanupPlan planCleanup(Path operationDirectory) {
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        return AdmissionCleanup.plan(operationDirectory);
    }

    /** Performs ownership-checked, dependency-ordered cleanup. */
    public static void applyCleanup(ReplicationCleanupPlan plan) {
        Objects.requireNonNull(plan, "plan");
        AdmissionCleanup.apply(plan);
    }

    /** Performs non-voting replacement planning from an intact, closed source. */
    public static ReplicationReplacementPlan planReplacement(
            ReplicationGroupConfig<?, ?> configuration, Path sourceReplicaDirectory,
            Path operationDirectory) {
        Objects.requireNonNull(configuration, "configuration");
        Objects.requireNonNull(sourceReplicaDirectory, "sourceReplicaDirectory");
        Objects.requireNonNull(operationDirectory, "operationDirectory");
        return AdmissionReplacement.plan(configuration, sourceReplicaDirectory, operationDirectory);
    }

    /** Performs installation of the exact replacement plan. */
    public static void applyReplacement(
            ReplicationGroupConfig<?, ?> configuration, ReplicationReplacementPlan plan) {
        Objects.requireNonNull(configuration, "configuration");
        Objects.requireNonNull(plan, "plan");
        AdmissionReplacement.apply(configuration, plan, false);
    }

    /** Performs recovery of the exact replacement plan. */
    public static void resumeReplacement(
            ReplicationGroupConfig<?, ?> configuration, ReplicationReplacementPlan plan) {
        Objects.requireNonNull(configuration, "configuration");
        Objects.requireNonNull(plan, "plan");
        AdmissionReplacement.apply(configuration, plan, true);
    }

    private static UnsupportedOperationException unavailable() {
        return new UnsupportedOperationException(
                "Legacy bootstrap overloads omit the complete application and operation authority; use the typed overloads");
    }
}
