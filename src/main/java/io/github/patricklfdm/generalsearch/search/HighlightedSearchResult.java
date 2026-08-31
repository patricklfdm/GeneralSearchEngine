package io.github.patricklfdm.generalsearch.search;

import java.util.List;

/** Immutable ordered highlighted-search result. */
public final class HighlightedSearchResult<T> {
    private final List<HighlightedSearchHit<T>> hits;

    /**
     * Creates a result by defensively copying its hit order.
     *
     * @param hits non-null ordered hits containing no null element
     * @throws NullPointerException when the list or one of its elements is null
     */
    public HighlightedSearchResult(List<HighlightedSearchHit<T>> hits) {
        this.hits = List.copyOf(hits);
    }

    /** @return immutable hits in canonical ranked order */
    public List<HighlightedSearchHit<T>> hits() {
        return hits;
    }
}
