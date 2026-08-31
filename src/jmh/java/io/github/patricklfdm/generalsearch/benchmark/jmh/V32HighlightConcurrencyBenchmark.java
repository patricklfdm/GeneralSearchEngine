package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
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

/** Phase 5 highlighted/ordinary/Explain readers with one progressing writer. */
@BenchmarkMode({Mode.Throughput, Mode.SampleTime})
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
public class V32HighlightConcurrencyBenchmark {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @State(Scope.Group)
    public static class SharedEngine {
        @Param("10000")
        public int documentCount;

        @Param("10")
        public int topK;

        private SearchEngine<Integer, Document> engine;
        private SearchRequest<Document> searchRequest;
        private HighlightedSearchRequest<Document> highlightedRequest;
        private final AtomicInteger nextMutation = new AtomicInteger();

        @Setup(Level.Trial)
        public void setUp() {
            engine = SearchEngine.builder(Document.class, ID)
                    .index(IndexDefinition.text(BODY_TEXT))
                    .build();
            List<Document> documents = new ArrayList<>(documentCount);
            for (int id = 0; id < documentCount; id++) {
                documents.add(document(id, 0));
            }
            for (int start = 0; start < documents.size(); start += 1_000) {
                engine.addAll(documents.subList(
                        start,
                        Math.min(start + 1_000, documents.size())
                )).join();
            }
            var query = SearchQueries.<Document>bool()
                    .must(SearchQueries.text(BODY_TEXT, "stable"))
                    .should(SearchQueries.phrase(
                            BODY_TEXT, "stable revision"))
                    .should(SearchQueries.fuzzy(BODY_TEXT, "stble"))
                    .minimumShouldMatch(1)
                    .build()
                    .boost(1.5);
            searchRequest = SearchRequest.<Document>builder()
                    .query(query)
                    .limit(topK)
                    .build();
            highlightedRequest = HighlightedSearchRequest
                    .<Document>builder(searchRequest)
                    .field(BODY_TEXT)
                    .contextCharacters(40)
                    .maxFragmentsPerField(3)
                    .build();
            if (engine.search(searchRequest).hits().size() != topK
                    || engine.search(highlightedRequest).hits().size() != topK) {
                throw new IllegalStateException(
                        "invalid concurrency control cardinality");
            }
        }

        @TearDown(Level.Trial)
        public void tearDown() {
            try {
                if (engine.metrics().writerQueueDepth() != 0) {
                    throw new IllegalStateException(
                            "writer queue did not drain after Phase 5 benchmark");
                }
            } finally {
                engine.close();
            }
        }
    }

    @State(Scope.Thread)
    public static class ReaderCursor {
        private int nextId;
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
    @GroupThreads(4)
    public long highlighted(SharedEngine shared) {
        long checksum = 0;
        var result = shared.engine.search(shared.highlightedRequest);
        for (var hit : result.hits()) {
            checksum += hit.hit().document().id();
            checksum += Double.doubleToLongBits(hit.hit().score());
            checksum += hit.highlights().stream()
                    .mapToInt(field -> field.fragments().stream()
                            .mapToInt(fragment -> fragment.spans().size())
                            .sum())
                    .sum();
        }
        return checksum;
    }

    @Benchmark
    @Group("mixed")
    @GroupThreads(4)
    public long ordinary(SharedEngine shared) {
        long checksum = 0;
        for (var hit : shared.engine.search(shared.searchRequest).hits()) {
            checksum += hit.document().id();
            checksum += Double.doubleToLongBits(hit.score());
        }
        return checksum;
    }

    @Benchmark
    @Group("mixed")
    @GroupThreads(1)
    public double explain(SharedEngine shared, ReaderCursor cursor) {
        int id = Math.floorMod(cursor.nextId++, shared.documentCount);
        var explanation = shared.engine.explain(shared.searchRequest, id)
                .orElseThrow();
        return explanation.score() + (explanation.matched() ? 1.0 : 0.0);
    }

    @Benchmark
    @Group("mixed")
    @GroupThreads(1)
    public long write(SharedEngine shared, WriterEvidence evidence) {
        int sequence = shared.nextMutation.getAndIncrement();
        int id = Math.floorMod(sequence, shared.documentCount);
        int revision = sequence / shared.documentCount + 1;
        shared.engine.update(document(id, revision)).join();
        int depth = shared.engine.metrics().writerQueueDepth();
        evidence.writerQueueMaximum = Math.max(
                evidence.writerQueueMaximum,
                depth
        );
        if (depth != 0) {
            evidence.writerQueueNonzeroSamples++;
        }
        evidence.snapshotPublications++;
        return shared.engine.metrics().snapshotVersion();
    }

    private static Document document(int id, int revision) {
        return new Document(
                id,
                "stable revision " + revision + " document " + id
                        + (revision % 2 == 0 ? " alpha" : " beta")
        );
    }

    private record Document(int id, String body) {
    }
}
