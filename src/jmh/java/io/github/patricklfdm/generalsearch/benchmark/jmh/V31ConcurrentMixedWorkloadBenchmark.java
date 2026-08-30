package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.openjdk.jmh.annotations.AuxCounters;
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

/** One-million-document V3.1 TEXT/PHRASE/FUZZY reader and single-writer lane. */
@BenchmarkMode({Mode.Throughput, Mode.SampleTime})
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
public class V31ConcurrentMixedWorkloadBenchmark {
    @State(Scope.Group)
    public static class SharedEngine {
        @Param("1000000")
        public int documentCount;

        private V3ProductionBenchmarkSupport.Fixture fixture;
        private List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests;
        private final AtomicInteger nextMutation = new AtomicInteger();

        @Setup(Level.Trial)
        public void setUp() {
            fixture = V3ProductionBenchmarkSupport.createFixture(
                    documentCount,
                    "zipf-en-medium-4"
            );
            requests = List.of(
                    SearchRequest.of(SearchQueries.text(
                            V3ProductionBenchmarkSupport.BODY_TEXT,
                            "search"
                    )),
                    SearchRequest.of(SearchQueries.phrase(
                            V3ProductionBenchmarkSupport.BODY_TEXT,
                            "search engine",
                            2
                    )),
                    SearchRequest.of(SearchQueries.fuzzy(
                            V3ProductionBenchmarkSupport.BODY_TEXT,
                            "serach"
                    ))
            );
            for (SearchRequest<V3ProductionBenchmarkSupport.Document> request
                    : requests) {
                if (fixture.engine().search(request).hits().isEmpty()) {
                    throw new IllegalStateException(
                            "V3.1 concurrency control query produced no hits");
                }
            }
        }

        @TearDown(Level.Trial)
        public void tearDown() {
            try {
                if (fixture.engine().metrics().writerQueueDepth() != 0) {
                    throw new IllegalStateException(
                            "writer queue did not drain after mixed benchmark");
                }
            } finally {
                fixture.close();
            }
        }
    }

    @State(Scope.Thread)
    public static class ReaderCursor {
        private int nextQuery;
    }

    @AuxCounters(AuxCounters.Type.EVENTS)
    @State(Scope.Thread)
    public static class WriterEvidence {
        public long writerQueueMaximum;
        public long writerQueueNonzeroSamples;
        public long snapshotPublications;

        @Setup(Level.Iteration)
        public void reset() {
            writerQueueMaximum = 0;
            writerQueueNonzeroSamples = 0;
            snapshotPublications = 0;
        }
    }

    @Benchmark
    @Group("mixed")
    @GroupThreads(16)
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
    public long write(SharedEngine shared, WriterEvidence evidence) {
        int sequence = shared.nextMutation.getAndIncrement();
        long id = Math.floorMod(sequence, shared.documentCount);
        int revision = sequence / shared.documentCount + 1;
        var replacement = V3ProductionBenchmarkSupport.replacement(
                id,
                revision,
                shared.fixture.profile()
        );
        var publication = shared.fixture.engine().update(replacement);
        int queueDepth = shared.fixture.engine().metrics().writerQueueDepth();
        evidence.writerQueueMaximum = Math.max(
                evidence.writerQueueMaximum,
                queueDepth
        );
        if (queueDepth != 0) {
            evidence.writerQueueNonzeroSamples++;
        }
        publication.join();
        evidence.snapshotPublications++;
        return shared.fixture.engine().metrics().snapshotVersion();
    }
}
