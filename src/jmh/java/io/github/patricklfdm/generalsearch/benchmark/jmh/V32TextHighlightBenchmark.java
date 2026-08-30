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

/** Contrasts canonical TEXT search with Phase 3 top-K source re-analysis. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V32TextHighlightBenchmark {
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

    @Param({"16", "256"})
    public int sourceTokenCount;

    @Param({"0", "40"})
    public int contextCharacters;

    @Param({"1", "3"})
    public int maxFragmentsPerField;

    private SearchEngine<Integer, Document> engine;
    private SearchRequest<Document> searchRequest;
    private HighlightedSearchRequest<Document> highlightedRequest;

    @Setup(Level.Trial)
    public void setUp() {
        engine = SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
        List<Document> documents = new ArrayList<>(documentCount);
        for (int id = 0; id < documentCount; id++) {
            StringBuilder source = new StringBuilder(sourceTokenCount * 10);
            for (int token = 0; token < sourceTokenCount; token++) {
                if (!source.isEmpty()) {
                    source.append(token % 5 == 0 ? ". " : " ");
                }
                source.append(token % 7 == 0 ? "highlight" : "stable");
            }
            documents.add(new Document(id, source.toString()));
        }
        for (int start = 0; start < documents.size(); start += 1_000) {
            engine.addAll(documents.subList(
                    start,
                    Math.min(start + 1_000, documents.size())
            )).join();
        }
        searchRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "highlight"))
                .limit(topK)
                .build();
        highlightedRequest = HighlightedSearchRequest.<Document>builder(searchRequest)
                .field(BODY_TEXT)
                .contextCharacters(contextCharacters)
                .maxFragmentsPerField(maxFragmentsPerField)
                .build();
        List<SearchHit<Document>> canonical = engine.search(searchRequest).hits();
        List<SearchHit<Document>> highlighted = engine.search(highlightedRequest)
                .hits()
                .stream()
                .map(HighlightedSearchHit::hit)
                .toList();
        if (!canonical.equals(highlighted) || canonical.size() != topK) {
            throw new IllegalStateException("invalid highlighted-search controls");
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public long ordinaryTextSearch() {
        long checksum = 0;
        for (SearchHit<Document> hit : engine.search(searchRequest).hits()) {
            checksum += hit.document().id();
            checksum += Double.doubleToLongBits(hit.score());
        }
        return checksum;
    }

    @Benchmark
    public long highlightedTextSearch() {
        long checksum = 0;
        for (HighlightedSearchHit<Document> hit :
                engine.search(highlightedRequest).hits()) {
            checksum += hit.hit().document().id();
            checksum += Double.doubleToLongBits(hit.hit().score());
            for (FieldHighlight field : hit.highlights()) {
                checksum += field.fieldName().length();
                for (HighlightFragment fragment : field.fragments()) {
                    checksum += fragment.startOffset();
                    checksum += fragment.endOffset();
                    checksum += fragment.text().length();
                    checksum += fragment.spans().size();
                }
            }
        }
        return checksum;
    }

    private record Document(int id, String body) {
    }
}
