package io.github.patricklfdm.generalsearch.engine.exception;

import java.util.Objects;

/** Raised for expected conflicts and cancellation in dynamic index management. */
public final class IndexLifecycleException extends SearchEngineException {
    public enum Reason {
        ALREADY_EXISTS,
        BUILD_IN_PROGRESS,
        CANCELLED
    }

    private final String fieldName;
    private final Reason reason;

    public IndexLifecycleException(String fieldName, Reason reason) {
        super(message(requireFieldName(fieldName), Objects.requireNonNull(reason, "reason")));
        this.fieldName = fieldName;
        this.reason = reason;
    }

    public String fieldName() {
        return fieldName;
    }

    public Reason reason() {
        return reason;
    }

    private static String requireFieldName(String fieldName) {
        if (fieldName == null || fieldName.isBlank()) {
            throw new IllegalArgumentException("fieldName must not be blank");
        }
        return fieldName;
    }

    private static String message(String fieldName, Reason reason) {
        return switch (reason) {
            case ALREADY_EXISTS -> "index already exists for field: " + fieldName;
            case BUILD_IN_PROGRESS ->
                    "index build is already in progress for field: " + fieldName;
            case CANCELLED ->
                    "index build was cancelled by dropIndex: " + fieldName;
        };
    }
}
