package io.github.patricklfdm.generalsearch.query;

import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;

/** A snapshot-local estimate paired with a delayed candidate materializer. */
final class EstimatedAccessPath<T> {
    private final IndexSnapshot<T> index;
    private final Query<T> query;
    private final CandidateEstimate estimate;

    EstimatedAccessPath(
            IndexSnapshot<T> index,
            Query<T> query,
            CandidateEstimate estimate
    ) {
        this.index = Objects.requireNonNull(index, "index");
        this.query = Objects.requireNonNull(query, "query");
        this.estimate = Objects.requireNonNull(estimate, "estimate");
    }

    CandidateEstimate estimate() {
        return estimate;
    }

    Optional<CandidateResult> materialize() {
        return index.candidates(query);
    }
}
