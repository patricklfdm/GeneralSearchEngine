package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;

/** Explicit opt-in entry for protocol 1.3. It never changes a legacy engine's mode. */
public final class MembershipSearchEngines {
    public static final String PROTOCOL = "gse-replication/1.3";
    private MembershipSearchEngines() {}
    public static <K, T> MembershipSearchEngineBuilder<K, T> builder(
            SearchEngineBuilder<K, T> applicationBuilder, MembershipReplicaConfig<K, T> configuration) {
        return new MembershipSearchEngineBuilder<>(applicationBuilder, configuration);
    }
}
