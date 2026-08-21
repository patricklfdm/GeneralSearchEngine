package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SnapshotUpdateEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.model.ProductFields;
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

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class DynamicIndexBuildBenchmark {
    @Param("10000")
    public int productCount;

    private SnapshotUpdateEngine engine;

    @Setup(Level.Trial)
    public void setUp() {
        engine = new SnapshotUpdateEngine();
        ProductBenchmarkData.load(engine, productCount);
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public void buildAndDropRangeIndex() {
        engine.createIndex(IndexDefinition.range(ProductFields.RATING)).join();
        engine.dropIndex(ProductFields.RATING.name()).join();
    }

    @Benchmark
    public void buildAndDropEqualityIndex() {
        engine.createIndex(IndexDefinition.equality(ProductFields.RATING)).join();
        engine.dropIndex(ProductFields.RATING.name()).join();
    }
}
