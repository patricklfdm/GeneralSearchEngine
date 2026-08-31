package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageResult;
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
 * Captures the signed-V3.2 ordinary ranked path before V3.3 page execution is
 * introduced. Dense equal-score and sparse corpora become stable comparison cells.
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V33PaginationBaselineBenchmark {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
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
    private SearchRequest<Document> filteredRequest;
    private SearchPageRequest<Document> firstPageDisabled;
    private SearchPageRequest<Document> firstPageExact;
    private SearchPageRequest<Document> filteredFirstPageExact;

    @Setup(Level.Trial)
    public void setUp() {
        engine = SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .index(IndexDefinition.equality(CATEGORY))
                .build();
        List<Document> documents = new ArrayList<>(documentCount);
        int matching = 0;
        int filteredMatching = 0;
        for (int id = 0; id < documentCount; id++) {
            boolean match = switch (corpusShape) {
                case "sparse" -> id % 100 == 0;
                case "dense-ties" -> true;
                default -> throw new IllegalArgumentException(
                        "unknown corpus shape: " + corpusShape);
            };
            boolean eligible = id % 2 == 0;
            documents.add(new Document(
                    id,
                    match ? "page search stable" : "unrelated stable document",
                    eligible ? "eligible" : "other"
            ));
            if (match) {
                matching++;
                if (eligible) {
                    filteredMatching++;
                }
            }
        }
        for (int start = 0; start < documents.size(); start += 1_000) {
            engine.addAll(documents.subList(
                    start,
                    Math.min(start + 1_000, documents.size())
            )).join();
        }

        ordinaryRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "page"))
                .limit(topK)
                .build();
        filteredRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "page"))
                .filter(Query.eq(CATEGORY, "eligible"))
                .limit(topK)
                .build();
        firstPageDisabled = SearchPageRequest.builder(ordinaryRequest).build();
        firstPageExact = SearchPageRequest.builder(ordinaryRequest)
                .totalHits(TotalHitsMode.EXACT)
                .build();
        filteredFirstPageExact = SearchPageRequest.builder(filteredRequest)
                .totalHits(TotalHitsMode.EXACT)
                .build();
        assertControl(ordinaryRequest, Math.min(topK, matching));
        assertControl(filteredRequest, Math.min(topK, filteredMatching));
        assertPageControl(firstPageDisabled, matching, false);
        assertPageControl(firstPageExact, matching, true);
        assertPageControl(filteredFirstPageExact, filteredMatching, true);
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public long ordinaryRankedSearch() {
        return checksum(engine.search(ordinaryRequest).hits());
    }

    @Benchmark
    public long filteredRankedSearch() {
        return checksum(engine.search(filteredRequest).hits());
    }

    @Benchmark
    public long firstPageDisabled() {
        return checksum(engine.search(firstPageDisabled).hits());
    }

    @Benchmark
    public long firstPageExact() {
        return pageChecksum(engine.search(firstPageExact));
    }

    @Benchmark
    public long filteredFirstPageExact() {
        return pageChecksum(engine.search(filteredFirstPageExact));
    }

    private void assertControl(SearchRequest<Document> request, int expectedSize) {
        List<SearchHit<Document>> hits = engine.search(request).hits();
        if (hits.size() != expectedSize) {
            throw new IllegalStateException(
                    "unexpected baseline hit count: " + hits.size());
        }
        for (int index = 1; index < hits.size(); index++) {
            SearchHit<Document> previous = hits.get(index - 1);
            SearchHit<Document> current = hits.get(index);
            int scoreComparison = Double.compare(
                    previous.score(),
                    current.score()
            );
            if (scoreComparison < 0
                    || (scoreComparison == 0
                    && previous.document().id() >= current.document().id())) {
                throw new IllegalStateException(
                        "ordinary ranked order is not canonical");
            }
        }
    }

    private void assertPageControl(
            SearchPageRequest<Document> request,
            long expectedTotal,
            boolean exact
    ) {
        SearchPageResult<Document> page = engine.search(request);
        List<SearchHit<Document>> ordinary = engine
                .search(request.searchRequest())
                .hits();
        if (!page.hits().equals(ordinary)
                || (expectedTotal > ordinary.size())
                != page.nextCursor().isPresent()
                || exact != page.totalHits().isPresent()
                || (exact && page.totalHits().orElseThrow() != expectedTotal)) {
            throw new IllegalStateException("invalid first-page controls");
        }
    }

    private static long checksum(List<SearchHit<Document>> hits) {
        long checksum = hits.size();
        for (SearchHit<Document> hit : hits) {
            checksum = 31L * checksum + hit.document().id();
            checksum = 31L * checksum
                    + Double.doubleToRawLongBits(hit.score());
        }
        return checksum;
    }

    private static long pageChecksum(SearchPageResult<Document> page) {
        long checksum = checksum(page.hits());
        return page.totalHits().isPresent()
                ? 31L * checksum + page.totalHits().orElseThrow()
                : checksum;
    }

    private record Document(int id, String body, String category) {
    }
}
