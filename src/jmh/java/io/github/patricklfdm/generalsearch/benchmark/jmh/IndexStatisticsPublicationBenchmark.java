package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
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

/** Measures index publication with the same document count and different key counts. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class IndexStatisticsPublicationBenchmark {
    private static final Field<MetricDocument, Integer> VALUE =
            Field.of("value", Integer.class, MetricDocument::value);

    @Param("10000")
    public int documentCount;

    @Param({"100", "10000"})
    public int distinctKeyCount;

    private EstimatingIndexSnapshot<MetricDocument> index;
    private MetricDocument first;
    private MetricDocument second;

    @Setup(Level.Trial)
    public void setUp() {
        if (distinctKeyCount < 2 || distinctKeyCount > documentCount) {
            throw new IllegalArgumentException(
                    "distinctKeyCount must be between 2 and documentCount");
        }
        IndexBuilder<MetricDocument> builder =
                IndexDefinition.range(VALUE).createEmpty().toBuilder();
        for (int docId = 0; docId < documentCount; docId++) {
            builder.add(docId, new MetricDocument(docId % distinctKeyCount));
        }
        index = estimating(builder.build());
        first = new MetricDocument(0);
        second = new MetricDocument(1);
        assertStatistics();
    }

    @Benchmark
    public IndexStatistics swapTwoValuesAndPublish() {
        IndexBuilder<MetricDocument> builder = index.toBuilder();
        builder.update(0, first, second);
        builder.update(1, second, first);
        index = estimating(builder.build());

        MetricDocument swap = first;
        first = second;
        second = swap;
        assertStatistics();
        return index.statistics();
    }

    private void assertStatistics() {
        IndexStatistics statistics = index.statistics();
        if (statistics.indexedDocumentCount() != documentCount
                || statistics.distinctKeyCount() != distinctKeyCount) {
            throw new IllegalStateException(
                    "index statistics changed during publication benchmark: "
                            + statistics);
        }
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
