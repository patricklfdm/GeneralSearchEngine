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

/** Measures analyzed any/all matching as query token count grows. */
@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class TextMultiTermQueryBenchmark {
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);
    private static final TextField<TextDocument> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("100000")
    public int documentCount;

    @Param({"1", "4", "8"})
    public int queryTokenCount;

    private final SnapshotSearcher<TextDocument> searcher = new SnapshotSearcher<>();
    private SearchSnapshot<TextDocument> indexed;
    private SearchSnapshot<TextDocument> scanned;
    private TextIndexSnapshot<TextDocument> textIndex;
    private String queryText;
    private Query<TextDocument> anyQuery;
    private Query<TextDocument> allQuery;

    @Setup(Level.Trial)
    public void setUp() {
        if (queryTokenCount <= 0 || queryTokenCount > 16) {
            throw new IllegalArgumentException("queryTokenCount must be in (0, 16]");
        }
        SearchSnapshotBuilder<TextDocument> indexedBuilder =
                new SearchSnapshotBuilder<>(new SearchSnapshot<>(
                        List.of(IndexDefinition.text(TEXT))));
        SearchSnapshotBuilder<TextDocument> scannedBuilder =
                new SearchSnapshotBuilder<>(new SearchSnapshot<>(List.of()));
        for (int docId = 0; docId < documentCount; docId++) {
            StringBuilder body = new StringBuilder("stable unique").append(docId);
            for (int term = 0; term < 16; term++) {
                if (docId % (term + 2) == 0) {
                    body.append(' ').append("term").append(term);
                }
            }
            TextDocument document = new TextDocument(body.toString());
            indexedBuilder.add(docId, document);
            scannedBuilder.add(docId, document);
        }
        indexed = indexedBuilder.build();
        scanned = scannedBuilder.build();
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<TextDocument> builtIndex =
                (TextIndexSnapshot<TextDocument>) indexed.indexes().indexes().getFirst();
        textIndex = builtIndex;

        StringBuilder selectedTerms = new StringBuilder();
        for (int term = 0; term < queryTokenCount; term++) {
            if (!selectedTerms.isEmpty()) {
                selectedTerms.append(' ');
            }
            selectedTerms.append("term").append(term);
        }
        queryText = selectedTerms.toString();
        anyQuery = Query.anyTerms(TEXT, queryText);
        allQuery = Query.allTerms(TEXT, queryText);
        verifyEqual("any", anyQuery);
        verifyEqual("all", allQuery);
    }

    @Benchmark
    public int indexedAnyTerms() {
        return searcher.search(indexed, anyQuery).size();
    }

    @Benchmark
    public int scannedAnyTerms() {
        return searcher.search(scanned, anyQuery).size();
    }

    @Benchmark
    public int indexedAllTerms() {
        return searcher.search(indexed, allQuery).size();
    }

    @Benchmark
    public int scannedAllTerms() {
        return searcher.search(scanned, allQuery).size();
    }

    @Benchmark
    public int anyCandidateUnionOnly() {
        return textIndex.candidates(anyQuery).orElseThrow().bitmap().cardinality();
    }

    @Benchmark
    public int allCandidateIntersectionOnly() {
        return textIndex.candidates(allQuery).orElseThrow().bitmap().cardinality();
    }

    @Benchmark
    public int queryAnalysisOnly() {
        return TEXT.analyzer().analyze(queryText).size();
    }

    private void verifyEqual(String label, Query<TextDocument> query) {
        int indexedMatches = searcher.search(indexed, query).size();
        int scannedMatches = searcher.search(scanned, query).size();
        if (indexedMatches != scannedMatches) {
            throw new IllegalStateException(
                    label + " differs: indexed=" + indexedMatches
                            + ", scanned=" + scannedMatches);
        }
    }

    private record TextDocument(String body) {}
}
