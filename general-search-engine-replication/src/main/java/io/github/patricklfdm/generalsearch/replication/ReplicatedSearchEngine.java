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

    /** Reserved explicit peer recovery. The eventual result is a LogIndex. */
    default CompletableFuture<Long> catchUp(ReplicationNodeId peer) {
        throw new UnsupportedOperationException("Peer catch-up requires public-admission Step C");
    }

    /** Reserved configured-leader disk reconstruction from both surviving voters. */
    default CompletableFuture<ReplicationStatus> reconstructConfiguredLeader() {
        throw new UnsupportedOperationException("Leader reconstruction requires public-admission Step C");
    }

    /** Reserved consistent local and observed-peer diagnostics. */
    default ReplicationDiagnostics replicationDiagnostics() {
        throw new UnsupportedOperationException("Diagnostics require public-admission Step C");
    }
}
