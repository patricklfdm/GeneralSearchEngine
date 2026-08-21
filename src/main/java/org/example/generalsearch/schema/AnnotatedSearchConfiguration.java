package org.example.generalsearch.schema;

import java.util.List;
import java.util.Objects;
import org.example.generalsearch.index.IndexDefinition;

public record AnnotatedSearchConfiguration<T, K>(
        SearchSchema<T, K> schema,
        List<IndexDefinition<T>> indexDefinitions
) {
    public AnnotatedSearchConfiguration {
        Objects.requireNonNull(schema, "schema");
        indexDefinitions = List.copyOf(
                Objects.requireNonNull(indexDefinitions, "indexDefinitions"));
    }
}
