package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.schema.TextField;

/**
 * Immutable highlighted-search request wrapping one canonical ranked request.
 *
 * @param <T> document type
 */
public final class HighlightedSearchRequest<T> {
    private static final int DEFAULT_CONTEXT_CHARACTERS = 40;
    private static final int DEFAULT_MAX_FRAGMENTS_PER_FIELD = 3;

    private final SearchRequest<T> searchRequest;
    private final List<TextField<T>> fields;
    private final int contextCharacters;
    private final int maxFragmentsPerField;

    private HighlightedSearchRequest(
            SearchRequest<T> searchRequest,
            List<TextField<T>> fields,
            int contextCharacters,
            int maxFragmentsPerField
    ) {
        this.searchRequest = searchRequest;
        this.fields = fields;
        this.contextCharacters = contextCharacters;
        this.maxFragmentsPerField = maxFragmentsPerField;
    }

    /**
     * Starts a mutable request builder.
     *
     * @param searchRequest wrapped ranked-search request
     * @param <T> document type
     * @return a new builder
     * @throws NullPointerException when {@code searchRequest} is null
     */
    public static <T> Builder<T> builder(SearchRequest<T> searchRequest) {
        return new Builder<>(Objects.requireNonNull(
                searchRequest,
                "searchRequest"
        ));
    }

    /** @return the wrapped immutable ranked-search request */
    public SearchRequest<T> searchRequest() {
        return searchRequest;
    }

    /** @return immutable requested text fields in insertion order */
    public List<TextField<T>> fields() {
        return fields;
    }

    /** @return UTF-16 context units requested on each side of a span */
    public int contextCharacters() {
        return contextCharacters;
    }

    /** @return positive maximum number of fragments retained per field */
    public int maxFragmentsPerField() {
        return maxFragmentsPerField;
    }

    /** Mutable reusable builder; instances are not thread-safe. */
    public static final class Builder<T> {
        private final SearchRequest<T> searchRequest;
        private final List<TextField<T>> fields = new ArrayList<>();
        private final Set<String> fieldNames = new HashSet<>();
        private int contextCharacters = DEFAULT_CONTEXT_CHARACTERS;
        private int maxFragmentsPerField = DEFAULT_MAX_FRAGMENTS_PER_FIELD;

        private Builder(SearchRequest<T> searchRequest) {
            this.searchRequest = searchRequest;
        }

        /**
         * Appends one requested field in presentation order.
         *
         * @param field requested analyzed-text field
         * @return this builder
         * @throws NullPointerException when {@code field} is null
         * @throws IllegalArgumentException when its logical name is already present
         */
        public Builder<T> field(TextField<T> field) {
            TextField<T> checked = Objects.requireNonNull(field, "field");
            if (!fieldNames.add(checked.name())) {
                throw new IllegalArgumentException(
                        "duplicate highlighted field name: " + checked.name());
            }
            fields.add(checked);
            return this;
        }

        /**
         * Sets the UTF-16 context count on each side of a selected span.
         *
         * @param contextCharacters non-negative context count
         * @return this builder
         * @throws IllegalArgumentException when the value is negative
         */
        public Builder<T> contextCharacters(int contextCharacters) {
            if (contextCharacters < 0) {
                throw new IllegalArgumentException(
                        "contextCharacters must not be negative");
            }
            this.contextCharacters = contextCharacters;
            return this;
        }

        /**
         * Sets the maximum fragments retained for each requested field.
         *
         * @param maxFragmentsPerField positive fragment cap
         * @return this builder
         * @throws IllegalArgumentException when the value is not positive
         */
        public Builder<T> maxFragmentsPerField(int maxFragmentsPerField) {
            if (maxFragmentsPerField <= 0) {
                throw new IllegalArgumentException(
                        "maxFragmentsPerField must be positive");
            }
            this.maxFragmentsPerField = maxFragmentsPerField;
            return this;
        }

        /**
         * Captures an immutable request snapshot.
         *
         * @return immutable highlighted-search request
         * @throws IllegalStateException when no field has been supplied
         */
        public HighlightedSearchRequest<T> build() {
            if (fields.isEmpty()) {
                throw new IllegalStateException(
                        "at least one highlighted field is required");
            }
            return new HighlightedSearchRequest<>(
                    searchRequest,
                    List.copyOf(fields),
                    contextCharacters,
                    maxFragmentsPerField
            );
        }
    }
}
