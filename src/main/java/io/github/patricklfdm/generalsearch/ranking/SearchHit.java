package io.github.patricklfdm.generalsearch.ranking;

import java.util.Objects;

/** One ranked document and its non-negative finite relevance score. */
public record SearchHit<T>(T document, double score) {
    public SearchHit {
        Objects.requireNonNull(document, "document");
        if (!Double.isFinite(score) || score < 0.0) {
            throw new IllegalArgumentException(
                    "score must be finite and non-negative");
        }
    }
}
