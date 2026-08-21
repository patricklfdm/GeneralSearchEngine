package org.example.generalsearch.engine.metrics;

import java.time.Duration;
import java.util.Objects;
import java.util.Optional;

/** Details of the most recent index build that failed during scan or replay. */
public record IndexBuildFailure(
        long buildId,
        String fieldName,
        String indexType,
        String exceptionType,
        Optional<String> message,
        Duration duration
) {
    public IndexBuildFailure {
        if (buildId < 0) {
            throw new IllegalArgumentException("buildId must not be negative");
        }
        fieldName = requireText(fieldName, "fieldName");
        indexType = requireText(indexType, "indexType");
        exceptionType = requireText(exceptionType, "exceptionType");
        message = Objects.requireNonNull(message, "message");
        Objects.requireNonNull(duration, "duration");
        if (duration.isNegative()) {
            throw new IllegalArgumentException("duration must not be negative");
        }
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }
}
