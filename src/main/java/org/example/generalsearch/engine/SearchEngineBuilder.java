package org.example.generalsearch.engine;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Objects;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.schema.AnnotatedSchemaFactory;
import org.example.generalsearch.schema.AnnotatedSearchConfiguration;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.SearchSchema;

/**
 * Fluent construction entry point for generic snapshot search engines.
 *
 * <p>A builder created from a document type assembles its schema and automatically
 * registers fields referenced by startup indexes. A builder created from an existing
 * schema requires every index to use that schema's canonical field instance.</p>
 *
 * @param <K> business ID type
 * @param <T> document type
 */
public final class SearchEngineBuilder<K, T> {
    private final SearchSchema<T, K> fixedSchema;
    private final SearchSchema.Builder<T, K> schemaBuilder;
    private final List<IndexDefinition<T>> indexDefinitions = new ArrayList<>();
    private SnapshotEngineConfig config = SnapshotEngineConfig.DEFAULT;

    SearchEngineBuilder(SearchSchema<T, K> schema) {
        fixedSchema = Objects.requireNonNull(schema, "schema");
        schemaBuilder = null;
    }

    SearchEngineBuilder(Class<T> documentType, Field<T, K> idField) {
        fixedSchema = null;
        schemaBuilder = SearchSchema.builder(documentType, idField);
    }

    static <K, T> SearchEngineBuilder<K, T> annotated(
            Class<T> documentType,
            Class<K> idType
    ) {
        AnnotatedSearchConfiguration<T, K> generated =
                AnnotatedSchemaFactory.create(documentType, idType);
        return new SearchEngineBuilder<K, T>(generated.schema())
                .indexes(generated.indexDefinitions());
    }

    /** Adds a field when building the schema manually. */
    public <V> SearchEngineBuilder<K, T> field(Field<T, V> field) {
        if (schemaBuilder == null) {
            throw new IllegalStateException(
                    "fields cannot be added to an existing SearchSchema");
        }
        schemaBuilder.field(Objects.requireNonNull(field, "field"));
        return this;
    }

    /** Registers one startup index and its field in a manually built schema. */
    public SearchEngineBuilder<K, T> index(IndexDefinition<T> definition) {
        IndexDefinition<T> checked = Objects.requireNonNull(definition, "definition");
        registerIndexField(checked.field());
        indexDefinitions.add(checked);
        return this;
    }

    /** Registers startup indexes in iteration order. */
    public SearchEngineBuilder<K, T> indexes(
            Collection<? extends IndexDefinition<T>> definitions
    ) {
        Objects.requireNonNull(definitions, "definitions").forEach(this::index);
        return this;
    }

    public SearchEngineBuilder<K, T> config(SnapshotEngineConfig config) {
        this.config = Objects.requireNonNull(config, "config");
        return this;
    }

    /** Builds and starts a new engine instance owned by the caller. */
    public SearchEngine<K, T> build() {
        SearchSchema<T, K> schema = fixedSchema == null
                ? schemaBuilder.build()
                : fixedSchema;
        return new SnapshotSearchEngine<>(config, schema, List.copyOf(indexDefinitions));
    }

    private void registerIndexField(Field<T, ?> field) {
        Objects.requireNonNull(field, "index field");
        if (schemaBuilder != null) {
            schemaBuilder.field(field);
            return;
        }
        Field<T, ?> canonical = fixedSchema.requireField(field.name());
        if (canonical != field) {
            throw new IllegalArgumentException(
                    "indexes require canonical schema fields: " + field.name());
        }
    }
}
