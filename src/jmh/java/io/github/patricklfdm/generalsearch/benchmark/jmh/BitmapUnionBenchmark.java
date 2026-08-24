package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
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

/** Compares repeated immutable union with P2 single-freeze accumulation. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class BitmapUnionBenchmark {
    @Param("100000")
    public int documentCount;

    @Param({"0.01", "0.1", "1.0", "10.0", "25.0", "50.0", "100.0"})
    public double selectivityPercent;

    @Param({"1", "10", "100", "1000"})
    public int requestedSourceCount;

    @Param({"NONE", "DUPLICATED"})
    public String overlap;

    private List<ImmutableBitmap> sources;
    private int expectedCardinality;

    @Setup(Level.Trial)
    public void setUp() {
        expectedCardinality = Math.max(
                1,
                (int) Math.round(documentCount * selectivityPercent / 100.0)
        );
        int sourceCount = Math.min(requestedSourceCount, expectedCardinality);
        List<ImmutableBitmapBuilder> builders = new ArrayList<>(sourceCount);
        for (int source = 0; source < sourceCount; source++) {
            builders.add(new ImmutableBitmapBuilder(ImmutableBitmap.empty()));
        }
        for (int docId = 0; docId < expectedCardinality; docId++) {
            int source = docId % sourceCount;
            builders.get(source).set(docId);
            if ("DUPLICATED".equals(overlap) && sourceCount > 1) {
                builders.get((source + 1) % sourceCount).set(docId);
            }
        }
        sources = builders.stream().map(ImmutableBitmapBuilder::build).toList();
        verify(singleFreeze());
        verify(repeatedImmutableUnion());
    }

    @Benchmark
    public ImmutableBitmap repeatedImmutableUnion() {
        ImmutableBitmap result = ImmutableBitmap.empty();
        for (ImmutableBitmap source : sources) {
            result = result.or(source);
        }
        return result;
    }

    @Benchmark
    public ImmutableBitmap singleFreeze() {
        if (sources.size() == 1) {
            return sources.getFirst();
        }
        ImmutableBitmapBuilder result =
                new ImmutableBitmapBuilder(ImmutableBitmap.empty());
        for (ImmutableBitmap source : sources) {
            result.or(source);
        }
        return result.build();
    }

    private void verify(ImmutableBitmap bitmap) {
        if (bitmap.cardinality() != expectedCardinality) {
            throw new IllegalStateException(
                    "unexpected union cardinality: " + bitmap.cardinality());
        }
    }
}
