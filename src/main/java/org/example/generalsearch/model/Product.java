package org.example.generalsearch.model;

import java.util.Objects;

public record Product(
        String id,
        String name,
        Category category,
        double price,
        boolean prime,
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
