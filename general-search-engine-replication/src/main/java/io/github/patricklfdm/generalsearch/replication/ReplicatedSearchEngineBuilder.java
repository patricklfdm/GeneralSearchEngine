package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Captures immutable application configuration into a stopped replicated handle. */
public final class ReplicatedSearchEngineBuilder<K, T> {
    private final SearchEngineBuilder<K, T> applicationBuilder;
    private final ReplicationGroupConfig<K, T> configuration;

    ReplicatedSearchEngineBuilder(
            SearchEngineBuilder<K, T> applicationBuilder,
            ReplicationGroupConfig<K, T> configuration
    ) {
        this.applicationBuilder = Objects.requireNonNull(
                applicationBuilder, "applicationBuilder");
        this.configuration = Objects.requireNonNull(configuration, "configuration");
    }

    public SearchEngineBuilder<K, T> applicationBuilder() {
        return applicationBuilder;
    }

    public ReplicationGroupConfig<K, T> configuration() {
        return configuration;
    }

    /**
     * Captures the application configuration and validates pure arguments. Opens no storage,
     * threads or sockets; {@link ReplicatedSearchEngine#start()} opens a sealed 1.1 authority.
     */
    public ReplicatedSearchEngine<K, T> build() {
        return new PublicReplicaEngine<>(applicationBuilder.configuration(), configuration);
    }
}
