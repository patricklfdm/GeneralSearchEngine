package io.github.patricklfdm.generalsearch.replication;

import java.util.concurrent.CompletableFuture;
import java.util.Objects;
import java.util.function.Function;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;

/** Automatic leadership with strong default reads and an optional explicit read capability. */
public interface AutomaticReplicatedSearchEngine<K, T> extends DurableSearchEngine<K, T> {
    CompletableFuture<AutomaticReplicationStatus> start();
    AutomaticReplicationStatus leadershipStatus();

    /**
     * Reads one callback-scoped committed view using an explicit consistency policy.
     * This additive capability is disabled in the V5.2 foundation. Implementations
     * that do not support it fail without invoking the callback or opening resources.
     *
     * @param options explicit policy and optional history-bound minimum
     * @param reader callback receiving a read-only view, never the underlying engine
     * @param <R> callback result type
     * @return a failed future until this capability is supported
     */
    default <R> CompletableFuture<ReplicaReadResult<R>> read(
            ReplicaReadOptions options, Function<ReplicaReadView<K, T>, R> reader) {
        Objects.requireNonNull(options, "options");
        Objects.requireNonNull(reader, "reader");
        return CompletableFuture.failedFuture(new UnsupportedOperationException(
                "explicit replica reads are not enabled"));
    }
}
