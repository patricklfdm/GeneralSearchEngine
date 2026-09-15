package io.github.patricklfdm.generalsearch.replication;

import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;

/** Optional replicated engine contract. */
public interface ReplicatedSearchEngine<K, T> extends DurableSearchEngine<K, T> {
    /** Starts local recovery without admitting application work. */
    CompletableFuture<ReplicationStatus> start();

    /** Returns a point-in-time local replication status. */
    ReplicationStatus replicationStatus();

    /** Requests a new quorum-persisted configured-leader incarnation. */
    CompletableFuture<ReplicationStatus> activateConfiguredLeader();
}
