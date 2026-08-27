package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Group;
import org.openjdk.jmh.annotations.GroupThreads;
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

/** Captures read and mutation tails under one shared immutable-snapshot engine. */
@BenchmarkMode({Mode.Throughput, Mode.SampleTime})
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
public class V3ConcurrentMixedWorkloadBenchmark {
    @State(Scope.Group)
    public static class SharedEngine {
        @Param("100000")
        public int documentCount;

        private V3ProductionBenchmarkSupport.Fixture fixture;
        private List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests;
        private final AtomicInteger nextMutation = new AtomicInteger();

        @Setup(Level.Trial)
        public void setUp() {
            fixture = V3ProductionBenchmarkSupport.createFixture(
                    documentCount,
                    "zipf-en-medium-4");
            requests = V3ProductionBenchmarkSupport.requests(fixture, 10);
            for (SearchRequest<V3ProductionBenchmarkSupport.Document> request
                    : requests) {
                if (fixture.engine().search(request).hits().isEmpty()) {
                    throw new IllegalStateException(
                            "concurrent benchmark control query produced no hits");
                }
            }
        }

        @TearDown(Level.Trial)
        public void tearDown() {
            fixture.close();
        }
    }

    @State(Scope.Thread)
    public static class ReaderCursor {
        private int nextQuery;
    }

    @Benchmark
    @Group("mixed")
    @GroupThreads(4)
    public double read(SharedEngine shared, ReaderCursor cursor) {
        SearchRequest<V3ProductionBenchmarkSupport.Document> request =
                shared.requests.get(Math.floorMod(
                        cursor.nextQuery++, shared.requests.size()));
        var hits = shared.fixture.engine().search(request).hits();
        return hits.getFirst().score() + hits.size();
    }

    @Benchmark
    @Group("mixed")
    @GroupThreads(1)
    public long write(SharedEngine shared) {
        int sequence = shared.nextMutation.getAndIncrement();
        long id = Math.floorMod(sequence, shared.documentCount);
        int revision = sequence / shared.documentCount + 1;
        var replacement = V3ProductionBenchmarkSupport.replacement(
                id,
                revision,
                shared.fixture.profile());
        shared.fixture.engine().update(replacement).join();
        return shared.fixture.engine().metrics().snapshotVersion();
    }
}
