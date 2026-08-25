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

/** Holds result selectivity constant while varying matched Range value buckets. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class RangeBucketSpreadBenchmark {
    private static final Field<BucketDocument, Integer> VALUE =
            Field.of("value", Integer.class, BucketDocument::value);

    @Param("100000")
    public int documentCount;

    @Param({"100", "10000", "100000"})
    public int distinctValueCount;

    @Param({"1.0", "25.0"})
    public double selectivityPercent;

    private EstimatingIndexSnapshot<BucketDocument> index;
    private Query<BucketDocument> query;

    @Setup(Level.Trial)
    public void setUp() {
        if (documentCount <= 0
                || distinctValueCount <= 0
                || documentCount % distinctValueCount != 0) {
            throw new IllegalArgumentException(
                    "distinctValueCount must evenly divide documentCount");
        }
        int matchedBuckets = Math.max(1, (int) Math.round(
                distinctValueCount * selectivityPercent / 100.0));
        int expectedMatches = Math.toIntExact(
                (long) matchedBuckets * documentCount / distinctValueCount
        );

        IndexBuilder<BucketDocument> builder =
                IndexDefinition.range(VALUE).createEmpty().toBuilder();
        for (int docId = 0; docId < documentCount; docId++) {
            int value = (int) ((long) docId * distinctValueCount / documentCount);
            builder.add(docId, new BucketDocument(value));
        }
        index = estimating(builder.build());
        query = Query.between(VALUE, 0, matchedBuckets - 1);

        CandidateEstimate estimate = index.estimateCandidates(query).orElseThrow();
        CandidateResult candidates = index.candidates(query).orElseThrow();
        if (estimate.estimatedCandidateCardinality() != expectedMatches
                || estimate.estimatedSourceCount() != matchedBuckets
                || candidates.bitmap().cardinality() != expectedMatches) {
            throw new IllegalStateException(
                    "bucket-spread setup cardinality mismatch: expectedMatches="
                            + expectedMatches
                            + ", expectedSources=" + matchedBuckets
                            + ", estimatedMatches="
                            + estimate.estimatedCandidateCardinality()
                            + ", estimatedSources="
                            + estimate.estimatedSourceCount()
                            + ", materializedMatches="
                            + candidates.bitmap().cardinality()
            );
        }
    }

    @Benchmark
    public CandidateEstimate estimate() {
        return index.estimateCandidates(query).orElseThrow();
    }

    @Benchmark
    public CandidateResult materialize() {
        return index.candidates(query).orElseThrow();
    }

    @SuppressWarnings("unchecked")
    private static EstimatingIndexSnapshot<BucketDocument> estimating(
            IndexSnapshot<BucketDocument> snapshot
    ) {
        if (!(snapshot instanceof EstimatingIndexSnapshot<?> estimating)) {
            throw new IllegalStateException("Range index must expose estimates");
        }
        return (EstimatingIndexSnapshot<BucketDocument>) estimating;
    }

    private record BucketDocument(int value) {}
}
