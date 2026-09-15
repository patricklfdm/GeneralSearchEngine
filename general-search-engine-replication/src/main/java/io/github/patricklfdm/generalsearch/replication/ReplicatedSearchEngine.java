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

    /** Explicit peer recovery on an activated configured leader; the result is a verified LogIndex. */
    default CompletableFuture<Long> catchUp(ReplicationNodeId peer) {
        throw new UnsupportedOperationException("Peer catch-up requires public-admission Step C");
    }

    /** Explicit configured-leader disk reconstruction from both surviving voters. */
    default CompletableFuture<ReplicationStatus> reconstructConfiguredLeader() {
        throw new UnsupportedOperationException("Leader reconstruction requires public-admission Step C");
    }

    /** Consistent local and observed-peer diagnostics without synchronous network waits. */
    default ReplicationDiagnostics replicationDiagnostics() {
        throw new UnsupportedOperationException("Diagnostics require public-admission Step C");
    }
}
