package io.github.patricklfdm.generalsearch.engine;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/**
 * Immutable application configuration handoff. Lists are copied; schema fields and
 * application functions retain their existing identity and immutability obligations.
 * Reconstruction creates an independent builder and preserves canonical fields.
 */
public record SearchEngineConfiguration<K, T>(
        SearchSchema<T, K> schema,
        List<IndexDefinition<T>> indexes,
        SnapshotEngineConfig config,
        PlannerConfig plannerConfig
) {
    public SearchEngineConfiguration {
        Objects.requireNonNull(schema, "schema");
        indexes = List.copyOf(indexes);
        Objects.requireNonNull(config, "config");
        Objects.requireNonNull(plannerConfig, "plannerConfig");
    }

    /** Reconstructs an independent builder; creates no engine, thread or files. */
    public SearchEngineBuilder<K, T> newBuilder() {
        return new SearchEngineBuilder<K, T>(schema).indexes(indexes)
                .config(config).plannerConfig(plannerConfig);
    }
}
