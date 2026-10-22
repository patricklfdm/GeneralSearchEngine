package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import java.util.Objects;

/** Pure stopped-handle construction: no file, codec, thread or transport activation. */
public final class MembershipSearchEngineBuilder<K, T> {
    private final SearchEngineBuilder<K, T> applicationBuilder;
    private final MembershipReplicaConfig<K, T> configuration;
    MembershipSearchEngineBuilder(SearchEngineBuilder<K, T> applicationBuilder, MembershipReplicaConfig<K, T> configuration) {
        this.applicationBuilder = Objects.requireNonNull(applicationBuilder, "applicationBuilder");
        this.configuration = Objects.requireNonNull(configuration, "configuration");
    }
    public SearchEngineBuilder<K, T> applicationBuilder() { return applicationBuilder; }
    public MembershipReplicaConfig<K, T> configuration() { return configuration; }
    public MembershipSearchEngine<K, T> build() {
        return new DisabledMembershipEngine<>(applicationBuilder.configuration(), configuration);
    }
}
