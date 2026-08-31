package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.PriorityQueue;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;

/** Executes one immutable search plan without consulting another snapshot. */
final class SearchExecutor<T> {
    List<SearchHit<T>> execute(SearchPlan<T> plan) {
        return rankedCandidates(plan).stream()
                .map(candidate -> new SearchHit<>(
                        candidate.document(),
                        candidate.score()
                ))
                .toList();
    }

    List<ExecutedSearchHit<T>> executeWithDocumentIds(SearchPlan<T> plan) {
        return rankedCandidates(plan).stream()
                .map(candidate -> new ExecutedSearchHit<>(
                        candidate.docId(),
                        new SearchHit<>(candidate.document(), candidate.score())
                ))
                .toList();
    }

    private List<RankedCandidate<T>> rankedCandidates(SearchPlan<T> plan) {
        Objects.requireNonNull(plan, "plan");
        if (plan.candidates().isEmpty()) {
            return List.of();
        }

        int initialCapacity = Math.min(plan.limit(), plan.candidates().cardinality());
        PriorityQueue<RankedCandidate<T>> top = new PriorityQueue<>(
                Math.max(1, initialCapacity),
                worstFirst()
        );
        ImmutableBitmap scoringCandidates = plan.candidates();
        scoringCandidates.forEachSetBit(docId -> {
            T document = plan.snapshot().get(docId);
            if (document == null
                    || (plan.filter() != null && !plan.filter().matches(document))) {
                return;
            }
            ScoreMatch result = Objects.requireNonNull(plan.root()).evaluate(docId);
            if (!result.matched()) {
                return;
            }
            double score = result.score();
            RankedCandidate<T> candidate = new RankedCandidate<>(docId, document, score);
            if (top.size() < plan.limit()) {
                top.add(candidate);
            } else if (isBetter(candidate, Objects.requireNonNull(top.peek()))) {
                top.remove();
                top.add(candidate);
            }
        });

        List<RankedCandidate<T>> ranked = new ArrayList<>(top);
        ranked.sort(bestFirst());
        return ranked;
    }

    private boolean isBetter(
            RankedCandidate<T> candidate,
            RankedCandidate<T> currentWorst
    ) {
        int scoreComparison = Double.compare(candidate.score(), currentWorst.score());
        return scoreComparison > 0
                || (scoreComparison == 0 && candidate.docId() < currentWorst.docId());
    }

    private Comparator<RankedCandidate<T>> worstFirst() {
        return Comparator
                .comparingDouble(RankedCandidate<T>::score)
                .thenComparing(
                        Comparator.comparingInt(RankedCandidate<T>::docId).reversed());
    }

    private Comparator<RankedCandidate<T>> bestFirst() {
        return Comparator
                .comparingDouble(RankedCandidate<T>::score)
                .reversed()
                .thenComparingInt(RankedCandidate<T>::docId);
    }

    private record RankedCandidate<T>(int docId, T document, double score) {
    }
}

record ExecutedSearchHit<T>(int documentId, SearchHit<T> hit) {
    ExecutedSearchHit {
        if (documentId < 0) {
            throw new IllegalArgumentException("documentId must not be negative");
        }
        Objects.requireNonNull(hit, "hit");
    }
}
