package io.github.patricklfdm.generalsearch.query;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.schema.Field;

public record EqualQuery<T, V>(Field<T, V> field, V expectedValue) implements Query<T> {
    public EqualQuery {
        Objects.requireNonNull(field, "field");
    }

    @Override
    public boolean matches(T document) {
        return Objects.equals(field.valueOf(document), expectedValue);
    }
}
