package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;

/** Validates source-dependent offset sequence invariants for engine consumers. */
final class OffsetTokenSequenceValidator {
    private OffsetTokenSequenceValidator() {
    }

    static List<OffsetAnalyzedToken> validate(
            String fieldName,
            String source,
            List<OffsetAnalyzedToken> output
    ) {
        Objects.requireNonNull(fieldName, "fieldName");
        Objects.requireNonNull(source, "source");
        if (fieldName.isEmpty()) {
            throw new IllegalArgumentException("fieldName must not be empty");
        }
        if (output == null) {
            throw failure(fieldName, -1, "analyzer output must not be null");
        }

        List<OffsetAnalyzedToken> copy = new ArrayList<>(output.size());
        int logicalPosition = -1;
        int previousPosition = -1;
        int previousStart = -1;
        int previousEnd = -1;
        for (int index = 0; index < output.size(); index++) {
            OffsetAnalyzedToken token = output.get(index);
            if (token == null) {
                throw failure(fieldName, index, "token must not be null");
            }
            if (index == 0 && token.positionIncrement() == 0) {
                throw failure(
                        fieldName,
                        index,
                        "first positionIncrement must be positive"
                );
            }
            try {
                logicalPosition = Math.addExact(
                        logicalPosition,
                        token.positionIncrement()
                );
            } catch (ArithmeticException overflow) {
                throw failure(
                        fieldName,
                        index,
                        "logical position overflow",
                        overflow
                );
            }
            validateRange(fieldName, source, token, index);

            if (logicalPosition == previousPosition) {
                if (token.startOffset() != previousStart
                        || token.endOffset() != previousEnd) {
                    throw failure(
                            fieldName,
                            index,
                            "same-position tokens must use the same source range"
                    );
                }
            } else if (previousPosition >= 0) {
                if (token.startOffset() < previousStart
                        || token.endOffset() < previousEnd) {
                    throw failure(
                            fieldName,
                            index,
                            "later-position range boundaries must not move backward"
                    );
                }
            }

            copy.add(token);
            previousPosition = logicalPosition;
            previousStart = token.startOffset();
            previousEnd = token.endOffset();
        }
        return List.copyOf(copy);
    }

    private static void validateRange(
            String fieldName,
            String source,
            OffsetAnalyzedToken token,
            int index
    ) {
        if (token.endOffset() > source.length()) {
            throw failure(fieldName, index, "source range exceeds text length");
        }
        if (splitsSurrogatePair(source, token.startOffset())
                || splitsSurrogatePair(source, token.endOffset())) {
            throw failure(fieldName, index, "source range splits a surrogate pair");
        }
    }

    private static boolean splitsSurrogatePair(String source, int boundary) {
        return boundary > 0
                && boundary < source.length()
                && Character.isHighSurrogate(source.charAt(boundary - 1))
                && Character.isLowSurrogate(source.charAt(boundary));
    }

    private static IllegalArgumentException failure(
            String fieldName,
            int tokenIndex,
            String message
    ) {
        return failure(fieldName, tokenIndex, message, null);
    }

    private static IllegalArgumentException failure(
            String fieldName,
            int tokenIndex,
            String message,
            Throwable cause
    ) {
        String prefix = "invalid offsets for text field '" + fieldName + "'";
        if (tokenIndex >= 0) {
            prefix += " at token " + tokenIndex;
        }
        return new IllegalArgumentException(prefix + ": " + message, cause);
    }
}
