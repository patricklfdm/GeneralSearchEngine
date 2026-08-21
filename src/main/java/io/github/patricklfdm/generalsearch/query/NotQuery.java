package io.github.patricklfdm.generalsearch.query;

import java.util.Objects;

public record NotQuery<T>(Query<T> query) implements Query<T> {
    public NotQuery {
        Objects.requireNonNull(query, "query");
    }

    @Override
    public boolean matches(T document) {
        return !query.matches(document);
    }
}
