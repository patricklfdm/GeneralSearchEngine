package io.github.patricklfdm.generalsearch.index;

import java.util.Optional;
import io.github.patricklfdm.generalsearch.query.Query;

/**
 * Optional index capability for estimating candidates without materializing a bitmap.
 *
 * <p>This interface is separate from {@link IndexSnapshot} so existing v1 custom index
 * implementations remain source- and binary-compatible. Implementations return empty
 * when they do not support a query.</p>
 *
 * @param <T> indexed document type
 */
public interface EstimatingIndexSnapshot<T> extends IndexSnapshot<T> {
    /** Returns immutable facts consistent with this exact index snapshot. */
    IndexStatistics statistics();

    /**
     * Estimates a supported candidate bitmap without constructing it.
     *
     * @param query query to inspect
     * @return candidate estimate, or empty when this index cannot serve the query
     */
    Optional<CandidateEstimate> estimateCandidates(Query<T> query);
}
