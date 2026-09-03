package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
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

    /**
     * Creates one asynchronous checkpoint-only backup of this live durable engine.
     *
     * <p>Successful completion proves that the absent target was atomically and
     * durably published and passes codec-free production structural verification.
     * Independent implementations that do not adopt V4.1 reject the capability.</p>
     *
     * @param request target and explicit maximum bundle size
     * @return a non-null future for the exact durable backup result
     */
    default CompletableFuture<DurableBackupResult> backup(
            DurableBackupRequest request
    ) {
        Objects.requireNonNull(request, "request");
        throw new UnsupportedOperationException("V4.1 backup is not supported");
    }

    /** Returns an immutable durability-specific operational snapshot. */
    DurabilityMetrics durabilityMetrics();
}
