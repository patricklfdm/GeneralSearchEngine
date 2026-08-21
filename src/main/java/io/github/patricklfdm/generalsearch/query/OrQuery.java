package io.github.patricklfdm.generalsearch.query;

import java.util.List;
import java.util.Objects;

public record OrQuery<T>(List<Query<T>> queries) implements Query<T> {
    public OrQuery {
        queries = List.copyOf(Objects.requireNonNull(queries, "queries"));
    }

    @Override
    public boolean matches(T document) {
        return queries.stream().anyMatch(query -> query.matches(document));
    }
}
