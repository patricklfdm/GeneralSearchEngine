package io.github.patricklfdm.generalsearch.schema;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;

/**
 * Schema and startup-index definitions generated together from one annotated type.
 *
 * @param <T> document type
 * @param <K> business ID type
 * @param schema generated canonical schema
 * @param indexDefinitions generated startup indexes in discovery order
 */
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
