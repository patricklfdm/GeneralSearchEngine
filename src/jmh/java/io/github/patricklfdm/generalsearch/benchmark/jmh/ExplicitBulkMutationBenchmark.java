package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletionException;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
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

/** Measures one explicit atomic publication at several collection sizes. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class ExplicitBulkMutationBenchmark {
    private static final Field<MutableDocument, Integer> ID =
            Field.of("id", Integer.class, MutableDocument::id);
    private static final Field<MutableDocument, Integer> VALUE =
            Field.of("value", Integer.class, MutableDocument::value);

    @Param({"1", "10", "100", "1000"})
    public int batchSize;

    private SearchEngine<Integer, MutableDocument> engine;
    private List<MutableDocument> low;
    private List<MutableDocument> high;
    private List<MutableDocument> invalid;
    private boolean highPublished;
    private long versionBefore;
    private int expectedVersionDelta;
    private MutableDocument documentBefore;

    @Setup(Level.Trial)
    public void setUp() {
        engine = SearchEngine.builder(MutableDocument.class, ID)
                .index(IndexDefinition.range(VALUE))
                .config(new SnapshotEngineConfig(
                        10_000,
                        1_000,
                        Duration.ZERO))
                .build();
        low = new ArrayList<>(batchSize);
        high = new ArrayList<>(batchSize);
        invalid = new ArrayList<>(batchSize);
        for (int id = 0; id < batchSize; id++) {
            low.add(new MutableDocument(id, id));
            high.add(new MutableDocument(id, 1_000_000 + id));
            invalid.add(new MutableDocument(id, 2_000_000 + id));
        }
        invalid.set(batchSize - 1,
                new MutableDocument(batchSize + 10_000, 2_000_000));
        engine.addAll(low).join();
    }

    @Setup(Level.Invocation)
    public void captureVersion() {
        versionBefore = engine.metrics().snapshotVersion();
        documentBefore = engine.get(0);
        expectedVersionDelta = -1;
    }

    @Benchmark
    public long updateAndPublishAtomicBulk() {
        engine.updateAll(highPublished ? low : high).join();
        highPublished = !highPublished;
        expectedVersionDelta = 1;
        return engine.metrics().snapshotVersion();
    }

    @Benchmark
    public long rejectInvalidAtomicBulk() {
        try {
            engine.updateAll(invalid).join();
            throw new IllegalStateException("invalid atomic bulk unexpectedly succeeded");
        } catch (CompletionException expected) {
            expectedVersionDelta = 0;
            return engine.metrics().snapshotVersion();
        }
    }

    @TearDown(Level.Invocation)
    public void verifySinglePublication() {
        long versionAfter = engine.metrics().snapshotVersion();
        if (expectedVersionDelta < 0
                || versionAfter != versionBefore + expectedVersionDelta) {
            throw new IllegalStateException(
                    "unexpected publication count, observed version "
                            + versionBefore + " -> " + versionAfter);
        }
        if (expectedVersionDelta == 0 && !documentBefore.equals(engine.get(0))) {
            throw new IllegalStateException("invalid atomic bulk changed a document");
        }
    }

    @TearDown(Level.Trial)
    public void close() {
        engine.close();
    }

    private record MutableDocument(int id, int value) {}
}
