package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
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
import org.openjdk.jmh.annotations.Warmup;

/** Measures positional posting construction and position-sensitive publication. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class PositionalTextIndexBenchmark {
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);

    @Param("10000")
    public int documentCount;

    @Param("16")
    public int tokenCount;

    @Param({"1", "100"})
    public int mutationBatchSize;

    @Param({"default-adapter", "native-positioned"})
    public String analysisMode;

    private TextField<TextDocument> textField;
    private List<TextDocument> documents;
    private List<TextDocument> reordered;
    private TextIndexSnapshot<TextDocument> base;

    @Setup(Level.Trial)
    public void setUp() {
        Analyzer analyzer = switch (analysisMode) {
            case "default-adapter" -> Analyzer.simple();
            case "native-positioned" -> nativePositionedAnalyzer();
            default -> throw new IllegalArgumentException(
                    "unknown analysisMode: " + analysisMode);
        };
        textField = TextField.of(BODY, analyzer);
        documents = new ArrayList<>(documentCount);
        reordered = new ArrayList<>(mutationBatchSize);
        IndexBuilder<TextDocument> builder = IndexDefinition.text(textField)
                .createEmpty()
                .toBuilder();
        for (int docId = 0; docId < documentCount; docId++) {
            List<String> terms = new ArrayList<>(tokenCount);
            for (int token = 0; token < tokenCount; token++) {
                terms.add("term" + Math.floorMod(docId * 31 + token * 17, 10_000));
            }
            TextDocument document = new TextDocument(String.join(" ", terms));
            documents.add(document);
            builder.add(docId, document);
            if (docId < mutationBatchSize) {
                Collections.reverse(terms);
                reordered.add(new TextDocument(String.join(" ", terms)));
            }
        }
        base = textIndex(builder.build());
    }

    @Benchmark
    public long buildPositionalTextIndex() {
        IndexBuilder<TextDocument> builder = IndexDefinition.text(textField)
                .createEmpty()
                .toBuilder();
        for (int docId = 0; docId < documents.size(); docId++) {
            builder.add(docId, documents.get(docId));
        }
        TextIndexSnapshot<TextDocument> index = textIndex(builder.build());
        return index.totalDocumentLength();
    }

    @Benchmark
    public long publishPositionSensitiveMutationBatch() {
        IndexBuilder<TextDocument> builder = base.toBuilder();
        for (int docId = 0; docId < mutationBatchSize; docId++) {
            builder.update(docId, documents.get(docId), reordered.get(docId));
        }
        return textIndex(builder.build()).totalDocumentLength();
    }

    private static Analyzer nativePositionedAnalyzer() {
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
                    int increment = index == 0 ? 2 : index % 5 == 0 ? 0 : 1;
                    positioned.add(new AnalyzedToken(terms.get(index).term(), increment));
                }
                return List.copyOf(positioned);
            }
        };
    }

    @SuppressWarnings("unchecked")
    private static TextIndexSnapshot<TextDocument> textIndex(Object index) {
        return (TextIndexSnapshot<TextDocument>) index;
    }

    private record TextDocument(String body) {}
}
