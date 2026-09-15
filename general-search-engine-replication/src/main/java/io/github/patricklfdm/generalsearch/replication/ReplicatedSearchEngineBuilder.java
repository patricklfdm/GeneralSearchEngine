package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Reserved public builder; complete group bootstrap/lifecycle admission is not enabled yet. */
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
     * Does not open storage or networking before complete group bootstrap/lifecycle admission.
     *
     * @throws UnsupportedOperationException always, until a later gated phase
     */
    public ReplicatedSearchEngine<K, T> build() {
        throw new UnsupportedOperationException(
                "Public replication construction requires the bootstrap/lifecycle gate");
    }
}
