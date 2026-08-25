package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.SnapshotSearcher;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
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

/** Compares one analyzed term through the inverted index and exhaustive scan. */
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class TextTermQueryBenchmark {
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);
    private static final TextField<TextDocument> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("100000")
    public int documentCount;

    @Param({"0.01", "0.1", "1.0", "10.0", "25.0", "50.0", "100.0"})
    public double documentFrequencyPercent;

    private final SnapshotSearcher<TextDocument> searcher = new SnapshotSearcher<>();
    private SearchSnapshot<TextDocument> indexed;
    private SearchSnapshot<TextDocument> scanned;
    private TextIndexSnapshot<TextDocument> textIndex;
    private Query<TextDocument> query;
    private int expectedMatches;

    @Setup(Level.Trial)
    public void setUp() {
        if (documentCount <= 0 || documentCount > 1_000_000) {
            throw new IllegalArgumentException("documentCount must be in (0, 1000000]");
        }
        if (documentFrequencyPercent <= 0.0 || documentFrequencyPercent > 100.0) {
            throw new IllegalArgumentException(
                    "documentFrequencyPercent must be in (0, 100]");
        }
        expectedMatches = Math.max(
                1,
                (int) Math.round(documentCount * documentFrequencyPercent / 100.0));

        SearchSnapshotBuilder<TextDocument> indexedBuilder =
                new SearchSnapshotBuilder<>(new SearchSnapshot<>(
                        List.of(IndexDefinition.text(TEXT))));
        SearchSnapshotBuilder<TextDocument> scannedBuilder =
                new SearchSnapshotBuilder<>(new SearchSnapshot<>(List.of()));
        for (int docId = 0; docId < documentCount; docId++) {
            String selected = docId < expectedMatches ? " selected" : "";
            TextDocument document = new TextDocument(
                    docId,
                    "stable corpus token" + (docId % 10_000) + selected);
            indexedBuilder.add(docId, document);
            scannedBuilder.add(docId, document);
        }
        indexed = indexedBuilder.build();
        scanned = scannedBuilder.build();
        query = Query.term(TEXT, "SELECTED");
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<TextDocument> builtIndex =
                (TextIndexSnapshot<TextDocument>) indexed.indexes().indexes().getFirst();
        textIndex = builtIndex;

        verify("indexed", searcher.search(indexed, query).size());
        verify("scanned", searcher.search(scanned, query).size());
        verify("candidate", textIndex.candidates(query)
                .orElseThrow().bitmap().cardinality());
    }

    @Benchmark
    public int indexedTermSearch() {
        return searcher.search(indexed, query).size();
    }

    @Benchmark
    public int scannedTermSearch() {
        return searcher.search(scanned, query).size();
    }

    @Benchmark
    public int postingLookupOnly() {
        return textIndex.candidates(query).orElseThrow().bitmap().cardinality();
    }

    private void verify(String path, int actual) {
        if (actual != expectedMatches) {
            throw new IllegalStateException(
                    path + " produced " + actual + ", expected " + expectedMatches);
        }
    }

    private record TextDocument(int id, String body) {}
}
