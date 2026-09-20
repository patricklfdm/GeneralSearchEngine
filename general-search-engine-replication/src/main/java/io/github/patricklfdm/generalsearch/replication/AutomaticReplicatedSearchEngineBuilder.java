package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Declaration-stage builder. Build rejects before configuration callbacks or IO. */
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

    /** Always rejects in Phase 1; no automatic runtime handle is constructed. */
    public AutomaticReplicatedSearchEngine<K, T> build() {
        throw AutomaticFoundation.unavailable();
    }
}
