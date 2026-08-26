package io.github.patricklfdm.generalsearch.search;

import java.util.Objects;

/**
 * Immutable ranked-retrieval query façade created through {@link SearchQueries}.
 *
 * @param <T> document type
 */
public final class SearchQuery<T> {
    private final SearchQueryNode<T> node;

    SearchQuery(SearchQueryNode<T> node) {
        this.node = Objects.requireNonNull(node, "node");
    }

    /**
     * Returns a new query whose eventual score is multiplied by the supplied value.
     *
     * @param boost finite, strictly positive multiplier
     * @return a new boosted query
     * @throws IllegalArgumentException when {@code boost} is not finite or is not
     *         strictly positive
     */
    public SearchQuery<T> boost(double boost) {
        if (!Double.isFinite(boost) || boost <= 0.0) {
            throw new IllegalArgumentException("boost must be finite and positive");
        }
        return new SearchQuery<>(new BoostSearchQueryNode<>(this, boost));
    }

    SearchQueryNode<T> node() {
        return node;
    }
}
