package io.github.patricklfdm.generalsearch.durability;

import java.time.Duration;
import java.util.Objects;
import java.util.Optional;

/** Immutable durability-specific operational snapshot. */
public final class DurabilityMetrics {
    private final DurabilityStatus status;
    private final long currentSequence;
    private final long checkpointSequence;
    private final long walGeneration;
    private final long walRecords;
    private final long walBytes;
    private final long retainedBytes;
    private final RecoverySource recoverySource;
    private final long replayedRecords;
    private final Duration recoveryDuration;
    private final Duration indexRebuildDuration;
    private final Optional<DurabilityException.Reason> lastCheckpointFailure;

    /** Creates one fully specified immutable metrics value. */
    public DurabilityMetrics(
            DurabilityStatus status,
            long currentSequence,
            long checkpointSequence,
            long walGeneration,
            long walRecords,
            long walBytes,
            long retainedBytes,
            RecoverySource recoverySource,
            long replayedRecords,
            Duration recoveryDuration,
            Duration indexRebuildDuration,
            Optional<DurabilityException.Reason> lastCheckpointFailure
    ) {
        this.status = Objects.requireNonNull(status, "status");
        this.currentSequence = nonNegative(currentSequence, "currentSequence");
        this.checkpointSequence = nonNegative(
                checkpointSequence, "checkpointSequence");
        this.walGeneration = nonNegative(walGeneration, "walGeneration");
        this.walRecords = nonNegative(walRecords, "walRecords");
        this.walBytes = nonNegative(walBytes, "walBytes");
        this.retainedBytes = nonNegative(retainedBytes, "retainedBytes");
        this.recoverySource = Objects.requireNonNull(recoverySource, "recoverySource");
        this.replayedRecords = nonNegative(replayedRecords, "replayedRecords");
        this.recoveryDuration = nonNegative(
                Objects.requireNonNull(recoveryDuration, "recoveryDuration"),
                "recoveryDuration");
        this.indexRebuildDuration = nonNegative(
                Objects.requireNonNull(indexRebuildDuration, "indexRebuildDuration"),
                "indexRebuildDuration");
        this.lastCheckpointFailure = Objects.requireNonNull(
                lastCheckpointFailure, "lastCheckpointFailure");
    }

    public DurabilityStatus status() {
        return status;
    }

    public long currentSequence() {
        return currentSequence;
    }

    public long checkpointSequence() {
        return checkpointSequence;
    }

    public long walGeneration() {
        return walGeneration;
    }

    public long walRecords() {
        return walRecords;
    }

    public long walBytes() {
        return walBytes;
    }

    public long retainedBytes() {
        return retainedBytes;
    }

    public RecoverySource recoverySource() {
        return recoverySource;
    }

    public long replayedRecords() {
        return replayedRecords;
    }

    public Duration recoveryDuration() {
        return recoveryDuration;
    }

    public Duration indexRebuildDuration() {
        return indexRebuildDuration;
    }

    public Optional<DurabilityException.Reason> lastCheckpointFailure() {
        return lastCheckpointFailure;
    }

    private static long nonNegative(long value, String name) {
        if (value < 0) {
            throw new IllegalArgumentException(name + " must not be negative");
        }
        return value;
    }

    private static Duration nonNegative(Duration value, String name) {
        if (value.isNegative()) {
            throw new IllegalArgumentException(name + " must not be negative");
        }
        return value;
    }
}
