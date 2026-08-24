package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.Query;
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
import org.openjdk.jmh.annotations.Warmup;

/** Separates range estimate cost from candidate bitmap materialization cost. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class RangeEstimateBenchmark {
    private static final Field<MetricDocument, Integer> VALUE =
            Field.of("value", Integer.class, MetricDocument::value);

    @Param("100000")
    public int documentCount;

    @Param({"0.01", "0.1", "1.0", "10.0", "25.0", "50.0", "100.0"})
    public double selectivityPercent;

    private EstimatingIndexSnapshot<MetricDocument> index;
    private Query<MetricDocument> query;

    @Setup(Level.Trial)
    public void setUp() {
        if (documentCount <= 0) {
            throw new IllegalArgumentException("documentCount must be positive");
        }
        if (selectivityPercent <= 0.0 || selectivityPercent > 100.0) {
            throw new IllegalArgumentException(
                    "selectivityPercent must be in (0, 100]");
        }

        IndexBuilder<MetricDocument> builder =
                IndexDefinition.range(VALUE).createEmpty().toBuilder();
        for (int docId = 0; docId < documentCount; docId++) {
            builder.add(docId, new MetricDocument(docId));
        }
        index = estimating(builder.build());

        int expectedMatches = Math.max(
                1,
                (int) Math.round(documentCount * selectivityPercent / 100.0)
        );
        query = Query.between(VALUE, 0, expectedMatches - 1);

        CandidateEstimate estimate = index.estimateCandidates(query).orElseThrow();
        CandidateResult candidates = index.candidates(query).orElseThrow();
        if (estimate.estimatedCandidateCardinality() != expectedMatches
                || estimate.estimatedSourceCount() != expectedMatches
                || candidates.bitmap().cardinality() != expectedMatches) {
            throw new IllegalStateException(
                    "range estimate setup produced an unexpected cardinality");
        }
    }

    @Benchmark
    public CandidateEstimate estimateRangeCandidates() {
        return index.estimateCandidates(query).orElseThrow();
    }

    @Benchmark
    public CandidateResult materializeRangeCandidates() {
        return index.candidates(query).orElseThrow();
    }

    @SuppressWarnings("unchecked")
    private static EstimatingIndexSnapshot<MetricDocument> estimating(
            IndexSnapshot<MetricDocument> snapshot
    ) {
        if (!(snapshot instanceof EstimatingIndexSnapshot<?> estimating)) {
            throw new IllegalStateException("built-in Range index must support estimates");
        }
        return (EstimatingIndexSnapshot<MetricDocument>) estimating;
    }

    private record MetricDocument(int value) {}
}
