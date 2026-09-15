package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Stable classified replication failure. */
public final class ReplicationException extends RuntimeException {
    /** Public failure categories; messages are diagnostic, not API. */
    public enum Reason {
        NOT_CONFIGURED_LEADER,
        QUORUM_UNAVAILABLE,
        STALE_EPOCH,
        CONFLICTING_HISTORY,
        CAPACITY_EXCEEDED,
        PROTOCOL_MISMATCH,
        INTEGRITY_FAILURE,
        STORAGE_FAILURE,
        CLOSED
    }

    private final Reason reason;

    public ReplicationException(Reason reason, String message) {
        super(message);
        this.reason = Objects.requireNonNull(reason, "reason");
    }

    public ReplicationException(Reason reason, String message, Throwable cause) {
        super(message, cause);
        this.reason = Objects.requireNonNull(reason, "reason");
    }

    public Reason reason() {
        return reason;
    }
}
