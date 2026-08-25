package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.RankedSearcher;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;
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

/** Compares bounded BM25 top-K retention with an exhaustive full-sort control. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class Bm25TopKBenchmark {
    private static final Field<TextDocument, String> BODY =
            Field.of("body", String.class, TextDocument::body);
    private static final Field<TextDocument, String> CATEGORY =
            Field.of("category", String.class, TextDocument::category);
    private static final TextField<TextDocument> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param("100000")
    public int documentCount;

    @Param({"0.1", "10.0", "50.0"})
    public double documentFrequencyPercent;

    @Param({"1", "10", "100", "100000"})
    public int topK;

    @Param({"NONE", "CATEGORY_10"})
    public String filterMode;

    private final RankedSearcher<TextDocument> searcher = new RankedSearcher<>();
    private SearchSnapshot<TextDocument> snapshot;
    private TextIndexSnapshot<TextDocument> textIndex;
    private RankedSearchRequest<TextDocument> request;
    private Query<TextDocument> filter;

    @Setup(Level.Trial)
    public void setUp() {
        int selectedCount = Math.max(
                1,
                (int) Math.round(documentCount * documentFrequencyPercent / 100.0));
        SearchSnapshotBuilder<TextDocument> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TEXT),
                        IndexDefinition.equality(CATEGORY))));
        for (int docId = 0; docId < documentCount; docId++) {
            StringBuilder body = new StringBuilder("stable token").append(docId);
            if (docId < selectedCount) {
                int repetitions = 1 + docId % 3;
                for (int repetition = 0; repetition < repetitions; repetition++) {
                    body.append(" target");
                }
            }
            TextDocument document = new TextDocument(
                    docId,
                    body.toString(),
                    docId % 10 == 0 ? "eligible" : "other");
            builder.add(docId, document);
        }
        snapshot = builder.build();
        @SuppressWarnings("unchecked")
        TextIndexSnapshot<TextDocument> builtIndex =
                (TextIndexSnapshot<TextDocument>) snapshot.indexes().indexes().stream()
                        .filter(TextIndexSnapshot.class::isInstance)
                        .findFirst()
                        .orElseThrow();
        textIndex = builtIndex;
        TextScoringQuery<TextDocument> scoring = TextScoringQuery.of(TEXT, "target");
        if ("NONE".equals(filterMode)) {
            filter = null;
            request = RankedSearchRequest.of(scoring, topK);
        } else if ("CATEGORY_10".equals(filterMode)) {
            filter = Query.eq(CATEGORY, "eligible");
            request = RankedSearchRequest.filtered(scoring, filter, topK);
        } else {
            throw new IllegalArgumentException("unknown filterMode: " + filterMode);
        }

        List<SearchHit<TextDocument>> bounded = searcher.search(snapshot, request);
        List<ControlHit> exhaustive = exhaustive();
        if (bounded.size() != exhaustive.size()) {
            throw new IllegalStateException("bounded and exhaustive result sizes differ");
        }
        for (int hit = 0; hit < bounded.size(); hit++) {
            if (bounded.get(hit).document().id() != exhaustive.get(hit).docId()
                    || Math.abs(bounded.get(hit).score() - exhaustive.get(hit).score())
                    > 1.0e-12) {
                throw new IllegalStateException("bounded result differs at hit " + hit);
            }
        }
    }

    @Benchmark
    public double boundedTopK() {
        List<SearchHit<TextDocument>> hits = searcher.search(snapshot, request);
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    @Benchmark
    public double exhaustiveFullSort() {
        List<ControlHit> hits = exhaustive();
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    private List<ControlHit> exhaustive() {
        PostingList posting = textIndex.posting("target");
        int indexedDocuments = textIndex.statistics().indexedDocumentCount();
        double averageLength = textIndex.averageDocumentLength();
        double idf = Math.log1p(
                (indexedDocuments - posting.documentFrequency() + 0.5)
                        / (posting.documentFrequency() + 0.5));
        List<ControlHit> hits = new ArrayList<>(posting.documentFrequency());
        posting.documents().forEachSetBit(docId -> {
            TextDocument document = snapshot.get(docId);
            if (filter != null && !filter.matches(document)) {
                return;
            }
            int tf = posting.termFrequency(docId);
            int length = textIndex.documentLength(docId);
            double normalization = Bm25Config.DEFAULT.k1() * (
                    1.0 - Bm25Config.DEFAULT.b()
                            + Bm25Config.DEFAULT.b() * length / averageLength);
            double score = idf * (tf * (Bm25Config.DEFAULT.k1() + 1.0))
                    / (tf + normalization);
            hits.add(new ControlHit(docId, score));
        });
        hits.sort(Comparator.comparingDouble(ControlHit::score)
                .reversed()
                .thenComparingInt(ControlHit::docId));
        return List.copyOf(hits.subList(0, Math.min(topK, hits.size())));
    }

    private record TextDocument(int id, String body, String category) {}

    private record ControlHit(int docId, double score) {}
}
