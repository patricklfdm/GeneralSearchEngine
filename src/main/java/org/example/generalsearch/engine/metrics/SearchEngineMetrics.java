package org.example.generalsearch.engine.metrics;

import java.time.Duration;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/** Immutable, point-in-time operational metrics for one search engine instance. */
public record SearchEngineMetrics(
        long snapshotVersion,
        int documentCount,
        int registeredIndexCount,
        int writerQueueDepth,
        int writerQueueCapacity,
        int mutationJournalLength,
        long successfulMutations,
        long failedMutations,
        long indexBuildsStarted,
        long indexBuildsSucceeded,
        long indexBuildsFailed,
        long indexBuildsCancelled,
        boolean acceptingRequests,
        Optional<Duration> lastSuccessfulIndexBuildDuration,
        Optional<IndexBuildFailure> lastIndexBuildFailure,
        List<IndexBuildMetrics> activeIndexBuilds
) {
    public SearchEngineMetrics {
        requireNonNegative(snapshotVersion, "snapshotVersion");
        requireNonNegative(documentCount, "documentCount");
        requireNonNegative(registeredIndexCount, "registeredIndexCount");
        requireNonNegative(writerQueueDepth, "writerQueueDepth");
        if (writerQueueCapacity <= 0) {
            throw new IllegalArgumentException("writerQueueCapacity must be positive");
        }
        requireNonNegative(mutationJournalLength, "mutationJournalLength");
        requireNonNegative(successfulMutations, "successfulMutations");
        requireNonNegative(failedMutations, "failedMutations");
        requireNonNegative(indexBuildsStarted, "indexBuildsStarted");
        requireNonNegative(indexBuildsSucceeded, "indexBuildsSucceeded");
        requireNonNegative(indexBuildsFailed, "indexBuildsFailed");
        requireNonNegative(indexBuildsCancelled, "indexBuildsCancelled");
        lastSuccessfulIndexBuildDuration = Objects.requireNonNull(
                lastSuccessfulIndexBuildDuration,
                "lastSuccessfulIndexBuildDuration");
        lastIndexBuildFailure = Objects.requireNonNull(
                lastIndexBuildFailure,
                "lastIndexBuildFailure");
        activeIndexBuilds = List.copyOf(activeIndexBuilds);
    }

    public int pendingIndexBuildCount() {
        return activeIndexBuilds.size();
    }

    private static void requireNonNegative(long value, String name) {
        if (value < 0) {
            throw new IllegalArgumentException(name + " must not be negative");
        }
    }
}
