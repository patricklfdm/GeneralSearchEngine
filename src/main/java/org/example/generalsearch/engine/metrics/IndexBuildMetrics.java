package org.example.generalsearch.engine.metrics;

import java.time.Duration;
import java.util.Objects;

/** A point-in-time view of an index build that has not been published yet. */
public record IndexBuildMetrics(
        long buildId,
        String fieldName,
        String indexType,
        long baseSnapshotVersion,
        Duration elapsed
) {
    public IndexBuildMetrics {
        if (buildId < 0) {
            throw new IllegalArgumentException("buildId must not be negative");
        }
        fieldName = requireText(fieldName, "fieldName");
        indexType = requireText(indexType, "indexType");
        if (baseSnapshotVersion < 0) {
            throw new IllegalArgumentException(
                    "baseSnapshotVersion must not be negative");
        }
        Objects.requireNonNull(elapsed, "elapsed");
        if (elapsed.isNegative()) {
            throw new IllegalArgumentException("elapsed must not be negative");
        }
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }
}
