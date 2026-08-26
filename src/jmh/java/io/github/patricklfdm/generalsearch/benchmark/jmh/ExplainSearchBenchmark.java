package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
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

/** Contrasts the normal ranked hot path with matching and non-matching Explain. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class ExplainSearchBenchmark {
    private static final Field<Document, Long> ID =
            Field.of("id", Long.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    private SearchEngine<Long, Document> engine;
    private SearchRequest<Document> request;
    private long matchingId;
    private long nonMatchingId;

    @Setup(Level.Trial)
    public void setUp() {
        engine = SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
        List<Document> documents = new ArrayList<>(documentCount);
        for (int docId = 0; docId < documentCount; docId++) {
            documents.add(new Document(
                    docId,
                    docId % 5 == 0
                            ? "java search engine snapshot"
                            : "stable travel document"
            ));
        }
        for (int start = 0; start < documents.size(); start += 1_000) {
            int end = Math.min(start + 1_000, documents.size());
            engine.addAll(documents.subList(start, end)).join();
        }
        request = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .must(SearchQueries.text(BODY_TEXT, "java"))
                        .should(SearchQueries.text(BODY_TEXT, "search").boost(2.0))
                        .build())
                .limit(10)
                .build();
        matchingId = 0L;
        nonMatchingId = documentCount - 1L;
        if (!engine.explain(request, matchingId).orElseThrow().matched()
                || engine.explain(request, nonMatchingId).orElseThrow().matched()) {
            throw new IllegalStateException("invalid Explain benchmark controls");
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public double normalSearchTop10() {
        return engine.search(request).hits().getFirst().score();
    }

    @Benchmark
    public double explainMatchingDocument() {
        return engine.explain(request, matchingId)
                .map(SearchExplanation::score)
                .orElseThrow();
    }

    @Benchmark
    public int explainNonMatchingDocument() {
        return engine.explain(request, nonMatchingId)
                .orElseThrow()
                .detail()
                .children()
                .size();
    }

    private record Document(long id, String body) {
    }
}
