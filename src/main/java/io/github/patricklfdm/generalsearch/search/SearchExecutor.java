package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.PriorityQueue;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;

/** Executes one immutable search plan without consulting another snapshot. */
final class SearchExecutor<T> {
    List<SearchHit<T>> execute(SearchPlan<T> plan) {
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
            double score = score(plan, docId);
            if (score <= 0.0) {
                return;
            }
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
        return ranked.stream()
                .map(candidate -> new SearchHit<>(candidate.document(), candidate.score()))
                .toList();
    }

    private double score(SearchPlan<T> plan, int docId) {
        int documentLength = Objects.requireNonNull(plan.textIndex())
                .documentLength(docId);
        double averageLength = plan.averageDocumentLength();
        if (averageLength == 0.0 || documentLength == 0) {
            return 0.0;
        }
        Bm25Config config = plan.config();
        double normalization = config.k1() * (
                1.0 - config.b()
                        + config.b() * documentLength / averageLength
        );
        double score = 0.0;
        for (SearchPlan.ScoringTerm term : plan.scoringTerms()) {
            int termFrequency = term.posting().termFrequency(docId);
            if (termFrequency == 0) {
                continue;
            }
            score += term.inverseDocumentFrequency()
                    * (termFrequency * (config.k1() + 1.0))
                    / (termFrequency + normalization);
        }
        return score;
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
