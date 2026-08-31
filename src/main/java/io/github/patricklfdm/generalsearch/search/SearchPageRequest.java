package io.github.patricklfdm.generalsearch.search;

import java.util.Objects;
import java.util.Optional;

/**
 * Immutable opt-in page wrapper around one exact ranked {@link SearchRequest} object.
 *
 * <p>The wrapped request's positive limit is the page size. Continuation requires
 * reusing that same request object with a cursor returned by the same engine.</p>
 *
 * @param <T> document type
 */
public final class SearchPageRequest<T> {
    private final SearchRequest<T> searchRequest;
    private final SearchAfterCursor after;
    private final TotalHitsMode totalHitsMode;

    private SearchPageRequest(
            SearchRequest<T> searchRequest,
            SearchAfterCursor after,
            TotalHitsMode totalHitsMode
    ) {
        this.searchRequest = Objects.requireNonNull(searchRequest, "searchRequest");
        this.after = after;
        this.totalHitsMode = Objects.requireNonNull(totalHitsMode, "totalHitsMode");
    }

    /**
     * Starts a reusable builder bound to the supplied immutable request object.
     *
     * @param searchRequest exact request object used for the page chain
     * @param <T> document type
     * @return a new builder with no cursor and disabled total hits
     * @throws NullPointerException when {@code searchRequest} is null
     */
    public static <T> Builder<T> builder(SearchRequest<T> searchRequest) {
        return new Builder<>(Objects.requireNonNull(searchRequest, "searchRequest"));
    }

    /** @return the exact immutable ranked request wrapped by this page request */
    public SearchRequest<T> searchRequest() {
        return searchRequest;
    }

    /** @return the optional opaque cursor supplied for continuation */
    public Optional<SearchAfterCursor> after() {
        return Optional.ofNullable(after);
    }

    /** @return the explicit total-hit computation mode */
    public TotalHitsMode totalHitsMode() {
        return totalHitsMode;
    }

    /**
     * Mutable reusable builder that creates immutable page-request snapshots. Builder
     * instances are not thread-safe.
     *
     * @param <T> document type
     */
    public static final class Builder<T> {
        private final SearchRequest<T> searchRequest;
        private SearchAfterCursor after;
        private TotalHitsMode totalHitsMode = TotalHitsMode.DISABLED;

        private Builder(SearchRequest<T> searchRequest) {
            this.searchRequest = searchRequest;
        }

        /**
         * Sets the opaque cursor used to continue this exact request.
         *
         * @param cursor non-null cursor returned by a paged-search implementation
         * @return this builder
         * @throws NullPointerException when {@code cursor} is null
         */
        public Builder<T> after(SearchAfterCursor cursor) {
            this.after = Objects.requireNonNull(cursor, "cursor");
            return this;
        }

        /**
         * Sets the total-hit computation mode.
         *
         * @param mode non-null total-hit mode
         * @return this builder
         * @throws NullPointerException when {@code mode} is null
         */
        public Builder<T> totalHits(TotalHitsMode mode) {
            this.totalHitsMode = Objects.requireNonNull(mode, "mode");
            return this;
        }

        /** @return an immutable snapshot of the current builder values */
        public SearchPageRequest<T> build() {
            return new SearchPageRequest<>(searchRequest, after, totalHitsMode);
        }
    }
}
