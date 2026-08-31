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
import io.github.patricklfdm.generalsearch.search.SearchAfterCursor;
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

/** Measures strict current-snapshot continuation at a controlled page depth. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V33SearchAfterBenchmark {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    @Param("10")
    public int pageSize;

    @Param({"1", "10", "100"})
    public int pageDepth;

    @Param({"dense-ties", "score-bands"})
    public String corpusShape;

    private SearchEngine<Integer, Document> engine;
    private SearchRequest<Document> request;
    private SearchPageRequest<Document> continuationDisabled;
    private SearchPageRequest<Document> continuationExact;

    @Setup(Level.Trial)
    public void setUp() {
        if ((long) pageSize * (pageDepth + 1L) >= documentCount) {
            throw new IllegalArgumentException(
                    "benchmark requires a later page after the measured page");
        }
        engine = SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(TEXT))
                .build();
        List<Document> documents = new ArrayList<>(documentCount);
        for (int id = 0; id < documentCount; id++) {
            String body = switch (corpusShape) {
                case "dense-ties" -> "page stable";
                case "score-bands" -> "page ".repeat(1 + id % 8) + "stable";
                default -> throw new IllegalArgumentException(
                        "unknown corpus shape: " + corpusShape);
            };
            documents.add(new Document(id, body));
        }
        for (int start = 0; start < documents.size(); start += 1_000) {
            engine.addAll(documents.subList(
                    start,
                    Math.min(start + 1_000, documents.size())
            )).join();
        }
        request = SearchRequest.<Document>builder()
                .query(SearchQueries.text(TEXT, "page"))
                .limit(pageSize)
                .build();

        SearchPageResult<Document> page = engine.search(
                SearchPageRequest.builder(request).build());
        for (int depth = 1; depth < pageDepth; depth++) {
            page = engine.search(SearchPageRequest.builder(request)
                    .after(page.nextCursor().orElseThrow())
                    .build());
        }
        SearchAfterCursor anchor = page.nextCursor().orElseThrow();
        continuationDisabled = SearchPageRequest.builder(request)
                .after(anchor)
                .build();
        continuationExact = SearchPageRequest.builder(request)
                .after(anchor)
                .totalHits(TotalHitsMode.EXACT)
                .build();

        assertControl(engine.search(continuationDisabled), false);
        assertControl(engine.search(continuationExact), true);
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public long continuationDisabled() {
        return checksum(engine.search(continuationDisabled));
    }

    @Benchmark
    public long continuationExact() {
        return checksum(engine.search(continuationExact));
    }

    private void assertControl(SearchPageResult<Document> page, boolean exact) {
        if (page.hits().size() != pageSize
                || page.nextCursor().isEmpty()
                || exact != page.totalHits().isPresent()
                || (exact && page.totalHits().orElseThrow() != documentCount)) {
            throw new IllegalStateException("invalid continuation controls");
        }
    }

    private static long checksum(SearchPageResult<Document> page) {
        long checksum = page.hits().size();
        for (SearchHit<Document> hit : page.hits()) {
            checksum = 31L * checksum + hit.document().id();
            checksum = 31L * checksum
                    + Double.doubleToRawLongBits(hit.score());
        }
        checksum = 31L * checksum + (page.nextCursor().isPresent() ? 1L : 0L);
        return page.totalHits().isPresent()
                ? 31L * checksum + page.totalHits().orElseThrow()
                : checksum;
    }

    private record Document(int id, String body) {
    }
}
