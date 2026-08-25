package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.SnapshotSearcher;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
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

/** Compares conservative AND planning under different child correlations. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class AndPlannerBenchmark {
    private static final Field<CorrelatedDocument, Integer> VALUE =
            Field.of("value", Integer.class, CorrelatedDocument::value);
    private static final Field<CorrelatedDocument, Boolean> FLAG =
            Field.of("flag", Boolean.class, CorrelatedDocument::flag);

    @Param("100000")
    public int documentCount;

    @Param({"POSITIVE", "NEGATIVE", "INDEPENDENT"})
    public String correlation;

    private final SnapshotSearcher<CorrelatedDocument> searcher =
            new SnapshotSearcher<>();
    private SearchSnapshot<CorrelatedDocument> indexed;
    private SearchSnapshot<CorrelatedDocument> scanned;
    private Query<CorrelatedDocument> query;

    @Setup(Level.Trial)
    public void setUp() {
        int rangeMatches = documentCount / 10;
        indexed = new SearchSnapshot<>(List.of(
                IndexDefinition.range(VALUE),
                IndexDefinition.equality(FLAG)
        ));
        scanned = new SearchSnapshot<>(List.of());
        for (int docId = 0; docId < documentCount; docId++) {
            CorrelatedDocument document = new CorrelatedDocument(
                    docId,
                    flag(docId, documentCount, correlation)
            );
            indexed = indexed.add(docId, document);
            scanned = scanned.add(docId, document);
        }
        query = Query.and(
                Query.between(VALUE, 0, rangeMatches - 1),
                Query.eq(FLAG, true)
        );
        if (!searcher.search(indexed, query).equals(searcher.search(scanned, query))) {
            throw new IllegalStateException("planned AND differs from scan oracle");
        }
    }

    @Benchmark
    public int plannedAnd() {
        return searcher.search(indexed, query).size();
    }

    @Benchmark
    public int scannedAnd() {
        return searcher.search(scanned, query).size();
    }

    private static boolean flag(int docId, int count, String correlation) {
        return switch (correlation) {
            case "POSITIVE" -> docId < count / 10;
            case "NEGATIVE" -> docId >= count - count / 10;
            case "INDEPENDENT" -> docId % 10 == 0;
            default -> throw new IllegalArgumentException(
                    "unknown correlation: " + correlation);
        };
    }

    private record CorrelatedDocument(int value, boolean flag) {}
}
