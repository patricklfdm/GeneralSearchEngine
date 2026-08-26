package io.github.patricklfdm.generalsearch.search;

import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;

/**
 * Immutable V3 ranked-search request.
 *
 * @param <T> document type
 */
public final class SearchRequest<T> {
    private static final int DEFAULT_LIMIT = 10;

    private final SearchQuery<T> query;
    private final Query<T> filter;
    private final int limit;
    private final Bm25Config bm25;

    private SearchRequest(
            SearchQuery<T> query,
            Query<T> filter,
            int limit,
            Bm25Config bm25
    ) {
        this.query = Objects.requireNonNull(query, "query");
        this.filter = filter;
        this.limit = limit;
        this.bm25 = Objects.requireNonNull(bm25, "bm25");
    }

    /**
     * Starts an empty reusable request builder.
     *
     * @param <T> document type
     * @return a new builder
     */
    public static <T> Builder<T> builder() {
        return new Builder<>();
    }

    /**
     * Creates a request with default limit, no filter, and default BM25 parameters.
     *
     * @param query required ranked query
     * @param <T> document type
     * @return immutable default request
     * @throws NullPointerException when {@code query} is null
     */
    public static <T> SearchRequest<T> of(SearchQuery<T> query) {
        return SearchRequest.<T>builder().query(query).build();
    }

    /** @return the required ranked query */
    public SearchQuery<T> query() {
        return query;
    }

    /** @return the optional structured eligibility filter */
    public Optional<Query<T>> filter() {
        return Optional.ofNullable(filter);
    }

    /** @return the positive maximum result count */
    public int limit() {
        return limit;
    }

    /** @return the BM25 parameters for this request */
    public Bm25Config bm25() {
        return bm25;
    }

    /**
     * Mutable reusable builder that creates immutable request snapshots.
     *
     * @param <T> document type
     */
    public static final class Builder<T> {
        private SearchQuery<T> query;
        private Query<T> filter;
        private int limit = DEFAULT_LIMIT;
        private Bm25Config bm25 = Bm25Config.DEFAULT;

        private Builder() {
        }

        /**
         * Sets the required ranked query.
         *
         * @param query ranked query
         * @return this builder
         * @throws NullPointerException when {@code query} is null
         */
        public Builder<T> query(SearchQuery<T> query) {
            this.query = Objects.requireNonNull(query, "query");
            return this;
        }

        /**
         * Sets the structured eligibility filter.
         *
         * @param filter non-null filter
         * @return this builder
         * @throws NullPointerException when {@code filter} is null
         */
        public Builder<T> filter(Query<T> filter) {
            this.filter = Objects.requireNonNull(filter, "filter");
            return this;
        }

        /**
         * Sets the maximum number of returned hits.
         *
         * @param limit positive result limit
         * @return this builder
         * @throws IllegalArgumentException when {@code limit} is not positive
         */
        public Builder<T> limit(int limit) {
            if (limit <= 0) {
                throw new IllegalArgumentException("limit must be positive");
            }
            this.limit = limit;
            return this;
        }

        /**
         * Sets the BM25 parameters.
         *
         * @param config non-null BM25 configuration
         * @return this builder
         * @throws NullPointerException when {@code config} is null
         */
        public Builder<T> bm25(Bm25Config config) {
            this.bm25 = Objects.requireNonNull(config, "config");
            return this;
        }

        /**
         * Captures the current values in an immutable request.
         *
         * @return immutable request
         * @throws IllegalStateException when no ranked query has been supplied
         */
        public SearchRequest<T> build() {
            if (query == null) {
                throw new IllegalStateException("query is required");
            }
            return new SearchRequest<>(query, filter, limit, bm25);
        }
    }
}
