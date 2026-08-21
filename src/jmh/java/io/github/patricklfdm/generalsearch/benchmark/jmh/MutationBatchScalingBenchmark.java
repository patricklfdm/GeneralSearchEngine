package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.engine.SnapshotUpdateEngine;
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

/**
 * Measures total batch latency while verifying that each invocation publishes once.
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class MutationBatchScalingBenchmark {
    @Param("100000")
    public int productCount;

    @Param({"1", "10", "100", "1000"})
    public int batchSize;

    private SnapshotUpdateEngine engine;
    private int nextSlot;
    private long revision;

    @Setup(Level.Trial)
    public void setUp() {
        if (productCount < batchSize) {
            throw new IllegalArgumentException(
                    "productCount must be at least batchSize");
        }
        engine = new SnapshotUpdateEngine(SnapshotEngineConfig.DEFAULT);
        ProductBenchmarkData.load(engine, productCount);
        nextSlot = 0;
        revision = 1;
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public int updateBatchAndPublish() {
        long versionBefore = engine.metrics().snapshotVersion();
        List<CompletableFuture<Void>> updates = new ArrayList<>(batchSize);
        for (int update = 0; update < batchSize; update++) {
            updates.add(engine.update(
                    ProductBenchmarkData.product(nextSlot(), revision++)));
        }
        CompletableFuture.allOf(updates.toArray(CompletableFuture[]::new)).join();
        long publications = engine.metrics().snapshotVersion() - versionBefore;
        if (publications != 1) {
            throw new IllegalStateException(
                    "expected one snapshot publication, observed " + publications
                            + " for batchSize=" + batchSize);
        }
        return batchSize;
    }

    private int nextSlot() {
        int slot = nextSlot;
        nextSlot = (nextSlot + 1) % productCount;
        return slot;
    }
}
