package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/** Builds immutable snapshot-bound plans for normalized text requests. */
final class SearchPlanner<T> {
    private final CandidatePlanner<T> filterPlanner;

    SearchPlanner(CandidatePlanner<T> filterPlanner) {
        this.filterPlanner = Objects.requireNonNull(filterPlanner, "filterPlanner");
    }

    SearchPlan<T> plan(SearchSnapshot<T> snapshot, TextSearchInput<T> input) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(input, "input");
        if (input.frozenTerms().isEmpty()) {
            return SearchPlan.empty(snapshot, input);
        }

        TextIndexSnapshot<T> textIndex = requireTextIndex(snapshot, input.textField());
        int documentCount = textIndex.statistics().indexedDocumentCount();
        double averageDocumentLength = textIndex.averageDocumentLength();
        List<SearchPlan.ScoringTerm> scoringTerms = new ArrayList<>(
                input.frozenTerms().size());
        ImmutableBitmap firstCandidates = null;
        ImmutableBitmapBuilder candidateUnion = null;
        for (String term : input.frozenTerms()) {
            PostingList posting = textIndex.posting(term);
            int documentFrequency = posting.documentFrequency();
            if (documentFrequency == 0) {
                continue;
            }
            double inverseDocumentFrequency = Math.log1p(
                    (documentCount - documentFrequency + 0.5)
                            / (documentFrequency + 0.5)
            );
            scoringTerms.add(new SearchPlan.ScoringTerm(
                    posting,
                    inverseDocumentFrequency
            ));
            if (firstCandidates == null) {
                firstCandidates = posting.documents();
            } else {
                if (candidateUnion == null) {
                    candidateUnion = new ImmutableBitmapBuilder(firstCandidates);
                }
                candidateUnion.or(posting.documents());
            }
        }

        ImmutableBitmap candidates = firstCandidates == null
                ? ImmutableBitmap.empty()
                : candidateUnion == null ? firstCandidates : candidateUnion.build();

        if (input.filter() != null) {
            var filterCandidates = filterPlanner.plan(snapshot, input.filter());
            if (filterCandidates.isPresent()) {
                candidates = candidates.and(filterCandidates.get().bitmap());
            }
        }

        return new SearchPlan<>(
                snapshot,
                textIndex,
                scoringTerms,
                candidates,
                input.filter(),
                input.limit(),
                input.config(),
                averageDocumentLength
        );
    }

    private TextIndexSnapshot<T> requireTextIndex(
            SearchSnapshot<T> snapshot,
            TextField<T> canonicalTextField
    ) {
        for (IndexSnapshot<T> candidate : snapshot.indexes().indexes()) {
            if (candidate instanceof TextIndexSnapshot<?> text
                    && text.textField() == canonicalTextField) {
                @SuppressWarnings("unchecked")
                TextIndexSnapshot<T> typed = (TextIndexSnapshot<T>) text;
                return typed;
            }
        }
        throw new IllegalStateException(
                "ranked search requires the canonical text index: "
                        + canonicalTextField.name());
    }
}
