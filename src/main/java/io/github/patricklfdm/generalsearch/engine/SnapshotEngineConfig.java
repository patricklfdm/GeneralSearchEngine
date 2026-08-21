package io.github.patricklfdm.generalsearch.engine;

import java.time.Duration;
import java.util.Objects;

/**
 * Writer queue and mutation batching configuration.
 *
 * @param queueCapacity maximum accepted operations waiting for the writer
 * @param maxBatchSize maximum mutations published in one batch
 * @param maxBatchWait maximum time spent waiting to fill a partial batch
 */
public record SnapshotEngineConfig(
        int queueCapacity,
        int maxBatchSize,
        Duration maxBatchWait
) {
    /** Default configuration suitable for general application use. */
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
