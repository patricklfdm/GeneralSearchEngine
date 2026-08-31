package io.github.patricklfdm.generalsearch.engine.exception;

import java.util.Objects;

/** Raised when the built-in engine rejects an opaque search-after cursor. */
public final class SearchCursorException extends SearchEngineException {
    /** Stable non-sensitive reason for cursor rejection. */
    public enum Reason {
        UNSUPPORTED_CURSOR,
        DIFFERENT_ENGINE,
        DIFFERENT_REQUEST,
        STALE_SNAPSHOT
    }

    private final Reason reason;

    /**
     * Creates a cursor rejection without exposing cursor internals.
     *
     * @param reason non-null rejection reason
     * @throws NullPointerException when {@code reason} is null
     */
    public SearchCursorException(Reason reason) {
        super(message(Objects.requireNonNull(reason, "reason")));
        this.reason = reason;
    }

    /** @return stable cursor rejection reason */
    public Reason reason() {
        return reason;
    }

    private static String message(Reason reason) {
        return switch (reason) {
            case UNSUPPORTED_CURSOR -> "search cursor is unsupported";
            case DIFFERENT_ENGINE -> "search cursor belongs to another engine";
            case DIFFERENT_REQUEST -> "search cursor belongs to another request";
            case STALE_SNAPSHOT -> "search cursor snapshot is stale";
        };
    }
}
