package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExecutionAccess;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
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

/** Measures prepared BOOL/BOOST composition across two field-local text indexes. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class RankedCompositionBenchmark {
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> mustShould;
    private SearchRequest<Document> allShould;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TITLE_TEXT),
                        IndexDefinition.text(BODY_TEXT),
                        IndexDefinition.equality(CATEGORY)
                ))
        );
        for (int docId = 0; docId < documentCount; docId++) {
            builder.add(docId, new Document(
                    docId,
                    docId % 3 == 0 ? "java engine" : "travel guide",
                    docId % 5 == 0 ? "search snapshot" : "stable content",
                    docId % 10 == 0 ? "eligible" : "other"
            ));
        }
        snapshot = builder.build();

        SearchQuery<Document> mustShouldQuery = SearchQueries.<Document>bool()
                .must(SearchQueries.text(TITLE_TEXT, "java"))
                .should(SearchQueries.text(BODY_TEXT, "search").boost(2.0))
                .build();
        mustShould = SearchRequest.<Document>builder()
                .query(mustShouldQuery)
                .filter(Query.eq(CATEGORY, "eligible"))
                .limit(10)
                .build();
        allShould = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .should(SearchQueries.text(TITLE_TEXT, "java"))
                        .should(SearchQueries.text(BODY_TEXT, "search").boost(2.0))
                        .build())
                .limit(10)
                .build();

        verify(SearchExecutionAccess.search(snapshot, mustShould, planner).hits());
        verify(SearchExecutionAccess.search(snapshot, allShould, planner).hits());
    }

    @Benchmark
    public double mustShouldCrossFieldTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                mustShould,
                planner
        ).hits());
    }

    @Benchmark
    public double allShouldCrossFieldTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                allShould,
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

    private record Document(int id, String title, String body, String category) {
    }
}
