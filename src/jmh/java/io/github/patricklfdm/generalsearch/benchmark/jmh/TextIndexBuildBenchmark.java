package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
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

/** Measures raw and lifecycle-integrated inverted-index construction. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class TextIndexBuildBenchmark {
    private static final Field<TextDocument, Integer> ID =
            Field.of("id", Integer.class, TextDocument::id);
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);
    private static final TextField<TextDocument> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    @Param({"4", "16"})
    public int averageTokenCount;

    @Param({"1000", "10000"})
    public int vocabularySize;

    private List<TextDocument> documents;
    private SearchEngine<Integer, TextDocument> engine;

    @Setup(Level.Trial)
    public void setUp() {
        documents = new ArrayList<>(documentCount);
        for (int docId = 0; docId < documentCount; docId++) {
            StringBuilder body = new StringBuilder();
            for (int token = 0; token < averageTokenCount; token++) {
                if (!body.isEmpty()) {
                    body.append(' ');
                }
                int term = Math.floorMod(docId * 31 + token * 17, vocabularySize);
                body.append("term").append(term);
            }
            documents.add(new TextDocument(docId, body.toString()));
        }

        engine = SearchEngine.builder(TextDocument.class, ID)
                .textField(TEXT)
                .build();
        List<CompletableFuture<Void>> pending = new ArrayList<>(1_000);
        for (TextDocument document : documents) {
            pending.add(engine.add(document));
            if (pending.size() == 1_000) {
                await(pending);
            }
        }
        await(pending);
    }

    @TearDown(Level.Invocation)
    public void dropDynamicIndex() {
        if (engine.metrics().registeredIndexCount() != 0) {
            engine.dropIndex(BODY.name()).join();
        }
    }

    @TearDown(Level.Trial)
    public void closeEngine() {
        engine.close();
    }

    @Benchmark
    public int buildRawTextIndex() {
        IndexBuilder<TextDocument> builder = IndexDefinition.text(TEXT)
                .createEmpty()
                .toBuilder();
        for (int docId = 0; docId < documents.size(); docId++) {
            builder.add(docId, documents.get(docId));
        }
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<TextDocument> index =
                (TextIndexSnapshot<TextDocument>) builder.build();
        return index.statistics().distinctKeyCount();
    }

    @Benchmark
    public int buildDynamicTextIndex() {
        engine.createIndex(IndexDefinition.text(TEXT)).join();
        return engine.metrics().registeredIndexCount();
    }

    private static void await(List<CompletableFuture<Void>> pending) {
        CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
        pending.clear();
    }

    private record TextDocument(int id, String body) {}
}
