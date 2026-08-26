package io.github.patricklfdm.generalsearch.search;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/** Immutable recursive ranked plan bound to exactly one search snapshot. */
record SearchPlan<T>(
        SearchSnapshot<T> snapshot,
        ScoringPlanNode<T> root,
        ImmutableBitmap candidates,
        Query<T> filter,
        int limit
) {
    SearchPlan {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(root, "root");
        Objects.requireNonNull(candidates, "candidates");
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
    }

    static <T> SearchPlan<T> empty(
            RankedSearchInput<T> input,
            ScoringPlanNode<T> root
    ) {
        return new SearchPlan<>(
                input.snapshot(),
                root,
                ImmutableBitmap.empty(),
                input.filter(),
                input.limit()
        );
    }
}
