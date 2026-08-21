package org.example.generalsearch.engine;

import java.time.Duration;
import java.util.Objects;

public record SnapshotEngineConfig(
        int queueCapacity,
        int maxBatchSize,
        Duration maxBatchWait
) {
    public static final SnapshotEngineConfig DEFAULT =
            new SnapshotEngineConfig(100_000, 1_000, Duration.ofMillis(5));

    public SnapshotEngineConfig {
        if (queueCapacity <= 0) {
            throw new IllegalArgumentException("queueCapacity must be positive");
        }
        if (maxBatchSize <= 0) {
            throw new IllegalArgumentException("maxBatchSize must be positive");
        }
        Objects.requireNonNull(maxBatchWait, "maxBatchWait");
        if (maxBatchWait.isNegative()) {
            throw new IllegalArgumentException("maxBatchWait must not be negative");
        }
    }
}
