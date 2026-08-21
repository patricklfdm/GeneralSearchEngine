package org.example.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.example.generalsearch.engine.SnapshotEngineConfig;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OperationsPerInvocation;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Warmup;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class ProductMutationBenchmark {
    private static final int UPDATE_BATCH_SIZE = 100;

    @Param("10000")
    public int productCount;

    private SnapshotUpdateEngine engine;
    private int nextSlot;
    private long revision;

    @Setup(Level.Trial)
    public void setUp() {
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
    public void updateAndPublish() {
        engine.update(ProductBenchmarkData.product(nextSlot(), revision++)).join();
    }

    @Benchmark
    @OperationsPerInvocation(UPDATE_BATCH_SIZE)
    public void updateBatchAndPublish() {
        List<CompletableFuture<Void>> updates = new ArrayList<>(UPDATE_BATCH_SIZE);
        for (int update = 0; update < UPDATE_BATCH_SIZE; update++) {
            updates.add(engine.update(
                    ProductBenchmarkData.product(nextSlot(), revision++)));
        }
        CompletableFuture.allOf(updates.toArray(CompletableFuture[]::new)).join();
    }

    private int nextSlot() {
        int slot = nextSlot;
        nextSlot = (nextSlot + 1) % productCount;
        return slot;
    }
}
