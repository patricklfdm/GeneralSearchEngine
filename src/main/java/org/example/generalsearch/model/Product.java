package org.example.generalsearch.model;

import java.util.Objects;
import org.example.generalsearch.schema.annotation.IndexType;
import org.example.generalsearch.schema.annotation.SearchId;
import org.example.generalsearch.schema.annotation.SearchIndex;

public record Product(
        @SearchId String id,
        @SearchIndex(IndexType.PREFIX) String name,
        @SearchIndex(IndexType.EQUALITY) Category category,
        @SearchIndex(IndexType.RANGE) double price,
        @SearchIndex(IndexType.EQUALITY) boolean prime,
        double rating
) {
    public Product {
        requireText(id, "id");
        requireText(name, "name");
        Objects.requireNonNull(category, "category");
        if (price < 0) {
            throw new IllegalArgumentException("price must not be negative");
        }
        if (rating < 0) {
            throw new IllegalArgumentException("rating must not be negative");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
