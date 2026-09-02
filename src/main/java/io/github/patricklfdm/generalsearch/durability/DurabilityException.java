package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.OptionalLong;

/** Runtime failure with a stable durability category and optional sequence identity. */
public final class DurabilityException extends RuntimeException {
    /** Stable V4.0 failure categories. */
    public enum Reason {
        STORAGE_IN_USE,
        STORAGE_ACCESS,
        UNSUPPORTED_FILESYSTEM,
        INCOMPATIBLE_STORAGE,
        CORRUPT_CHECKPOINT,
        CORRUPT_WAL,
        CODEC_FAILURE,
        REPLAY_FAILURE,
        INDEX_REBUILD_FAILURE,
        IO_FAILURE,
        CAPACITY_EXCEEDED,
        SEQUENCE_EXHAUSTED,
        CLOSED
    }

    private final Reason reason;
    private final OptionalLong sequence;

    /** Creates a failure without a sequence identity. */
    public DurabilityException(Reason reason, String message) {
        this(reason, OptionalLong.empty(), message, null);
    }

    /** Creates a failure without a sequence identity and retains its cause. */
    public DurabilityException(Reason reason, String message, Throwable cause) {
        this(reason, OptionalLong.empty(), message, cause);
    }

    /** Creates a failure associated with one allocated sequence. */
    public DurabilityException(Reason reason, long sequence, String message) {
        this(reason, OptionalLong.of(sequence), message, null);
    }

    /** Creates a failure associated with one allocated sequence and its cause. */
    public DurabilityException(
            Reason reason,
            long sequence,
            String message,
            Throwable cause
    ) {
        this(reason, OptionalLong.of(sequence), message, cause);
    }

    private DurabilityException(
            Reason reason,
            OptionalLong sequence,
            String message,
            Throwable cause
    ) {
        super(Objects.requireNonNull(message, "message"), cause);
        this.reason = Objects.requireNonNull(reason, "reason");
        this.sequence = Objects.requireNonNull(sequence, "sequence");
    }

    /** Returns the stable failure category. */
    public Reason reason() {
        return reason;
    }

    /** Returns the affected sequence when allocation had already occurred. */
    public OptionalLong sequence() {
        return sequence;
    }
}
