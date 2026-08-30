package io.github.patricklfdm.generalsearch.analysis;

/**
 * One normalized analyzed term with its logical-position increment and original-text
 * UTF-16 source range.
 *
 * <p>Offsets are zero-based and half-open: {@code [startOffset, endOffset)}. This
 * value validates only context-free invariants. Consumers validate source bounds,
 * surrogate boundaries, position order, and relationships between successive
 * tokens.</p>
 *
 * @param term normalized non-empty term emitted by the analyzer
 * @param positionIncrement non-negative increment from the previous logical position
 * @param startOffset non-negative UTF-16 start index into the original source string
 * @param endOffset exclusive UTF-16 end index, greater than {@code startOffset}
 */
public record OffsetAnalyzedToken(
        String term,
        int positionIncrement,
        int startOffset,
        int endOffset
) {
    /**
     * Creates an offset-aware analyzed token.
     *
     * @throws IllegalArgumentException if the term is null/empty, the position
     *         increment or start offset is negative, or the range is empty/reversed
     */
    public OffsetAnalyzedToken {
        if (term == null || term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
        if (positionIncrement < 0) {
            throw new IllegalArgumentException(
                    "positionIncrement must not be negative");
        }
        if (startOffset < 0) {
            throw new IllegalArgumentException("startOffset must not be negative");
        }
        if (endOffset <= startOffset) {
            throw new IllegalArgumentException(
                    "endOffset must be greater than startOffset");
        }
    }
}
