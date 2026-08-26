package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;

/** Builds immutable snapshot-bound recursive ranked plans. */
final class SearchPlanner<T> {
    private final CandidatePlanner<T> filterPlanner;

    SearchPlanner(CandidatePlanner<T> filterPlanner) {
        this.filterPlanner = Objects.requireNonNull(filterPlanner, "filterPlanner");
    }

    SearchPlan<T> plan(RankedSearchInput<T> input) {
        Objects.requireNonNull(input, "input");
        if (!input.hasNonEmptyText()) {
            return SearchPlan.empty(input);
        }

        ScoringPlanNode<T> root = compile(input.root(), input.config());
        ImmutableBitmap candidates = root.candidates();
        if (input.filter() != null) {
            var filterCandidates = filterPlanner.plan(
                    input.snapshot(),
                    input.filter()
            );
            if (filterCandidates.isPresent()) {
                candidates = candidates.and(filterCandidates.get().bitmap());
            }
        }

        return new SearchPlan<>(
                input.snapshot(),
                root,
                candidates,
                input.filter(),
                input.limit()
        );
    }

    private ScoringPlanNode<T> compile(
            NormalizedScoringNode<T> node,
            Bm25Config config
    ) {
        if (node instanceof NormalizedTextNode<?> untypedText) {
            @SuppressWarnings("unchecked")
            NormalizedTextNode<T> text = (NormalizedTextNode<T>) untypedText;
            return compileText(text, config);
        }
        if (node instanceof NormalizedBoolNode<?> untypedBool) {
            @SuppressWarnings("unchecked")
            NormalizedBoolNode<T> bool = (NormalizedBoolNode<T>) untypedBool;
            List<ScoringPlanNode<T>> must = compileChildren(bool.must(), config);
            List<ScoringPlanNode<T>> should = compileChildren(bool.should(), config);
            return new BoolPlan<>(must, should, boolCandidates(must, should));
        }
        @SuppressWarnings("unchecked")
        NormalizedBoostNode<T> boost = (NormalizedBoostNode<T>) node;
        return new BoostPlan<>(compile(boost.child(), config), boost.multiplier());
    }

    private List<ScoringPlanNode<T>> compileChildren(
            List<NormalizedScoringNode<T>> children,
            Bm25Config config
    ) {
        List<ScoringPlanNode<T>> plans = new ArrayList<>(children.size());
        for (NormalizedScoringNode<T> child : children) {
            plans.add(compile(child, config));
        }
        return List.copyOf(plans);
    }

    private TextPlan<T> compileText(
            NormalizedTextNode<T> text,
            Bm25Config config
    ) {
        if (text.frozenTerms().isEmpty()) {
            return new TextPlan<>(
                    null,
                    List.of(),
                    ImmutableBitmap.empty(),
                    config,
                    0.0
            );
        }

        TextIndexSnapshot<T> textIndex = Objects.requireNonNull(text.textIndex());
        int documentCount = textIndex.statistics().indexedDocumentCount();
        double averageDocumentLength = textIndex.averageDocumentLength();
        List<ScoringTerm> scoringTerms = new ArrayList<>(text.frozenTerms().size());
        ImmutableBitmap firstCandidates = null;
        ImmutableBitmapBuilder candidateUnion = null;
        for (String term : text.frozenTerms()) {
            PostingList posting = textIndex.posting(term);
            int documentFrequency = posting.documentFrequency();
            if (documentFrequency == 0) {
                continue;
            }
            double inverseDocumentFrequency = Math.log1p(
                    (documentCount - documentFrequency + 0.5)
                            / (documentFrequency + 0.5)
            );
            scoringTerms.add(new ScoringTerm(
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

        return new TextPlan<>(
                textIndex,
                scoringTerms,
                candidates,
                config,
                averageDocumentLength
        );
    }

    private ImmutableBitmap boolCandidates(
            List<ScoringPlanNode<T>> must,
            List<ScoringPlanNode<T>> should
    ) {
        if (!must.isEmpty()) {
            List<ScoringPlanNode<T>> physical = new ArrayList<>(must);
            physical.sort(Comparator.comparingInt(
                    child -> child.candidates().cardinality()));
            ImmutableBitmap candidates = physical.getFirst().candidates();
            for (int index = 1; index < physical.size(); index++) {
                candidates = candidates.and(physical.get(index).candidates());
                if (candidates.isEmpty()) {
                    break;
                }
            }
            return candidates;
        }

        ImmutableBitmap first = null;
        ImmutableBitmapBuilder union = null;
        for (ScoringPlanNode<T> child : should) {
            if (first == null) {
                first = child.candidates();
            } else {
                if (union == null) {
                    union = new ImmutableBitmapBuilder(first);
                }
                union.or(child.candidates());
            }
        }
        if (first == null) {
            return ImmutableBitmap.empty();
        }
        return union == null ? first : union.build();
    }
}
