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

/** V3.1 feature-lane initial build and dictionary-membership publication costs. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V31TextDictionaryBenchmark {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param({"100000", "1000000"})
    public int vocabularySize;

    @Param({"1", "100"})
    public int mutationBatchSize;

    @Param({"unchanged", "added", "removed"})
    public String transition;

    private TextIndexSnapshot<Document> base;
    private Document[] oldDocuments;
    private Document[] newDocuments;

    @Setup(Level.Trial)
    public void setUp() {
        if (mutationBatchSize > vocabularySize) {
            throw new IllegalArgumentException(
                    "mutationBatchSize must not exceed vocabularySize");
        }
        IndexBuilder<Document> builder = IndexDefinition.text(BODY_TEXT)
                .createEmpty()
                .toBuilder();
        oldDocuments = new Document[mutationBatchSize];
        newDocuments = new Document[mutationBatchSize];
        for (int documentId = 0; documentId < vocabularySize; documentId++) {
            Document original = original(documentId);
            builder.add(documentId, original);
            if (documentId < mutationBatchSize) {
                oldDocuments[documentId] = original;
                newDocuments[documentId] = replacement(documentId);
            }
        }
        base = textIndex(builder.build());
        int expectedDelta = switch (transition) {
            case "unchanged" -> 0;
            case "added" -> mutationBatchSize;
            case "removed" -> -mutationBatchSize;
            default -> throw new IllegalArgumentException(
                    "unknown membership transition: " + transition);
        };
        int before = base.statistics().distinctKeyCount();
        int after = publish();
        if (after != before + expectedDelta) {
            throw new IllegalStateException(
                    "unexpected dictionary-membership transition");
        }
    }

    @Benchmark
    public int build() {
        IndexBuilder<Document> builder = IndexDefinition.text(BODY_TEXT)
                .createEmpty()
                .toBuilder();
        for (int documentId = 0; documentId < vocabularySize; documentId++) {
            builder.add(documentId, new Document("token" + documentId, 0));
        }
        return textIndex(builder.build()).statistics().distinctKeyCount();
    }

    @Benchmark
    public int publish() {
        IndexBuilder<Document> builder = base.toBuilder();
        for (int documentId = 0; documentId < mutationBatchSize; documentId++) {
            builder.update(
                    documentId,
                    oldDocuments[documentId],
                    newDocuments[documentId]
            );
        }
        return textIndex(builder.build()).statistics().distinctKeyCount();
    }

    private Document original(int documentId) {
        return switch (transition) {
            case "unchanged", "added" ->
                    new Document("stable token" + documentId, 0);
            case "removed" ->
                    new Document("stable removable" + documentId, 0);
            default -> throw new IllegalArgumentException(
                    "unknown membership transition: " + transition);
        };
    }

    private Document replacement(int documentId) {
        return switch (transition) {
            case "unchanged" ->
                    new Document("stable token" + documentId, 1);
            case "added" ->
                    new Document("stable token" + documentId + " added" + documentId, 1);
            case "removed" -> new Document("stable", 1);
            default -> throw new IllegalArgumentException(
                    "unknown membership transition: " + transition);
        };
    }

    @SuppressWarnings("unchecked")
    private static TextIndexSnapshot<Document> textIndex(Object value) {
        return (TextIndexSnapshot<Document>) value;
    }

    private record Document(String body, int revision) {
    }
}
