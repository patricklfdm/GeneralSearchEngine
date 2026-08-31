package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.FieldHighlight;
import io.github.patricklfdm.generalsearch.search.HighlightFragment;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchHit;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageResult;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.TotalHitsMode;
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
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Warmup;

/**
 * Captures representative signed-V3.3 read paths before V3.4 hardening probes
 * exist. It deliberately implements no cold-build, heap, burst, or cloud workload.
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V34FinalHardeningBaselineBenchmark {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    @Param({"1", "10", "100"})
    public int topK;

    @Param({"sparse", "dense-ties"})
    public String corpusShape;

    private SearchEngine<Integer, Document> engine;
    private SearchRequest<Document> ordinaryRequest;
    private HighlightedSearchRequest<Document> highlightedRequest;
    private SearchPageRequest<Document> firstPageDisabled;
    private SearchPageRequest<Document> firstPageExact;

    @Setup(Level.Trial)
    public void setUp() {
        engine = SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
        List<Document> documents = new ArrayList<>(documentCount);
        int matching = 0;
        for (int id = 0; id < documentCount; id++) {
            boolean match = switch (corpusShape) {
                case "sparse" -> id % 100 == 0;
                case "dense-ties" -> true;
                default -> throw new IllegalArgumentException(
                        "unknown corpus shape: " + corpusShape);
            };
            documents.add(new Document(
                    id,
                    match ? "final hardening stable" : "unrelated stable"
            ));
            matching += match ? 1 : 0;
        }
        for (int start = 0; start < documents.size(); start += 1_000) {
            engine.addAll(documents.subList(
                    start,
                    Math.min(start + 1_000, documents.size())
            )).join();
        }

        ordinaryRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "hardening"))
                .limit(topK)
                .build();
        highlightedRequest = HighlightedSearchRequest
                .<Document>builder(ordinaryRequest)
                .field(BODY_TEXT)
                .contextCharacters(0)
                .maxFragmentsPerField(1)
                .build();
        firstPageDisabled = SearchPageRequest.builder(ordinaryRequest).build();
        firstPageExact = SearchPageRequest.builder(ordinaryRequest)
                .totalHits(TotalHitsMode.EXACT)
                .build();

        List<SearchHit<Document>> ordinary = engine.search(ordinaryRequest).hits();
        List<SearchHit<Document>> highlighted = engine.search(highlightedRequest)
                .hits().stream().map(HighlightedSearchHit::hit).toList();
        SearchPageResult<Document> disabled = engine.search(firstPageDisabled);
        SearchPageResult<Document> exact = engine.search(firstPageExact);
        if (ordinary.size() != Math.min(topK, matching)
                || !ordinary.equals(highlighted)
                || !ordinary.equals(disabled.hits())
                || !ordinary.equals(exact.hits())
                || disabled.totalHits().isPresent()
                || exact.totalHits().orElseThrow() != matching) {
            throw new IllegalStateException("invalid V3.3 baseline controls");
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public long ordinaryRankedSearch() {
        return hitChecksum(engine.search(ordinaryRequest).hits());
    }

    @Benchmark
    public long highlightedSearch() {
        long checksum = 1;
        for (HighlightedSearchHit<Document> hit
                : engine.search(highlightedRequest).hits()) {
            checksum = 31L * checksum + hit.hit().document().id();
            checksum = 31L * checksum
                    + Double.doubleToRawLongBits(hit.hit().score());
            for (FieldHighlight field : hit.highlights()) {
                checksum = 31L * checksum + field.fieldName().length();
                for (HighlightFragment fragment : field.fragments()) {
                    checksum = 31L * checksum + fragment.startOffset();
                    checksum = 31L * checksum + fragment.endOffset();
                }
            }
        }
        return checksum;
    }

    @Benchmark
    public long firstPageDisabled() {
        return hitChecksum(engine.search(firstPageDisabled).hits());
    }

    @Benchmark
    public long firstPageExact() {
        SearchPageResult<Document> page = engine.search(firstPageExact);
        return 31L * hitChecksum(page.hits()) + page.totalHits().orElseThrow();
    }

    private static long hitChecksum(List<SearchHit<Document>> hits) {
        long checksum = hits.size();
        for (SearchHit<Document> hit : hits) {
            checksum = 31L * checksum + hit.document().id();
            checksum = 31L * checksum
                    + Double.doubleToRawLongBits(hit.score());
        }
        return checksum;
    }

    private record Document(int id, String body) {
    }
}
