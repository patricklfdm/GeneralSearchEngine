package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
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

/** Measures posting-filtered exact and ordered-slop phrase verification. */
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
    private static final Field<Document, String> GAPPED_BODY =
            Field.of("gappedBody", String.class, Document::gappedBody);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final TextField<Document> GAPPED_BODY_TEXT =
            TextField.of(GAPPED_BODY, gappedAnalyzer());

    @Param("10000")
    public int documentCount;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> exactPhrase;
    private SearchRequest<Document> explicitZeroPhrase;
    private SearchRequest<Document> sloppyPhrase;
    private SearchRequest<Document> composedPhrase;
    private SearchRequest<Document> selectivePhrase;
    private SearchRequest<Document> commonPhrase;
    private SearchRequest<Document> repeatedPhrase;
    private SearchRequest<Document> longPhrase;
    private SearchRequest<Document> gappedPhrase;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TITLE_TEXT),
                        IndexDefinition.text(BODY_TEXT),
                        IndexDefinition.text(GAPPED_BODY_TEXT)
                ))
        );
        for (int docId = 0; docId < documentCount; docId++) {
            String body;
            if (docId % 5 == 0) {
                body = "premium noise cancelling headphones travel";
            } else if (docId % 7 == 0) {
                body = "noise premium cancelling headphones travel";
            } else if (docId % 11 == 0) {
                body = "echo echo echo echo travel";
            } else {
                body = "stable travel audio guide";
            }
            builder.add(docId, new Document(
                    docId,
                    docId % 3 == 0 ? "wireless audio" : "travel guide",
                    body,
                    docId % 2 == 0
                            ? "quiet neighborhood"
                            : "quiet distant neighborhood"
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
        explicitZeroPhrase = SearchRequest.<Document>builder()
                .query(SearchQueries.phrase(
                        BODY_TEXT,
                        "noise cancelling headphones",
                        0
                ))
                .limit(10)
                .build();
        sloppyPhrase = SearchRequest.<Document>builder()
                .query(SearchQueries.phrase(
                        BODY_TEXT,
                        "premium cancelling headphones",
                        1
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
        selectivePhrase = SearchRequest.of(SearchQueries.phrase(
                BODY_TEXT,
                "premium noise cancelling"
        ));
        commonPhrase = SearchRequest.of(SearchQueries.phrase(
                BODY_TEXT,
                "stable travel"
        ));
        repeatedPhrase = SearchRequest.of(SearchQueries.phrase(
                BODY_TEXT,
                "echo echo echo"
        ));
        longPhrase = SearchRequest.of(SearchQueries.phrase(
                BODY_TEXT,
                "premium noise cancelling headphones travel"
        ));
        gappedPhrase = SearchRequest.of(SearchQueries.phrase(
                GAPPED_BODY_TEXT,
                "quiet neighborhood"
        ));

        List<SearchHit<Document>> exactHits = SearchExecutionAccess.search(
                snapshot,
                exactPhrase,
                planner
        ).hits();
        List<SearchHit<Document>> explicitZeroHits = SearchExecutionAccess.search(
                snapshot,
                explicitZeroPhrase,
                planner
        ).hits();
        verify(exactHits);
        if (!exactHits.equals(explicitZeroHits)) {
            throw new IllegalStateException(
                    "legacy and explicit-zero phrase results differ");
        }
        verify(SearchExecutionAccess.search(snapshot, sloppyPhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, composedPhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, selectivePhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, commonPhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, repeatedPhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, longPhrase, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, gappedPhrase, planner).hits());
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
    public double sloppyPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                sloppyPhrase,
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

    @Benchmark
    public double selectivePhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                selectivePhrase,
                planner
        ).hits());
    }

    @Benchmark
    public double commonPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                commonPhrase,
                planner
        ).hits());
    }

    @Benchmark
    public double repeatedPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                repeatedPhrase,
                planner
        ).hits());
    }

    @Benchmark
    public double longPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                longPhrase,
                planner
        ).hits());
    }

    @Benchmark
    public double positionGapPhraseTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                gappedPhrase,
                planner
        ).hits());
    }

    private static Analyzer gappedAnalyzer() {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                List<Token> terms = analyze(text);
                java.util.ArrayList<AnalyzedToken> positioned =
                        new java.util.ArrayList<>(terms.size());
                for (int index = 0; index < terms.size(); index++) {
                    positioned.add(new AnalyzedToken(
                            terms.get(index).term(),
                            index == 1 ? 2 : 1
                    ));
                }
                return List.copyOf(positioned);
            }
        };
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

    private record Document(int id, String title, String body, String gappedBody) {
    }
}
