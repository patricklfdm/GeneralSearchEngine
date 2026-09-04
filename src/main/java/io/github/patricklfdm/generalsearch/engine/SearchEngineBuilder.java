package io.github.patricklfdm.generalsearch.engine;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationResult;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.schema.AnnotatedSchemaFactory;
import io.github.patricklfdm.generalsearch.schema.AnnotatedSearchConfiguration;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;

/**
 * Fluent construction entry point for generic snapshot search engines.
 *
 * <p>A builder created from a document type assembles its schema and automatically
 * registers fields referenced by startup indexes. A builder created from an existing
 * schema preserves its canonical instances and can safely extend a copy with additional
 * fields or analyzed-text configuration.</p>
 *
 * @param <K> business ID type
 * @param <T> document type
 */
public final class SearchEngineBuilder<K, T> {
    private final SearchSchema<T, K> baseSchema;
    private final SearchSchema.Builder<T, K> schemaBuilder;
    private final List<IndexDefinition<T>> indexDefinitions = new ArrayList<>();
    private SnapshotEngineConfig config = SnapshotEngineConfig.DEFAULT;
    private PlannerConfig plannerConfig = PlannerConfig.DEFAULT;
    private boolean schemaExtended;

    SearchEngineBuilder(SearchSchema<T, K> schema) {
        baseSchema = Objects.requireNonNull(schema, "schema");
        schemaBuilder = copySchema(baseSchema);
    }

    SearchEngineBuilder(Class<T> documentType, Field<T, K> idField) {
        baseSchema = null;
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

    /** Adds a field to the engine schema without mutating a supplied existing schema. */
    public <V> SearchEngineBuilder<K, T> field(Field<T, V> field) {
        registerIndexField(Objects.requireNonNull(field, "field"));
        return this;
    }

    /**
     * Registers a canonical analyzed-text configuration in the engine schema.
     * Existing schemas are copied and extended; the supplied schema remains immutable.
     */
    public SearchEngineBuilder<K, T> textField(TextField<T> textField) {
        registerTextIndexField(Objects.requireNonNull(textField, "textField"));
        return this;
    }

    /**
     * Adds a startup text index for a named String field already present in the schema.
     * The canonical {@link TextField} can be retrieved from {@code engine.schema()}
     * after building and reused by boolean text and ranked queries.
     *
     * @param fieldName canonical schema field name
     * @param analyzer deterministic analysis semantics for documents and queries
     * @return this builder
     */
    public SearchEngineBuilder<K, T> textIndex(
            String fieldName,
            Analyzer analyzer
    ) {
        Objects.requireNonNull(fieldName, "fieldName");
        Objects.requireNonNull(analyzer, "analyzer");
        Field<T, String> field = schemaBuilder.build()
                .requireField(fieldName, String.class);
        return index(IndexDefinition.text(TextField.of(field, analyzer)));
    }

    /** Registers one startup index and its field in a manually built schema. */
    public SearchEngineBuilder<K, T> index(IndexDefinition<T> definition) {
        IndexDefinition<T> checked = Objects.requireNonNull(definition, "definition");
        if (checked instanceof TextIndexDefinition<T> text) {
            registerTextIndexField(text.textField());
        } else {
            registerIndexField(checked.field());
        }
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

    /** Configures snapshot-local query access-path selection. */
    public SearchEngineBuilder<K, T> plannerConfig(PlannerConfig plannerConfig) {
        this.plannerConfig = Objects.requireNonNull(plannerConfig, "plannerConfig");
        return this;
    }

    /** Builds and starts a new engine instance owned by the caller. */
    public SearchEngine<K, T> build() {
        SearchSchema<T, K> schema = buildSchema();
        return new SnapshotSearchEngine<>(
                config,
                plannerConfig,
                schema,
                List.copyOf(indexDefinitions)
        );
    }

    /**
     * Builds a new opt-in durable engine over one exclusively owned local directory.
     *
     * @param storageConfig persisted identities, codec, directory and safety bounds
     * @return a started durable engine owned by the caller
     */
    public DurableSearchEngine<K, T> buildDurable(
            DurableStorageConfig<K, T> storageConfig
    ) {
        SearchSchema<T, K> schema = buildSchema();
        DurableCommitCoordinator<K, T> durability =
                DurableCommitCoordinator.open(
                        Objects.requireNonNull(storageConfig, "storageConfig"),
                        config,
                        schema,
                        List.copyOf(indexDefinitions));
        try {
            return new DurableSnapshotSearchEngine<>(
                    config,
                    plannerConfig,
                    schema,
                    List.copyOf(indexDefinitions),
                    durability);
        } catch (RuntimeException | Error failure) {
            try {
                durability.close();
            } catch (RuntimeException closeFailure) {
                failure.addSuppressed(closeFailure);
            }
            throw failure;
        }
    }

    /**
     * Synchronously performs a read-only typed semantic pass over one structurally
     * valid supported V4 backup. Successful status proves bounded canonical decode and
     * reconstruction of the builder's durable index configuration.
     *
     * @param backupDirectory immutable completed backup bundle
     * @param expectedConfig expected identities, codec and decode bounds
     * @return immutable semantic report
     */
    public DurableSemanticVerificationReport verifyDurableBackup(
            Path backupDirectory,
            DurableVerificationConfig<K, T> expectedConfig
    ) {
        SearchSchema<T, K> schema = buildSchema();
        return DurableSemanticOperations.inspect(
                Objects.requireNonNull(backupDirectory, "backupDirectory"),
                Objects.requireNonNull(expectedConfig, "expectedConfig"),
                schema, List.copyOf(indexDefinitions)).report();
    }

    /**
     * Synchronously restores a valid supported V4 backup into an absent local target
     * as a new same-format durable history. Successful return proves durable publication,
     * codec-free structural validation and typed state reconstruction.
     *
     * @param backupDirectory immutable completed backup bundle
     * @param targetConfig exact persisted target identities and safety bounds
     * @return completed restore authority and external provenance
     */
    public DurableRestoreResult restoreDurableBackup(
            Path backupDirectory,
            DurableStorageConfig<K, T> targetConfig
    ) {
        SearchSchema<T, K> schema = buildSchema();
        return DurableRestoreWriter.restore(
                Objects.requireNonNull(backupDirectory, "backupDirectory"),
                Objects.requireNonNull(targetConfig, "targetConfig"),
                schema, List.copyOf(indexDefinitions));
    }

    /**
     * Plans an offline, source-preserving durable migration without creating any
     * target, staging, marker, cache or spill file. Supported V4.2 edges are an exact
     * {@code (1,0)} to {@code (1,1)} migration and a declared non-no-op
     * {@code (1,1)} to {@code (1,1)} migration. The versioned transform may change
     * codec, schema, business-key and document bytes one-to-one; target indexes are
     * rebuilt from the transformed documents. The transform is executed serially and
     * its complete projection is bound into the returned immutable plan.
     *
     * @param sourceBuilder complete typed descriptor for the closed source
     * @param request source, absent target, versioned transform and hard bounds
     * @return immutable authority that apply must fully revalidate
     */
    public <SK, ST> DurableMigrationPlan planDurableMigration(
            SearchEngineBuilder<SK, ST> sourceBuilder,
            DurableMigrationRequest<SK, ST, K, T> request
    ) {
        Objects.requireNonNull(sourceBuilder, "sourceBuilder");
        return DurableMigrationOperations.plan(
                sourceBuilder.buildSchema(),
                List.copyOf(sourceBuilder.indexDefinitions),
                buildSchema(), List.copyOf(indexDefinitions),
                Objects.requireNonNull(request, "request"));
    }

    /**
     * Applies an exact offline migration plan into an absent target directory.
     * Source authority is held exclusively and preserved byte-for-byte; the caller
     * transform is rerun and must reproduce the planned projection. Successful
     * return proves atomic target publication, parent force, structural and typed
     * verification, normal target open/close, source recheck and marker cleanup. It
     * does not perform application cutover or dispose of the source.
     *
     * @param sourceBuilder complete typed descriptor for the closed source
     * @param request exact request used while planning
     * @param plan immutable plan to revalidate before publication
     * @return completed target and external source/projection provenance
     */
    public <SK, ST> DurableMigrationResult applyDurableMigration(
            SearchEngineBuilder<SK, ST> sourceBuilder,
            DurableMigrationRequest<SK, ST, K, T> request,
            DurableMigrationPlan plan
    ) {
        Objects.requireNonNull(sourceBuilder, "sourceBuilder");
        return DurableMigrationOperations.apply(
                sourceBuilder.buildSchema(),
                List.copyOf(sourceBuilder.indexDefinitions),
                buildSchema(), List.copyOf(indexDefinitions), config,
                Objects.requireNonNull(request, "request"),
                Objects.requireNonNull(plan, "plan"));
    }

    private SearchSchema<T, K> buildSchema() {
        return baseSchema != null && !schemaExtended
                ? baseSchema
                : schemaBuilder.build();
    }

    private void registerIndexField(Field<T, ?> field) {
        Objects.requireNonNull(field, "index field");
        schemaBuilder.field(field);
        if (baseSchema == null || baseSchema.field(field.name()).orElse(null) != field) {
            schemaExtended = true;
        }
    }

    private void registerTextIndexField(TextField<T> textField) {
        schemaBuilder.textField(Objects.requireNonNull(textField, "textField"));
        if (baseSchema == null
                || baseSchema.textField(textField.name()).orElse(null) != textField) {
            schemaExtended = true;
        }
    }

    private static <K, T> SearchSchema.Builder<T, K> copySchema(
            SearchSchema<T, K> schema
    ) {
        SearchSchema.Builder<T, K> copy = SearchSchema.builder(
                schema.documentType(),
                schema.idField()
        );
        for (Field<T, ?> field : schema.fields().values()) {
            copy.field(field);
        }
        for (TextField<T> textField : schema.textFields().values()) {
            copy.textField(textField);
        }
        return copy;
    }
}
