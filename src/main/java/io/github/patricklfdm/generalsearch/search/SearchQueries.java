package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Factory methods for immutable V3 ranked-retrieval queries. */
public final class SearchQueries {
    private SearchQueries() {
    }

    /**
     * Retains a raw analyzed-text query for later planning.
     *
     * @param field canonical analyzed-text field
     * @param text raw query text
     * @param <T> document type
     * @return immutable text query
     * @throws NullPointerException when {@code field} or {@code text} is null
     */
    public static <T> SearchQuery<T> text(TextField<T> field, String text) {
        return leaf(SearchLeafKind.TEXT, field, text);
    }

    /**
     * Retains a raw exact-phrase query for later planning.
     *
     * @param field canonical analyzed-text field
     * @param text raw query text
     * @param <T> document type
     * @return immutable phrase query
     * @throws NullPointerException when {@code field} or {@code text} is null
     */
    public static <T> SearchQuery<T> phrase(TextField<T> field, String text) {
        return phrase(field, text, 0);
    }

    /**
     * Retains a raw ordered phrase query with an extra-gap budget for later planning.
     * Query position gaps remain minimum required gaps and term transposition is not
     * permitted.
     *
     * @param field canonical analyzed-text field
     * @param text raw query text
     * @param slop non-negative ordered extra-gap budget
     * @param <T> document type
     * @return immutable phrase query
     * @throws IllegalArgumentException when {@code slop} is negative
     * @throws NullPointerException when {@code field} or {@code text} is null
     */
    public static <T> SearchQuery<T> phrase(
            TextField<T> field,
            String text,
            int slop
    ) {
        if (slop < 0) {
            throw new IllegalArgumentException("slop must not be negative");
        }
        Objects.requireNonNull(field, "field");
        Objects.requireNonNull(text, "text");
        return new SearchQuery<>(new LeafSearchQueryNode<>(
                SearchLeafKind.PHRASE,
                field,
                text,
                slop
        ));
    }

    /**
     * Retains a raw single-analyzed-term fuzzy query for later planning.
     *
     * @param field canonical analyzed-text field
     * @param text raw query text
     * @param <T> document type
     * @return immutable fuzzy query
     * @throws NullPointerException when {@code field} or {@code text} is null
     */
    public static <T> SearchQuery<T> fuzzy(TextField<T> field, String text) {
        return leaf(SearchLeafKind.FUZZY, field, text);
    }

    /**
     * Starts an ordered boolean ranked-query builder.
     *
     * @param <T> document type
     * @return a new empty builder
     */
    public static <T> BoolBuilder<T> bool() {
        return new BoolBuilder<>();
    }

    private static <T> SearchQuery<T> leaf(
            SearchLeafKind kind,
            TextField<T> field,
            String text
    ) {
        Objects.requireNonNull(field, "field");
        Objects.requireNonNull(text, "text");
        return new SearchQuery<>(new LeafSearchQueryNode<>(kind, field, text, 0));
    }

    /**
     * Mutable reusable builder that creates immutable ordered boolean query snapshots.
     * Builder instances are not thread-safe.
     *
     * @param <T> document type
     */
    public static final class BoolBuilder<T> {
        private final List<SearchQuery<T>> must = new ArrayList<>();
        private final List<SearchQuery<T>> should = new ArrayList<>();

        private BoolBuilder() {
        }

        /**
         * Appends a required scoring clause.
         *
         * @param query required query
         * @return this builder
         * @throws NullPointerException when {@code query} is null
         */
        public BoolBuilder<T> must(SearchQuery<T> query) {
            must.add(Objects.requireNonNull(query, "query"));
            return this;
        }

        /**
         * Appends an optional scoring clause.
         *
         * @param query optional query
         * @return this builder
         * @throws NullPointerException when {@code query} is null
         */
        public BoolBuilder<T> should(SearchQuery<T> query) {
            should.add(Objects.requireNonNull(query, "query"));
            return this;
        }

        /**
         * Captures the current ordered clauses in an immutable query.
         *
         * @return immutable boolean query snapshot
         * @throws IllegalStateException when no clauses have been added
         */
        public SearchQuery<T> build() {
            if (must.isEmpty() && should.isEmpty()) {
                throw new IllegalStateException("a bool query requires at least one clause");
            }
            return new SearchQuery<>(new BoolSearchQueryNode<>(must, should));
        }
    }
}
