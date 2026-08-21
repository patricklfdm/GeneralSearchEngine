package io.github.patricklfdm.generalsearch.query;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.schema.Field;

public record PrefixQuery<T>(Field<T, String> field, String prefix) implements Query<T> {
    public PrefixQuery {
        Objects.requireNonNull(field, "field");
        Objects.requireNonNull(prefix, "prefix");
    }

    @Override
    public boolean matches(T document) {
        String value = field.valueOf(document);
        return value != null && value.startsWith(prefix);
    }
}
