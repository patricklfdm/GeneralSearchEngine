package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
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

/** Measures V2-equivalent ranking beside the canonical V3 request path. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V3TextCompatibilityBenchmark {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private RankedSearchRequest<Document> legacy;
    private SearchRequest<Document> v3;
    private SearchRequest<Document> filtered;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(BODY_TEXT),
                        IndexDefinition.equality(CATEGORY)
                ))
        );
        for (int docId = 0; docId < documentCount; docId++) {
            String body = docId % 5 == 0
                    ? "java search engine snapshot"
                    : "stable travel document";
            builder.add(docId, new Document(
                    docId,
                    body,
                    docId % 10 == 0 ? "eligible" : "other"
            ));
        }
        snapshot = builder.build();
        legacy = RankedSearchRequest.of(
                TextScoringQuery.of(BODY_TEXT, "java search"),
                10
        );
        v3 = SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "java search"))
                .limit(10)
                .build();
        filtered = SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "java search"))
                .filter(Query.eq(CATEGORY, "eligible"))
                .limit(10)
                .build();

        List<SearchHit<Document>> legacyHits =
                SearchExecutionAccess.search(snapshot, legacy, planner);
        List<SearchHit<Document>> v3Hits =
                SearchExecutionAccess.search(snapshot, v3, planner).hits();
        if (!legacyHits.equals(v3Hits)) {
            throw new IllegalStateException("legacy and V3 benchmark controls differ");
        }
    }

    @Benchmark
    public double legacyTextTop10() {
        return firstScore(SearchExecutionAccess.search(snapshot, legacy, planner));
    }

    @Benchmark
    public double v3TextTop10() {
        return firstScore(SearchExecutionAccess.search(snapshot, v3, planner).hits());
    }

    @Benchmark
    public double v3TextAndFilterTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                filtered,
                planner
        ).hits());
    }

    private static double firstScore(List<SearchHit<Document>> hits) {
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    private record Document(int id, String body, String category) {
    }
}
