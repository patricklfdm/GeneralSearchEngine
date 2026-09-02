package io.github.patricklfdm.generalsearch.engine;

/** Package-private counters used only by the V4 durable evidence probes. */
record DurablePerformanceSnapshot(
        long forceGroups,
        long forcedUnits,
        int maximumForceGroupSize,
        long walAppendForceNanos,
        long storageOpenNanos,
        long checkpointLoadNanos,
        long replayAndRebuildNanos
) {
    DurablePerformanceSnapshot {
        if (forceGroups < 0 || forcedUnits < 0 || maximumForceGroupSize < 0
                || walAppendForceNanos < 0 || storageOpenNanos < 0
                || checkpointLoadNanos < 0 || replayAndRebuildNanos < 0) {
            throw new IllegalArgumentException(
                    "durable performance counters must not be negative");
        }
    }
}
