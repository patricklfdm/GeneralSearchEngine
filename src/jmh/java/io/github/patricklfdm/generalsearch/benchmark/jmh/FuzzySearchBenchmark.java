package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.Locale;
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

/** Measures bounded vocabulary-scan planning plus fuzzy top-K execution. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class FuzzySearchBenchmark {
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param({"10000", "100000"})
    public int vocabularySize;

    @Param({
            "exact",
            "substitution",
            "insertion",
            "deletion",
            "transposition",
            "two-edits",
            "no-match",
            "high-expansion"
    })
    public String scenario;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> fuzzy;
    private SearchRequest<Document> composedFuzzy;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TITLE_TEXT),
                        IndexDefinition.text(BODY_TEXT)
                ))
        );
        for (int docId = 0; docId < vocabularySize; docId++) {
            builder.add(docId, new Document(
                    docId,
                    docId % 3 == 0 ? "featured travel" : "standard travel",
                    vocabularyTerm(docId, scenario)
            ));
        }
        snapshot = builder.build();
        String queryText = queryText(scenario);
        fuzzy = SearchRequest.<Document>builder()
                .query(SearchQueries.fuzzy(BODY_TEXT, queryText))
                .limit(10)
                .build();
        composedFuzzy = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .must(SearchQueries.fuzzy(
                                BODY_TEXT,
                                queryText
                        ))
                        .should(SearchQueries.text(
                                TITLE_TEXT,
                                "featured"
                        ).boost(1.5))
                        .build())
                .limit(10)
                .build();

        boolean expectMatch = !"no-match".equals(scenario);
        verify(
                SearchExecutionAccess.search(snapshot, fuzzy, planner).hits(),
                expectMatch
        );
        verify(SearchExecutionAccess.search(
                snapshot,
                composedFuzzy,
                planner
        ).hits(), expectMatch);
    }

    @Benchmark
    public double fuzzyPlanAndTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                fuzzy,
                planner
        ).hits());
    }

    @Benchmark
    public double composedFuzzyPlanAndTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                composedFuzzy,
                planner
        ).hits());
    }

    private static String vocabularyTerm(int value, String scenario) {
        if ("high-expansion".equals(scenario)) {
            if (value == 0) {
                return "aaaaaaaa";
            }
            if (value <= 625) {
                int pair = value - 1;
                char first = (char) ('b' + pair / 25);
                char second = (char) ('b' + pair % 25);
                return new String(new char[]{
                        first, second, 'a', 'a', 'a', 'a', 'a', 'a'
                });
            }
        }
        return String.format(Locale.ROOT, "destination%05d", value);
    }

    private static String queryText(String scenario) {
        return switch (scenario) {
            case "exact" -> "destination00000";
            case "substitution" -> "xestination00000";
            case "insertion" -> "xdestination00000";
            case "deletion" -> "estination00000";
            case "transposition" -> "edstination00000";
            case "two-edits" -> "xxstination00000";
            case "no-match" -> "zzzzzzzzzzzzzzzz";
            case "high-expansion" -> "aaaaaaaa";
            default -> throw new IllegalArgumentException(
                    "unknown fuzzy scenario: " + scenario);
        };
    }

    private static void verify(
            List<SearchHit<Document>> hits,
            boolean expectMatch
    ) {
        if (hits.isEmpty() == expectMatch) {
            throw new IllegalStateException(
                    expectMatch
                            ? "expected benchmark hits"
                            : "expected no benchmark hits");
        }
        double previous = Double.POSITIVE_INFINITY;
        for (SearchHit<Document> hit : hits) {
            if (hit.score() > previous) {
                throw new IllegalStateException("scores are not descending");
            }
            previous = hit.score();
        }
    }

    private static double firstScore(List<SearchHit<Document>> hits) {
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    private record Document(int id, String title, String body) {
    }
}
