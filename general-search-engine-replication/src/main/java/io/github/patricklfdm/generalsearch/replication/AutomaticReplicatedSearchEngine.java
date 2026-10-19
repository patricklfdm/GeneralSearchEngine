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
     * GSE supports this capability on a started automatic handle. Implementations
     * that retain this default fail without invoking the callback or opening resources.
     *
     * @param options explicit policy and optional history-bound minimum
     * @param reader callback receiving a read-only view, never the underlying engine
     * @param <R> callback result type
     * @return the captured result, or a failed future when unsupported or rejected
     */
    default <R> CompletableFuture<ReplicaReadResult<R>> read(
            ReplicaReadOptions options, Function<ReplicaReadView<K, T>, R> reader) {
        Objects.requireNonNull(options, "options");
        Objects.requireNonNull(reader, "reader");
        return CompletableFuture.failedFuture(new UnsupportedOperationException(
                "explicit replica reads are not enabled"));
    }
}
