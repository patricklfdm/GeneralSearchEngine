package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExecutionAccess;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
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

/** Measures posting-filtered exact phrase verification and ranked composition. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class PhraseSearchBenchmark {
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> exactPhrase;
    private SearchRequest<Document> composedPhrase;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TITLE_TEXT),
                        IndexDefinition.text(BODY_TEXT)
                ))
        );
        for (int docId = 0; docId < documentCount; docId++) {
            String body;
            if (docId % 5 == 0) {
                body = "premium noise cancelling headphones travel";
            } else if (docId % 7 == 0) {
                body = "noise premium cancelling headphones travel";
            } else {
                body = "stable travel audio guide";
            }
            builder.add(docId, new Document(
                    docId,
                    docId % 3 == 0 ? "wireless audio" : "travel guide",
                    body
            ));
        }
        snapshot = builder.build();
        exactPhrase = SearchRequest.<Document>builder()
                .query(SearchQueries.phrase(
                        BODY_TEXT,
                        "noise cancelling headphones"
                ))
                .limit(10)
                .build();
        composedPhrase = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .must(SearchQueries.text(TITLE_TEXT, "wireless"))
                        .should(SearchQueries.phrase(
                                BODY_TEXT,
                                "noise cancelling headphones"
                        ).boost(2.0))
                        .build())
                .limit(10)
                .build();

        verify(SearchExecutionAccess.search(snapshot, exactPhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, composedPhrase, planner).hits());
    }

    @Benchmark
    public double exactPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                exactPhrase,
                planner
        ).hits());
    }

    @Benchmark
    public double composedPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                composedPhrase,
                planner
        ).hits());
    }

    private void verify(List<SearchHit<Document>> hits) {
        if (hits.size() != 10) {
            throw new IllegalStateException("expected ten benchmark hits");
        }
        double previous = Double.POSITIVE_INFINITY;
        for (SearchHit<Document> hit : hits) {
            if (hit.score() > previous) {
                throw new IllegalStateException("scores are not descending");
            }
            previous = hit.score();
        }
    }

    private double firstScore(List<SearchHit<Document>> hits) {
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    private record Document(int id, String title, String body) {
    }
}
