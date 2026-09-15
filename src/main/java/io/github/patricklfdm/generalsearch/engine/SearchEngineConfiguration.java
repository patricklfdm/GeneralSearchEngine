package io.github.patricklfdm.generalsearch.engine;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/**
 * Immutable application configuration handoff. Lists are copied; schema fields and
 * application functions retain their existing identity and immutability obligations.
 * Builder reconstruction is reserved until public-admission Step B.
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

    /** Reserved configuration reconstruction; creates no engine, thread or files. */
    public SearchEngineBuilder<K, T> newBuilder() {
        throw new UnsupportedOperationException("Configuration handoff requires public-admission Step B");
    }
}
