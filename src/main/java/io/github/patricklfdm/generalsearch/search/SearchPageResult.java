package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.OptionalLong;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;

/**
 * Immutable ordered page of ranked hits with an optional continuation cursor and
 * optional exact total-hit value.
 *
 * @param <T> document type
 */
public final class SearchPageResult<T> {
    private final List<SearchHit<T>> hits;
    private final SearchAfterCursor nextCursor;
    private final OptionalLong totalHits;

    private SearchPageResult(
            List<SearchHit<T>> hits,
            SearchAfterCursor nextCursor,
            OptionalLong totalHits
    ) {
        this.hits = List.copyOf(hits);
        this.nextCursor = nextCursor;
        this.totalHits = Objects.requireNonNull(totalHits, "totalHits");
    }

    /**
     * Creates a final page without a total-hit value.
     *
     * @param hits ordered non-null hits containing no null element
     * @param <T> document type
     * @return immutable final page
     */
    public static <T> SearchPageResult<T> withoutTotalHits(
            List<SearchHit<T>> hits
    ) {
        return new SearchPageResult<>(hits, null, OptionalLong.empty());
    }

    /**
     * Creates a continuable page without a total-hit value.
     *
     * @param hits ordered non-null hits containing no null element
     * @param nextCursor non-null opaque continuation cursor
     * @param <T> document type
     * @return immutable continuable page
     */
    public static <T> SearchPageResult<T> withoutTotalHits(
            List<SearchHit<T>> hits,
            SearchAfterCursor nextCursor
    ) {
        return new SearchPageResult<>(
                hits,
                Objects.requireNonNull(nextCursor, "nextCursor"),
                OptionalLong.empty()
        );
    }

    /**
     * Creates a final page with the exact complete match count.
     *
     * @param hits ordered non-null hits containing no null element
     * @param exactTotalHits non-negative complete match count
     * @param <T> document type
     * @return immutable final page with exact total hits
     * @throws IllegalArgumentException when {@code exactTotalHits} is negative
     */
    public static <T> SearchPageResult<T> withExactTotalHits(
            List<SearchHit<T>> hits,
            long exactTotalHits
    ) {
        return new SearchPageResult<>(
                hits,
                null,
                exactTotalHits(exactTotalHits)
        );
    }

    /**
     * Creates a continuable page with the exact complete match count.
     *
     * @param hits ordered non-null hits containing no null element
     * @param nextCursor non-null opaque continuation cursor
     * @param exactTotalHits non-negative complete match count
     * @param <T> document type
     * @return immutable continuable page with exact total hits
     * @throws IllegalArgumentException when {@code exactTotalHits} is negative
     */
    public static <T> SearchPageResult<T> withExactTotalHits(
            List<SearchHit<T>> hits,
            SearchAfterCursor nextCursor,
            long exactTotalHits
    ) {
        return new SearchPageResult<>(
                hits,
                Objects.requireNonNull(nextCursor, "nextCursor"),
                exactTotalHits(exactTotalHits)
        );
    }

    /** @return immutable ranked hits in canonical order */
    public List<SearchHit<T>> hits() {
        return hits;
    }

    /** @return an opaque cursor only when another page is available */
    public Optional<SearchAfterCursor> nextCursor() {
        return Optional.ofNullable(nextCursor);
    }

    /** @return exact total hits when requested, otherwise an empty optional */
    public OptionalLong totalHits() {
        return totalHits;
    }

    private static OptionalLong exactTotalHits(long exactTotalHits) {
        if (exactTotalHits < 0L) {
            throw new IllegalArgumentException(
                    "exactTotalHits must not be negative");
        }
        return OptionalLong.of(exactTotalHits);
    }
}
