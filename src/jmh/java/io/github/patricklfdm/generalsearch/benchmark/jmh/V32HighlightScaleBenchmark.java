package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.FieldHighlight;
import io.github.patricklfdm.generalsearch.search.HighlightFragment;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchHit;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
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

/** Phase 5 highlighted overhead scaling and requested-field outcome matrix. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V32HighlightScaleBenchmark {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> SUMMARY =
            Field.of("summary", String.class, Document::summary);
    private static final Field<Document, String> TAGS =
            Field.of("tags", String.class, Document::tags);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> SUMMARY_TEXT =
            TextField.of(SUMMARY, Analyzer.simple());
    private static final TextField<Document> TAGS_TEXT =
            TextField.of(TAGS, Analyzer.simple());

    @Param("10000")
    public int documentCount;

    @Param({"1", "10", "100"})
    public int topK;

    @Param({"1", "3"})
    public int requestedFieldCount;

    @Param({"16", "64", "256"})
    public int sourceTokenCount;

    @Param({"text", "phrase-exact", "phrase-sloppy", "fuzzy", "bool-boost"})
    public String queryKind;

    @Param({"highlighted", "unrelated", "no-hit"})
    public String outcome;

    @Param({"0", "40", "160"})
    public int contextCharacters;

    @Param({"1", "3", "10"})
    public int maxFragmentsPerField;

    private SearchEngine<Integer, Document> engine;
    private SearchRequest<Document> searchRequest;
    private HighlightedSearchRequest<Document> highlightedRequest;

    @Setup(Level.Trial)
    public void setUp() {
        engine = SearchEngine.builder(Document.class, ID)
                .textField(TITLE_TEXT)
                .textField(SUMMARY_TEXT)
                .textField(TAGS_TEXT)
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
        List<Document> documents = new ArrayList<>(documentCount);
        String matching = source("highlight", sourceTokenCount);
        String unrelated = source("presentation", sourceTokenCount);
        for (int id = 0; id < documentCount; id++) {
            documents.add(new Document(
                    id,
                    matching,
                    unrelated,
                    unrelated,
                    unrelated
            ));
        }
        for (int start = 0; start < documents.size(); start += 1_000) {
            engine.addAll(documents.subList(
                    start,
                    Math.min(start + 1_000, documents.size())
            )).join();
        }

        searchRequest = SearchRequest.<Document>builder()
                .query(query())
                .limit(topK)
                .build();
        HighlightedSearchRequest.Builder<Document> highlighted =
                HighlightedSearchRequest.<Document>builder(searchRequest)
                        .contextCharacters(contextCharacters)
                        .maxFragmentsPerField(maxFragmentsPerField);
        if (outcome.equals("unrelated")) {
            highlighted.field(TITLE_TEXT);
            if (requestedFieldCount == 3) {
                highlighted.field(SUMMARY_TEXT).field(TAGS_TEXT);
            }
        } else {
            highlighted.field(BODY_TEXT);
            if (requestedFieldCount == 3) {
                highlighted.field(TITLE_TEXT).field(SUMMARY_TEXT);
            }
        }
        highlightedRequest = highlighted.build();

        List<SearchHit<Document>> canonical = engine.search(searchRequest).hits();
        List<SearchHit<Document>> projected = engine.search(highlightedRequest)
                .hits().stream().map(HighlightedSearchHit::hit).toList();
        if (!canonical.equals(projected)) {
            throw new IllegalStateException("highlight scale control drifted");
        }
        int expected = outcome.equals("no-hit") ? 0 : topK;
        if (canonical.size() != expected) {
            throw new IllegalStateException(
                    "unexpected scale control cardinality: " + canonical.size());
        }
    }

    @TearDown(Level.Trial)
    public void tearDown() {
        engine.close();
    }

    @Benchmark
    public long ordinarySearch() {
        long checksum = 0;
        for (SearchHit<Document> hit : engine.search(searchRequest).hits()) {
            checksum += hit.document().id();
            checksum += Double.doubleToLongBits(hit.score());
        }
        return checksum;
    }

    @Benchmark
    public long highlightedSearch() {
        long checksum = 0;
        for (HighlightedSearchHit<Document> hit :
                engine.search(highlightedRequest).hits()) {
            checksum += hit.hit().document().id();
            checksum += Double.doubleToLongBits(hit.hit().score());
            for (FieldHighlight field : hit.highlights()) {
                checksum += field.fieldName().length();
                for (HighlightFragment fragment : field.fragments()) {
                    checksum += fragment.startOffset();
                    checksum += fragment.endOffset();
                    checksum += fragment.text().length();
                    checksum += fragment.spans().size();
                }
            }
        }
        return checksum;
    }

    private SearchQuery<Document> query() {
        if (outcome.equals("no-hit")) {
            return SearchQueries.text(BODY_TEXT, "term-never-present");
        }
        return switch (queryKind) {
            case "text" -> SearchQueries.text(BODY_TEXT, "highlight");
            case "phrase-exact" -> SearchQueries.phrase(
                    BODY_TEXT, "highlight stable");
            case "phrase-sloppy" -> SearchQueries.phrase(
                    BODY_TEXT, "highlight highlight", 6);
            case "fuzzy" -> SearchQueries.fuzzy(BODY_TEXT, "higlight");
            case "bool-boost" -> SearchQueries.<Document>bool()
                    .must(SearchQueries.text(BODY_TEXT, "highlight"))
                    .should(SearchQueries.phrase(
                            BODY_TEXT, "highlight stable"))
                    .should(SearchQueries.fuzzy(BODY_TEXT, "higlight"))
                    .minimumShouldMatch(1)
                    .build()
                    .boost(2.0);
            default -> throw new IllegalArgumentException(
                    "unknown queryKind: " + queryKind);
        };
    }

    private static String source(String first, int tokenCount) {
        StringBuilder source = new StringBuilder(tokenCount * 10);
        for (int token = 0; token < tokenCount; token++) {
            if (!source.isEmpty()) {
                source.append(' ');
            }
            source.append(token % 7 == 0 ? first : "stable");
        }
        return source.toString();
    }

    private record Document(
            int id,
            String body,
            String title,
            String summary,
            String tags
    ) {
    }
}
