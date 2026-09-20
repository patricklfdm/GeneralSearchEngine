package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Explicit automatic-mode entry, separate from the published configured-leader factory. */
public final class AutomaticReplicatedSearchEngines {
    public static final String PROTOCOL = "gse-replication/1.2";
    private AutomaticReplicatedSearchEngines() { }

    public static <K, T> AutomaticReplicatedSearchEngineBuilder<K, T> builder(
            SearchEngineBuilder<K, T> applicationBuilder,
            AutomaticReplicationGroupConfig<K, T> configuration) {
        return new AutomaticReplicatedSearchEngineBuilder<>(applicationBuilder, configuration);
    }
}
