package io.github.patricklfdm.generalsearch.engine;

import java.util.Collection;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurabilityMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

final class DurableSnapshotSearchEngine<K, T> extends SnapshotSearchEngine<K, T>
        implements DurableSearchEngine<K, T> {
    private final DurableCommitCoordinator<K, T> durability;

    DurableSnapshotSearchEngine(
            SnapshotEngineConfig config,
            PlannerConfig plannerConfig,
            SearchSchema<T, K> schema,
            Collection<? extends IndexDefinition<T>> indexDefinitions,
            DurableCommitCoordinator<K, T> durability
    ) {
        super(config, plannerConfig, schema, indexDefinitions, durability);
        this.durability = durability;
    }

    @Override
    public long currentSequence() {
        return durability.currentSequence();
    }

    @Override
    public CompletableFuture<Void> checkpoint() {
        return checkpointDurably();
    }

    @Override
    public DurabilityMetrics durabilityMetrics() {
        return durability.metrics();
    }
}
