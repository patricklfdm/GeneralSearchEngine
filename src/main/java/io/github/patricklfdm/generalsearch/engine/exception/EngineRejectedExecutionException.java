package io.github.patricklfdm.generalsearch.engine.exception;

import java.util.Objects;
import java.util.concurrent.RejectedExecutionException;

/** Raised when an asynchronous operation cannot be accepted by the writer. */
public final class EngineRejectedExecutionException extends RejectedExecutionException {
    public enum Reason {
        CLOSED,
        QUEUE_FULL
    }

    private final Reason reason;

    public EngineRejectedExecutionException(Reason reason) {
        super(message(Objects.requireNonNull(reason, "reason")));
        this.reason = reason;
    }

    public Reason reason() {
        return reason;
    }

    private static String message(Reason reason) {
        return switch (reason) {
            case CLOSED -> "engine is closed";
            case QUEUE_FULL -> "writer queue is full";
        };
    }
}
