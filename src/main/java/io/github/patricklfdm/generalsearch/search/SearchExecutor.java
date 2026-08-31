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

    SearchPageResult<T> executePage(
            SearchPlan<T> plan,
            TotalHitsMode totalHitsMode,
            PageAnchor after,
            Object cursorOwnerToken,
            SearchRequest<T> searchRequest,
            long snapshotVersion
    ) {
        Objects.requireNonNull(plan, "plan");
        Objects.requireNonNull(totalHitsMode, "totalHitsMode");
        Objects.requireNonNull(cursorOwnerToken, "cursorOwnerToken");
        Objects.requireNonNull(searchRequest, "searchRequest");
        PageAccumulator<T> page = rankedPageCandidates(
                plan,
                totalHitsMode,
                after
        );
        List<RankedCandidate<T>> ranked = page.ranked();
        List<SearchHit<T>> hits = ranked.stream()
                .map(candidate -> new SearchHit<>(
                        candidate.document(),
                        candidate.score()
                ))
                .toList();
        SearchAfterCursor nextCursor = null;
        if (page.hasMore()) {
            RankedCandidate<T> last = ranked.getLast();
            nextCursor = new BuiltInSearchAfterCursor(
                    cursorOwnerToken,
                    searchRequest,
                    snapshotVersion,
                    last.score(),
                    last.docId()
            );
        }
        if (totalHitsMode == TotalHitsMode.EXACT) {
            return nextCursor == null
                    ? SearchPageResult.withExactTotalHits(
                            hits,
                            page.exactTotalHits()
                    )
                    : SearchPageResult.withExactTotalHits(
                            hits,
                            nextCursor,
                            page.exactTotalHits()
                    );
        }
        return nextCursor == null
                ? SearchPageResult.withoutTotalHits(hits)
                : SearchPageResult.withoutTotalHits(hits, nextCursor);
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

    private PageAccumulator<T> rankedPageCandidates(
            SearchPlan<T> plan,
            TotalHitsMode totalHitsMode,
            PageAnchor after
    ) {
        int initialCapacity = Math.min(
                plan.limit(),
                plan.candidates().cardinality()
        );
        PageAccumulator<T> page = new PageAccumulator<>(
                plan.limit(),
                initialCapacity,
                totalHitsMode == TotalHitsMode.EXACT,
                after
        );
        if (plan.candidates().isEmpty()) {
            return page;
        }

        ImmutableBitmap scoringCandidates = plan.candidates();
        scoringCandidates.forEachSetBit(docId -> {
            T document = plan.snapshot().get(docId);
            if (document == null
                    || (plan.filter() != null
                    && !plan.filter().matches(document))) {
                return;
            }
            ScoreMatch result = Objects.requireNonNull(plan.root()).evaluate(docId);
            if (!result.matched()) {
                return;
            }
            page.recordMatch(docId, document, result.score());
        });
        return page;
    }

    private static <T> boolean isBetter(
            RankedCandidate<T> candidate,
            RankedCandidate<T> currentWorst
    ) {
        int scoreComparison = Double.compare(candidate.score(), currentWorst.score());
        return scoreComparison > 0
                || (scoreComparison == 0 && candidate.docId() < currentWorst.docId());
    }

    private static <T> Comparator<RankedCandidate<T>> worstFirst() {
        return Comparator
                .comparingDouble(RankedCandidate<T>::score)
                .thenComparing(
                        Comparator.comparingInt(RankedCandidate<T>::docId).reversed());
    }

    private static <T> Comparator<RankedCandidate<T>> bestFirst() {
        return Comparator
                .comparingDouble(RankedCandidate<T>::score)
                .reversed()
                .thenComparingInt(RankedCandidate<T>::docId);
    }

    private record RankedCandidate<T>(int docId, T document, double score) {
    }

    private static final class PageAccumulator<T> {
        private final int limit;
        private final boolean exact;
        private final PageAnchor after;
        private final PriorityQueue<RankedCandidate<T>> top;
        private long exactTotalHits;
        private long eligibleMatches;

        private PageAccumulator(
                int limit,
                int initialCapacity,
                boolean exact,
                PageAnchor after
        ) {
            this.limit = limit;
            this.exact = exact;
            this.after = after;
            this.top = new PriorityQueue<>(
                    Math.max(1, initialCapacity),
                    worstFirst()
            );
        }

        private void recordMatch(int docId, T document, double score) {
            if (exact) {
                exactTotalHits = Math.incrementExact(exactTotalHits);
            }
            if (after != null && !isAfter(score, docId, after)) {
                return;
            }
            eligibleMatches = Math.incrementExact(eligibleMatches);
            RankedCandidate<T> candidate = new RankedCandidate<>(
                    docId,
                    document,
                    score
            );
            if (top.size() < limit) {
                top.add(candidate);
            } else if (isBetter(candidate, Objects.requireNonNull(top.peek()))) {
                top.remove();
                top.add(candidate);
            }
        }

        private List<RankedCandidate<T>> ranked() {
            List<RankedCandidate<T>> ranked = new ArrayList<>(top);
            ranked.sort(bestFirst());
            return ranked;
        }

        private boolean hasMore() {
            return eligibleMatches > top.size();
        }

        private long exactTotalHits() {
            return exactTotalHits;
        }

        private static boolean isAfter(
                double score,
                int documentId,
                PageAnchor after
        ) {
            int scoreComparison = Double.compare(score, after.score());
            return scoreComparison < 0
                    || (scoreComparison == 0
                    && documentId > after.documentId());
        }
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
