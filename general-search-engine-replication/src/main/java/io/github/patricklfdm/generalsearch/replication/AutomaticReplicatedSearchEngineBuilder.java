package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Pure configuration builder. Only start acquires local storage and transport. */
public final class AutomaticReplicatedSearchEngineBuilder<K, T> {
    private final SearchEngineBuilder<K, T> applicationBuilder;
    private final AutomaticReplicationGroupConfig<K, T> configuration;

    AutomaticReplicatedSearchEngineBuilder(SearchEngineBuilder<K, T> applicationBuilder,
            AutomaticReplicationGroupConfig<K, T> configuration) {
        this.applicationBuilder = Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        this.configuration = Objects.requireNonNull(configuration, "configuration");
    }

    public SearchEngineBuilder<K, T> applicationBuilder() { return applicationBuilder; }
    public AutomaticReplicationGroupConfig<K, T> configuration() { return configuration; }

    /** Returns a stopped handle without codec calls, IO or running threads. */
    public AutomaticReplicatedSearchEngine<K, T> build() {
        return new PublicAutomaticEngine<>(applicationBuilder.configuration(), configuration);
    }
}
