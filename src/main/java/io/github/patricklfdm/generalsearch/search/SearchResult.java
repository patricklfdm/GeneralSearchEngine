package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;

/**
 * Immutable wrapper for ordered V3 ranked-search hits.
 *
 * @param <T> document type
 */
public final class SearchResult<T> {
    private final List<SearchHit<T>> hits;

    /**
     * Creates a result by copying the supplied hit order.
     *
     * @param hits non-null ordered hits containing no null element
     * @throws NullPointerException when the list or one of its elements is null
     */
    public SearchResult(List<SearchHit<T>> hits) {
        this.hits = List.copyOf(hits);
    }

    /** @return the immutable ordered hit list */
    public List<SearchHit<T>> hits() {
        return hits;
    }
}
