package io.github.patricklfdm.generalsearch.ranking;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.PriorityQueue;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/** Posting-driven BM25 retrieval with bounded top-K retention. */
public final class RankedSearcher<T> {
    private final CandidatePlanner<T> filterPlanner;

    public RankedSearcher() {
        this(new CandidatePlanner<>());
    }

    public RankedSearcher(CandidatePlanner<T> filterPlanner) {
        this.filterPlanner = Objects.requireNonNull(filterPlanner, "filterPlanner");
    }

    /** Searches one immutable snapshot without changing its unranked query behavior. */
    public List<SearchHit<T>> search(
            SearchSnapshot<T> snapshot,
            RankedSearchRequest<T> request
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        TextScoringQuery<T> scoringQuery = request.scoringQuery();
        if (scoringQuery.terms().isEmpty()) {
            return List.of();
        }

        TextIndexSnapshot<T> textIndex = requireTextIndex(snapshot, scoringQuery);
        List<ScoringTerm> scoringTerms = scoringTerms(textIndex, scoringQuery.terms());
        double averageDocumentLength = textIndex.averageDocumentLength();
        ImmutableBitmap candidates = textIndex.documentsContainingAny(
                scoringQuery.terms());
        Query<T> filter = request.filter().orElse(null);
        if (filter != null) {
            var filterCandidates = filterPlanner.plan(snapshot, filter);
            if (filterCandidates.isPresent()) {
                candidates = candidates.and(filterCandidates.get().bitmap());
            }
        }
        if (candidates.isEmpty()) {
            return List.of();
        }

        int initialCapacity = Math.min(request.limit(), candidates.cardinality());
        PriorityQueue<RankedCandidate<T>> top = new PriorityQueue<>(
                Math.max(1, initialCapacity),
                worstFirst()
        );
        ImmutableBitmap scoringCandidates = candidates;
        scoringCandidates.forEachSetBit(docId -> {
            T document = snapshot.get(docId);
            if (document == null || (filter != null && !filter.matches(document))) {
                return;
            }
            double score = score(
                    scoringTerms,
                    textIndex.documentLength(docId),
                    averageDocumentLength,
                    docId,
                    request.config()
            );
            if (score <= 0.0) {
                return;
            }
            RankedCandidate<T> candidate = new RankedCandidate<>(docId, document, score);
            if (top.size() < request.limit()) {
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

    private TextIndexSnapshot<T> requireTextIndex(
            SearchSnapshot<T> snapshot,
            TextScoringQuery<T> query
    ) {
        for (IndexSnapshot<T> candidate : snapshot.indexes().indexes()) {
            if (candidate instanceof TextIndexSnapshot<?> text
                    && text.textField() == query.textField()) {
                @SuppressWarnings("unchecked")
                TextIndexSnapshot<T> typed = (TextIndexSnapshot<T>) text;
                return typed;
            }
        }
        throw new IllegalStateException(
                "ranked search requires the canonical text index: "
                        + query.textField().name());
    }

    private List<ScoringTerm> scoringTerms(
            TextIndexSnapshot<T> index,
            List<String> terms
    ) {
        int documentCount = index.statistics().indexedDocumentCount();
        List<ScoringTerm> scoringTerms = new ArrayList<>(terms.size());
        for (String term : terms) {
            PostingList posting = index.posting(term);
            if (posting.documentFrequency() == 0) {
                continue;
            }
            double inverseDocumentFrequency = Math.log1p(
                    (documentCount - posting.documentFrequency() + 0.5)
                            / (posting.documentFrequency() + 0.5)
            );
            scoringTerms.add(new ScoringTerm(posting, inverseDocumentFrequency));
        }
        return List.copyOf(scoringTerms);
    }

    private double score(
            List<ScoringTerm> terms,
            int documentLength,
            double averageLength,
            int docId,
            Bm25Config config
    ) {
        if (averageLength == 0.0 || documentLength == 0) {
            return 0.0;
        }
        double normalization = config.k1() * (
                1.0 - config.b()
                        + config.b() * documentLength / averageLength
        );
        double score = 0.0;
        for (ScoringTerm term : terms) {
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

    private record RankedCandidate<T>(int docId, T document, double score) {}

    private record ScoringTerm(
            PostingList posting,
            double inverseDocumentFrequency
    ) {}
}
