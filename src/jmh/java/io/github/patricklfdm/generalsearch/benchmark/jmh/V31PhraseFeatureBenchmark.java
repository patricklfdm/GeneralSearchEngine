package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
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

/** V3.1 feature-lane coverage for slop and analyzed-position phrase shapes. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V31PhraseFeatureBenchmark {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> GAPPED =
            Field.of("gapped", String.class, Document::gapped);
    private static final Field<Document, String> ALTERNATIVES =
            Field.of("alternatives", String.class, Document::alternatives);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final TextField<Document> GAPPED_TEXT =
            TextField.of(GAPPED, positionedAnalyzer(false));
    private static final TextField<Document> ALTERNATIVES_TEXT =
            TextField.of(ALTERNATIVES, positionedAnalyzer(true));

    @Param({"100000", "1000000"})
    public int documentCount;

    @Param({
            "low-s0", "high-s0", "low-s1", "high-s1",
            "low-s2", "high-s2", "low-s4", "high-s4",
            "repeated", "analyzer-gap", "same-position"
    })
    public String scenario;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> request;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(BODY_TEXT),
                        IndexDefinition.text(GAPPED_TEXT),
                        IndexDefinition.text(ALTERNATIVES_TEXT)
                ))
        );
        for (int documentId = 0; documentId < documentCount; documentId++) {
            boolean rare = documentId % 97 == 0;
            String lead = rare ? "rare" : "common";
            String body = lead + " a b c d target";
            if (documentId % 211 == 0) {
                body += " echo echo gap echo";
            }
            builder.add(documentId, new Document(
                    body,
                    documentId % 997 == 0 ? "quiet neighborhood" : "",
                    documentId % 991 == 0 ? "rapid quick route" : ""
            ));
        }
        snapshot = builder.build();
        request = SearchRequest.<Document>builder()
                .query(queryForScenario())
                .limit(10)
                .build();
        List<SearchHit<Document>> hits = execute();
        verifyHits(hits, expectedHitCount());
        if (scenario.endsWith("-s0")) {
            String text = scenario.startsWith("low") ? "rare a" : "common a";
            SearchRequest<Document> legacy = SearchRequest.of(
                    SearchQueries.phrase(BODY_TEXT, text));
            SearchRequest<Document> explicit = SearchRequest.of(
                    SearchQueries.phrase(BODY_TEXT, text, 0));
            if (!SearchExecutionAccess.search(snapshot, legacy, planner).hits().equals(
                    SearchExecutionAccess.search(snapshot, explicit, planner).hits())) {
                throw new IllegalStateException(
                        "legacy and explicit-zero phrase controls differ");
            }
        }
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

    private io.github.patricklfdm.generalsearch.search.SearchQuery<Document>
            queryForScenario() {
        if (scenario.equals("repeated")) {
            return SearchQueries.phrase(BODY_TEXT, "echo echo echo", 1);
        }
        if (scenario.equals("analyzer-gap")) {
            return SearchQueries.phrase(GAPPED_TEXT, "quiet neighborhood", 0);
        }
        if (scenario.equals("same-position")) {
            return SearchQueries.phrase(
                    ALTERNATIVES_TEXT,
                    "rapid quick route",
                    0
            );
        }
        String[] parts = scenario.split("-s", -1);
        if (parts.length != 2) {
            throw new IllegalArgumentException("unknown phrase scenario: " + scenario);
        }
        int slop = Integer.parseInt(parts[1]);
        String lead = parts[0].equals("low") ? "rare" : "common";
        String second = switch (slop) {
            case 0 -> "a";
            case 1 -> "b";
            case 2 -> "c";
            case 4 -> "target";
            default -> throw new IllegalArgumentException(
                    "unsupported phrase slop: " + slop);
        };
        return SearchQueries.phrase(BODY_TEXT, lead + " " + second, slop);
    }

    private List<SearchHit<Document>> execute() {
        return SearchExecutionAccess.search(snapshot, request, planner).hits();
    }

    private int expectedHitCount() {
        int divisor = switch (scenario) {
            case "repeated" -> 211;
            case "analyzer-gap" -> 997;
            case "same-position" -> 991;
            default -> scenario.startsWith("low-") ? 97 : 1;
        };
        int matchingDocuments = scenario.startsWith("high-")
                ? documentCount - ((documentCount - 1) / 97 + 1)
                : (documentCount - 1) / divisor + 1;
        return Math.min(10, matchingDocuments);
    }

    private static void verifyHits(
            List<SearchHit<Document>> hits,
            int expectedHitCount) {
        if (hits.size() != expectedHitCount) {
            throw new IllegalStateException(
                    "expected " + expectedHitCount
                            + " phrase control hits, found " + hits.size());
        }
        double previous = Double.POSITIVE_INFINITY;
        for (SearchHit<Document> hit : hits) {
            if (hit.score() > previous) {
                throw new IllegalStateException("phrase scores are not descending");
            }
            previous = hit.score();
        }
    }

    private static Analyzer positionedAnalyzer(boolean samePosition) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                List<Token> terms = analyze(text);
                List<AnalyzedToken> positioned = new ArrayList<>(terms.size());
                for (int index = 0; index < terms.size(); index++) {
                    int increment = 1;
                    if (index == 1) {
                        increment = samePosition ? 0 : 3;
                    }
                    positioned.add(new AnalyzedToken(
                            terms.get(index).term(), increment));
                }
                return List.copyOf(positioned);
            }
        };
    }

    private record Document(String body, String gapped, String alternatives) {
    }
}
