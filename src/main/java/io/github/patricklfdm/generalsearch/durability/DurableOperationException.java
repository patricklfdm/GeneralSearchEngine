package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.OptionalLong;

/** Runtime failure when no trustworthy structural report can be constructed. */
public final class DurableOperationException extends RuntimeException {
    /** Stable V4.1 operational failure categories. */
    public enum Reason {
        STORAGE_IN_USE,
        SOURCE_INVALID,
        BACKUP_INVALID,
        IDENTITY_MISMATCH,
        TARGET_EXISTS,
        TARGET_INVALID,
        OPERATION_IN_PROGRESS,
        UNSUPPORTED_FORMAT,
        UNSUPPORTED_FILESYSTEM,
        CAPACITY_EXCEEDED,
        IO_FAILURE,
        CLOSED
    }

    private final Reason reason;
    private final OptionalLong sequence;

    /** Creates an operational failure and retains its optional sequence and cause. */
    public DurableOperationException(
            Reason reason,
            OptionalLong sequence,
            Throwable cause
    ) {
        super(Objects.requireNonNull(reason, "reason").name(), cause);
        this.reason = reason;
        this.sequence = Objects.requireNonNull(sequence, "sequence");
        if (sequence.isPresent() && sequence.getAsLong() < 0) {
            throw new IllegalArgumentException("sequence must not be negative");
        }
    }

    /** Returns the stable operational failure category. */
    public Reason reason() {
        return reason;
    }

    /** Returns the known source or backup sequence, when one was established. */
    public OptionalLong sequence() {
        return sequence;
    }
}
