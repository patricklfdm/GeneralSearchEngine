package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.RankedSearcher;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;

/** Measures multi-term BM25 with and without an indexed structured filter. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class Bm25MultiTermBenchmark {
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);
    private static final Field<TextDocument, String> CATEGORY =
            Field.of("category", String.class, TextDocument::category);
    private static final TextField<TextDocument> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("100000")
    public int documentCount;

    @Param({"1", "4", "8"})
    public int queryTokenCount;

    private final RankedSearcher<TextDocument> searcher = new RankedSearcher<>();
    private SearchSnapshot<TextDocument> snapshot;
    private RankedSearchRequest<TextDocument> unfiltered;
    private RankedSearchRequest<TextDocument> filtered;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<TextDocument> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TEXT),
                        IndexDefinition.equality(CATEGORY))));
        for (int docId = 0; docId < documentCount; docId++) {
            StringBuilder body = new StringBuilder("stable unique").append(docId);
            for (int term = 0; term < 8; term++) {
                if (docId % (term + 2) == 0) {
                    body.append(' ').append("term").append(term);
                    if ((docId + term) % 5 == 0) {
                        body.append(' ').append("term").append(term);
                    }
                }
            }
            builder.add(docId, new TextDocument(
                    docId,
                    body.toString(),
                    docId % 10 == 0 ? "eligible" : "other"));
        }
        snapshot = builder.build();

        StringBuilder queryText = new StringBuilder();
        for (int term = 0; term < queryTokenCount; term++) {
            if (!queryText.isEmpty()) {
                queryText.append(' ');
            }
            queryText.append("term").append(term);
        }
        TextScoringQuery<TextDocument> scoring =
                TextScoringQuery.of(TEXT, queryText.toString());
        unfiltered = RankedSearchRequest.of(scoring, 10);
        filtered = RankedSearchRequest.filtered(
                scoring,
                Query.eq(CATEGORY, "eligible"),
                10);
        verify(searcher.search(snapshot, unfiltered), false);
        verify(searcher.search(snapshot, filtered), true);
    }

    @Benchmark
    public double unfilteredTop10() {
        return firstScore(searcher.search(snapshot, unfiltered));
    }

    @Benchmark
    public double structuredFilteredTop10() {
        return firstScore(searcher.search(snapshot, filtered));
    }

    private void verify(List<SearchHit<TextDocument>> hits, boolean requireEligible) {
        if (hits.size() != 10) {
            throw new IllegalStateException("expected ten benchmark hits");
        }
        double previous = Double.POSITIVE_INFINITY;
        for (SearchHit<TextDocument> hit : hits) {
            if (hit.score() > previous) {
                throw new IllegalStateException("scores are not descending");
            }
            if (requireEligible && !"eligible".equals(hit.document().category())) {
                throw new IllegalStateException("filtered result is not eligible");
            }
            previous = hit.score();
        }
    }

    private double firstScore(List<SearchHit<TextDocument>> hits) {
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    private record TextDocument(int id, String body, String category) {}
}
