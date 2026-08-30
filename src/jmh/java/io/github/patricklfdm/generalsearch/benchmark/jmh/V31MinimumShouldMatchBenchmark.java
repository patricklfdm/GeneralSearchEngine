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

/** V3.1 feature-lane BOOL-width and minimum-should-match matrix. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V31MinimumShouldMatchBenchmark {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param({"100000", "1000000"})
    public int documentCount;

    @Param({"4", "16", "64"})
    public int shouldWidth;

    @Param({"one", "half", "all"})
    public String minimum;

    @Param({"false", "true"})
    public boolean withMust;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> request;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(IndexDefinition.text(BODY_TEXT)))
        );
        for (int documentId = 0; documentId < documentCount; documentId++) {
            StringBuilder body = new StringBuilder(96);
            if ((documentId & 1) == 0 || documentId % 97 == 0) {
                body.append("required ");
            }
            int terms = documentId % 97 == 0 ? 64 : 8;
            for (int offset = 0; offset < terms; offset++) {
                if (!body.isEmpty() && body.charAt(body.length() - 1) != ' ') {
                    body.append(' ');
                }
                int term = documentId % 97 == 0
                        ? offset
                        : Math.floorMod(documentId + offset, 64);
                body.append(termName(term));
            }
            builder.add(documentId, new Document(body.toString()));
        }
        snapshot = builder.build();

        SearchQueries.BoolBuilder<Document> query = SearchQueries.bool();
        if (withMust) {
            query.must(SearchQueries.text(BODY_TEXT, "required"));
        }
        for (int term = 0; term < shouldWidth; term++) {
            query.should(SearchQueries.text(BODY_TEXT, termName(term)));
        }
        query.minimumShouldMatch(switch (minimum) {
            case "one" -> 1;
            case "half" -> (shouldWidth + 1) / 2;
            case "all" -> shouldWidth;
            default -> throw new IllegalArgumentException(
                    "unknown minimum scenario: " + minimum);
        });
        request = SearchRequest.<Document>builder()
                .query(query.build())
                .limit(10)
                .build();
        verifyHits(execute());
    }

    @Benchmark
    public long search() {
        List<SearchHit<Document>> hits = execute();
        long checksum = hits.size();
        for (SearchHit<Document> hit : hits) {
            checksum = 31L * checksum + hit.document().hashCode();
            checksum = 31L * checksum + Double.doubleToLongBits(hit.score());
        }
        return checksum;
    }

    private List<SearchHit<Document>> execute() {
        return SearchExecutionAccess.search(snapshot, request, planner).hits();
    }

    private static String termName(int term) {
        return term < 10 ? "term0" + term : "term" + term;
    }

    private static void verifyHits(List<SearchHit<Document>> hits) {
        if (hits.size() != 10) {
            throw new IllegalStateException("expected ten BOOL control hits");
        }
        double previous = Double.POSITIVE_INFINITY;
        for (SearchHit<Document> hit : hits) {
            if (hit.score() > previous) {
                throw new IllegalStateException("BOOL scores are not descending");
            }
            previous = hit.score();
        }
    }

    private record Document(String body) {
    }
}
