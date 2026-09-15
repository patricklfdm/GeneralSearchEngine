package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Entry point for the optional replication artifact. */
public final class ReplicatedSearchEngines {
    /** Public-admission protocol; recompile unpublished V5 consumers with inlined constants. */
    public static final String PROTOCOL = "gse-replication/1.1";

    private ReplicatedSearchEngines() {
    }

    public static <K, T> ReplicatedSearchEngineBuilder<K, T> builder(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationGroupConfig<K, T> configuration
    ) {
        return new ReplicatedSearchEngineBuilder<>(applicationBuilder, configuration);
    }
}
