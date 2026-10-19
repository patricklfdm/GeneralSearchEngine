package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Read/token failure; conveys no retry decision about any earlier mutation. */
public final class ReplicaReadException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    /** Stable token/view-specific rejection classifications. */
    public enum Reason {
        INVALID_TOKEN, UNSUPPORTED_TOKEN_VERSION, INCOMPATIBLE_HISTORY,
        PROGRESS_NOT_REACHED, VIEW_NOT_ACTIVE
    }
    private final Reason reason;

    public ReplicaReadException(Reason reason, String message) {
        this(reason, message, null);
    }
    public ReplicaReadException(Reason reason, String message, Throwable cause) {
        super(Objects.requireNonNull(message, "message"), cause);
        this.reason = Objects.requireNonNull(reason, "reason");
    }
    public Reason reason() { return reason; }
}
