package io.github.patricklfdm.generalsearch.durability;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/** Immutable timing and fallback diagnostics for one completed durable reopen. */
public record DurableReopenReport(
        long authoritativeCheckpointSequence,
        long recoveredSequence,
        int checkpointIndexCount,
        int loadedComponentCount,
        int rebuiltComponentCount,
        int replayCreatedIndexCount,
        DurableDerivedStateStatus derivedStatus,
        DurableReopenOutcome outcome,
        List<DurableReopenRejection> rejections,
        Duration canonicalLoadDuration,
        Duration derivedInspectionDuration,
        Duration derivedLoadDuration,
        Duration rebuildDuration,
        Duration walReplayDuration,
        Duration refreshDuration,
        Duration totalOpenDuration,
        long derivedBytesRead,
        long derivedBytesWritten,
        boolean refreshAttempted,
        boolean refreshSucceeded
) {
    /** Freezes collections and validates all counts, durations and outcomes. */
    public DurableReopenReport {
        if (authoritativeCheckpointSequence < 0
                || recoveredSequence < authoritativeCheckpointSequence
                || checkpointIndexCount < 0 || checkpointIndexCount > 100_000
                || loadedComponentCount < 0 || rebuiltComponentCount < 0
                || loadedComponentCount + (long) rebuiltComponentCount
                        != checkpointIndexCount
                || replayCreatedIndexCount < 0
                || replayCreatedIndexCount > 100_000
                || derivedBytesRead < 0 || derivedBytesWritten < 0) {
            throw new IllegalArgumentException("reopen counts or bytes are invalid");
        }
        derivedStatus = Objects.requireNonNull(derivedStatus, "derivedStatus");
        outcome = Objects.requireNonNull(outcome, "outcome");
        rejections = List.copyOf(Objects.requireNonNull(rejections, "rejections"));
        canonicalLoadDuration = duration(canonicalLoadDuration, "canonicalLoadDuration");
        derivedInspectionDuration = duration(
                derivedInspectionDuration, "derivedInspectionDuration");
        derivedLoadDuration = duration(derivedLoadDuration, "derivedLoadDuration");
        rebuildDuration = duration(rebuildDuration, "rebuildDuration");
        walReplayDuration = duration(walReplayDuration, "walReplayDuration");
        refreshDuration = duration(refreshDuration, "refreshDuration");
        totalOpenDuration = duration(totalOpenDuration, "totalOpenDuration");
        Set<Integer> ordinals = new HashSet<>();
        int previous = -1;
        for (DurableReopenRejection rejection : rejections) {
            if (!ordinals.add(rejection.ordinal()) || rejection.ordinal() <= previous
                    || rejection.ordinal() >= checkpointIndexCount) {
                throw new IllegalArgumentException(
                        "rejections must have increasing unique ordinals");
            }
            previous = rejection.ordinal();
        }
        if (refreshSucceeded && !refreshAttempted) {
            throw new IllegalArgumentException(
                    "refresh success requires an attempted refresh");
        }
        if ((outcome == DurableReopenOutcome.COMPLETE_WARM
                && (loadedComponentCount != checkpointIndexCount
                        || rebuiltComponentCount != 0 || !rejections.isEmpty()))
                || (outcome == DurableReopenOutcome.PARTIAL_FALLBACK
                && (loadedComponentCount == 0 || rebuiltComponentCount == 0))
                || (outcome == DurableReopenOutcome.FULL_FALLBACK
                && loadedComponentCount != 0)
                || (outcome == DurableReopenOutcome.NOT_APPLICABLE
                && derivedStatus != DurableDerivedStateStatus.NOT_APPLICABLE)) {
            throw new IllegalArgumentException("outcome and component counts disagree");
        }
    }

    private static Duration duration(Duration value, String name) {
        Objects.requireNonNull(value, name);
        if (value.isNegative()) {
            throw new IllegalArgumentException(name + " must not be negative");
        }
        return value;
    }
}
