package org.example.generalsearch.query;

import java.util.Objects;
import org.example.generalsearch.schema.Field;

public record RangeQuery<T, V extends Comparable<? super V>>(
        Field<T, V> field,
        V minValue,
        V maxValue
) implements Query<T> {
    public RangeQuery {
        Objects.requireNonNull(field, "field");
        Objects.requireNonNull(minValue, "minValue");
        Objects.requireNonNull(maxValue, "maxValue");
    }

    @Override
    public boolean matches(T document) {
        V value = field.valueOf(document);
        return value != null
                && value.compareTo(minValue) >= 0
                && value.compareTo(maxValue) <= 0;
    }
}
