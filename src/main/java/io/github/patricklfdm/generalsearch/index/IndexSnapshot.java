package io.github.patricklfdm.generalsearch.index;

import java.util.Optional;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

/**
 * Immutable, thread-safe index state published as part of a search snapshot.
 *
 * @param <T> indexed document type
 */
public interface IndexSnapshot<T> {
    /** Returns the canonical field served by this index. */
    Field<T, ?> field();

    /**
     * Returns a safe candidate bitmap when this index supports the query, or empty when
     * it cannot help. A result must never omit a matching document.
     */
    Optional<CandidateResult> candidates(Query<T> query);

    /** Creates a single-use mutable builder rooted at this immutable snapshot. */
    IndexBuilder<T> toBuilder();
}
