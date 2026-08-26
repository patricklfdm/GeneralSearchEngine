package io.github.patricklfdm.generalsearch.search;

import java.util.Objects;

/**
 * Immutable top-level explanation for one existing document.
 *
 * @param <T> document type
 */
public final class SearchExplanation<T> {
    private final T document;
    private final boolean matched;
    private final double score;
    private final ExplanationNode detail;

    /**
     * Creates a document explanation whose root detail mirrors its match and score.
     *
     * @param document non-null retained document
     * @param matched whether the request matched the document
     * @param score finite non-negative score, zero when unmatched
     * @param detail non-null root explanation node with matching match and score values
     * @throws NullPointerException when {@code document} or {@code detail} is null
     * @throws IllegalArgumentException when the score is invalid, non-zero while
     *         unmatched, or inconsistent with {@code detail}
     */
    public SearchExplanation(
            T document,
            boolean matched,
            double score,
            ExplanationNode detail
    ) {
        ExplanationNode.validateScore(matched, score);
        this.document = Objects.requireNonNull(document, "document");
        this.detail = Objects.requireNonNull(detail, "detail");
        if (detail.matched() != matched || detail.score() != score) {
            throw new IllegalArgumentException(
                    "detail match and score must mirror the top-level explanation");
        }
        this.matched = matched;
        this.score = score;
    }

    /** @return the explained document */
    public T document() {
        return document;
    }

    /** @return whether the request matched the document */
    public boolean matched() {
        return matched;
    }

    /** @return the finite non-negative request score for the document */
    public double score() {
        return score;
    }

    /** @return the root explanation node */
    public ExplanationNode detail() {
        return detail;
    }
}
