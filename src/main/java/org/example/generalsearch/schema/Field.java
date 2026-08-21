package org.example.generalsearch.schema;

import java.util.Objects;
import java.util.function.Function;

/**
 * A type-safe description of a searchable document field.
 */
public record Field<T, V>(
        String name,
        Class<V> valueType,
        Function<T, V> extractor
) {
    public Field {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("field name must not be blank");
        }
        Objects.requireNonNull(valueType, "valueType");
        Objects.requireNonNull(extractor, "extractor");
    }

    public static <T, V> Field<T, V> of(
            String name,
            Class<V> valueType,
            Function<T, V> extractor
    ) {
        return new Field<>(name, valueType, extractor);
    }

    public V valueOf(T document) {
        return extractor.apply(Objects.requireNonNull(document, "document"));
    }
}
