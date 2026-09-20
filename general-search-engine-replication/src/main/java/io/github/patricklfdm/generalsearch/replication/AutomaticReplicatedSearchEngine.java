package io.github.patricklfdm.generalsearch.replication;

import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;

/** Future opt-in automatic runtime surface; no implementation is enabled in Phase 1. */
public interface AutomaticReplicatedSearchEngine<K, T> extends DurableSearchEngine<K, T> {
    CompletableFuture<AutomaticReplicationStatus> start();
    AutomaticReplicationStatus leadershipStatus();
}
