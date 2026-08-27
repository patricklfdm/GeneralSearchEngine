package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
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

/** Measures V3 query scaling across controlled document and corpus shapes. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V3ScaleAndCorpusBenchmark {
    @Param("10000")
    public int documentCount;

    @Param("10")
    public int topK;

    @Param("uniform-en-short-1")
    public String corpusProfile;

    @Param({"TEXT", "BOOL", "PHRASE", "FUZZY"})
    public String queryType;

    private V3ProductionBenchmarkSupport.Fixture fixture;
    private SearchRequest<V3ProductionBenchmarkSupport.Document> request;

    @Setup(Level.Trial)
    public void setUp() {
        fixture = V3ProductionBenchmarkSupport.createFixture(
                documentCount,
                corpusProfile);
        request = V3ProductionBenchmarkSupport.requestFor(
                fixture,
                queryType,
                topK);
        if (fixture.engine().search(request).hits().isEmpty()) {
            throw new IllegalStateException(
                    "benchmark control query produced no hits: " + queryType);
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        fixture.close();
    }

    @Benchmark
    public double search() {
        var hits = fixture.engine().search(request).hits();
        return hits.getFirst().score() + hits.size();
    }
}
