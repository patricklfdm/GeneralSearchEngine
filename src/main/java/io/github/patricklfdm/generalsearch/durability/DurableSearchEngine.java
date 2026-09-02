package io.github.patricklfdm.generalsearch.durability;

import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;

/**
 * Opt-in single-node durable capability over the existing search-engine contract.
 *
 * @param <K> business-key type
 * @param <T> document type
 */
public interface DurableSearchEngine<K, T> extends SearchEngine<K, T> {
    /** Returns the last durably forced and published logical-unit sequence. */
    long currentSequence();

    /**
     * Requests an asynchronous checkpoint.
     *
     * <p>The API is frozen in V4 Phase 2; production checkpoint execution is enabled
     * by the checkpoint phase.</p>
     */
    CompletableFuture<Void> checkpoint();

    /** Returns an immutable durability-specific operational snapshot. */
    DurabilityMetrics durabilityMetrics();
}
