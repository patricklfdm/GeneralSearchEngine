package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/** Immutable request facts bound to exactly one search snapshot. */
record SearchPlan<T>(
        SearchSnapshot<T> snapshot,
        TextIndexSnapshot<T> textIndex,
        List<ScoringTerm> scoringTerms,
        ImmutableBitmap candidates,
        Query<T> filter,
        int limit,
        Bm25Config config,
        double averageDocumentLength
) {
    SearchPlan {
        Objects.requireNonNull(snapshot, "snapshot");
        scoringTerms = List.copyOf(scoringTerms);
        Objects.requireNonNull(candidates, "candidates");
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        Objects.requireNonNull(config, "config");
    }

    static <T> SearchPlan<T> empty(
            SearchSnapshot<T> snapshot,
            TextSearchInput<T> input
    ) {
        return new SearchPlan<>(
                snapshot,
                null,
                List.of(),
                ImmutableBitmap.empty(),
                input.filter(),
                input.limit(),
                input.config(),
                0.0
        );
    }

    record ScoringTerm(PostingList posting, double inverseDocumentFrequency) {
        ScoringTerm {
            Objects.requireNonNull(posting, "posting");
        }
    }
}
