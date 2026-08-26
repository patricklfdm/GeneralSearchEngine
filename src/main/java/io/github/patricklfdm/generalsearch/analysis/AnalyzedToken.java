package io.github.patricklfdm.generalsearch.analysis;

/**
 * One analyzed term and its increment from the previous logical position. Increment
 * zero represents a same-position alternative and is valid at the record boundary;
 * a complete token sequence must still begin with a positive increment.
 *
 * @param term normalized term emitted by the Analyzer
 * @param positionIncrement non-negative logical-position increment
 */
public record AnalyzedToken(String term, int positionIncrement) {
    /**
     * Creates an analyzed token.
     *
     * @param term normalized term emitted by the Analyzer
     * @param positionIncrement non-negative logical-position increment
     * @throws IllegalArgumentException if {@code term} is null or empty, or if
     *         {@code positionIncrement} is negative
     */
    public AnalyzedToken {
        if (term == null || term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
        if (positionIncrement < 0) {
            throw new IllegalArgumentException("positionIncrement must not be negative");
        }
    }
}
