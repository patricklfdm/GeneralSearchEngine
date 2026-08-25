package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
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

/** Measures path-copied text dictionary publication across vocabulary sizes. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class TextIndexPublicationBenchmark {
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);
    private static final TextField<TextDocument> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param({"10000", "100000"})
    public int vocabularySize;

    @Param({"1", "10", "100", "1000"})
    public int mutationBatchSize;

    private TextDocument[] original;
    private TextDocument[] replacement;
    private TextIndexSnapshot<TextDocument> current;
    private boolean replacementsPublished;

    @Setup(Level.Trial)
    public void setUp() {
        if (mutationBatchSize > vocabularySize) {
            throw new IllegalArgumentException(
                    "mutationBatchSize must not exceed vocabularySize");
        }
        original = new TextDocument[vocabularySize];
        replacement = new TextDocument[vocabularySize];
        IndexBuilder<TextDocument> builder = IndexDefinition.text(TEXT)
                .createEmpty()
                .toBuilder();
        for (int docId = 0; docId < vocabularySize; docId++) {
            original[docId] = new TextDocument("stable token" + docId);
            replacement[docId] = new TextDocument("stable replacement" + docId);
            builder.add(docId, original[docId]);
        }
        current = textIndex(builder.build());
    }

    @Benchmark
    public int publishTextMutationBatch() {
        IndexBuilder<TextDocument> builder = current.toBuilder();
        TextDocument[] oldDocuments = replacementsPublished ? replacement : original;
        TextDocument[] newDocuments = replacementsPublished ? original : replacement;
        for (int docId = 0; docId < mutationBatchSize; docId++) {
            builder.update(docId, oldDocuments[docId], newDocuments[docId]);
        }
        current = textIndex(builder.build());
        replacementsPublished = !replacementsPublished;
        return current.statistics().distinctKeyCount();
    }

    @SuppressWarnings("unchecked")
    private static TextIndexSnapshot<TextDocument> textIndex(Object index) {
        return (TextIndexSnapshot<TextDocument>) index;
    }

    private record TextDocument(String body) {}
}
