package io.github.patricklfdm.generalsearch.query;

import java.util.List;
import java.util.Objects;

public record AndQuery<T>(List<Query<T>> queries) implements Query<T> {
    public AndQuery {
        queries = List.copyOf(Objects.requireNonNull(queries, "queries"));
    }

    @Override
    public boolean matches(T document) {
        return queries.stream().allMatch(query -> query.matches(document));
    }
}
