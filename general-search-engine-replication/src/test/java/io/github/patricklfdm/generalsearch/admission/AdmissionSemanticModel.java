package io.github.patricklfdm.generalsearch.admission;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.*;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.schema.*;
import io.github.patricklfdm.generalsearch.search.*;

/** Uses published V4.4 APIs only; compiled separately against the pinned control JAR. */
public final class AdmissionSemanticModel {
    public record Doc(int id, String title, String category, int price, String body) { }
    public static final Field<Doc, Integer> ID = Field.of("id", Integer.class, Doc::id);
    public static final Field<Doc, String> TITLE = Field.of("title", String.class, Doc::title);
    public static final Field<Doc, String> CATEGORY = Field.of("category", String.class, Doc::category);
    public static final Field<Doc, Integer> PRICE = Field.of("price", Integer.class, Doc::price);
    public static final Field<Doc, String> BODY = Field.of("body", String.class, Doc::body);
    public static final TextField<Doc> TEXT = TextField.of(BODY, SimpleAnalyzer.INSTANCE);
    private AdmissionSemanticModel() { }
    public static SearchEngineBuilder<Integer, Doc> builder() {
        return SearchEngine.builder(Doc.class, ID).index(IndexDefinition.prefix(TITLE)).index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE)).index(IndexDefinition.text(TEXT))
                .config(new SnapshotEngineConfig(31, 7, Duration.ofNanos(1_234_567)))
                .plannerConfig(new PlannerConfig(RangePlanningMode.FORCE_SCAN));
    }
    public static DurableStorageConfig<Integer, Doc> storage(Path path, int minor) {
        var config = DurableStorageConfig.builder(path, new Codec()).format(new DurableStorageFormat("gse-durable", 1, minor))
                .storageIdentity("semantic-store").schemaIdentity("semantic-schema").maxEncodedKeyBytes(1024)
                .maxEncodedDocumentBytes(65536).maxBulkElements(1000).maxDocuments(10000).checkpointWalBytes(1024).maxRetainedBytes(1 << 30);
        if (minor == 2) config.maxDerivedStateBytes(1 << 20);
        return config.build();
    }
    public static void populate(SearchEngine<Integer, Doc> engine) {
        engine.addAll(List.of(new Doc(9, "Removed", "news", 9, "old"), new Doc(3, "Java Search", "guide", 30, "java search search"),
                new Doc(1, "Java Memory", "guide", 10, "java memory search"), new Doc(7, "Prefix Query", "reference", 70, "query search"))).join();
        engine.remove(9).join();
        engine.update(new Doc(1, "Updated Memory", "guide", 22, "java memory tuned search")).join();
        engine.add(new Doc(5, "Java Query", "guide", 55, "java query query search")).join();
    }
    public static Map<String, Object> report(SearchEngine<Integer, Doc> engine) {
        var ordered = engine.search(doc -> true);
        List<Query<Doc>> queries = List.of(Query.eq(CATEGORY, "guide"), Query.prefix(TITLE, "Java"), Query.between(PRICE, 20, 60),
                Query.term(TEXT, "java"), Query.allTerms(TEXT, "java search"), Query.anyTerms(TEXT, "memory query"),
                Query.and(Query.eq(CATEGORY, "guide"), Query.term(TEXT, "search")), Query.not(Query.eq(CATEGORY, "news")));
        var search = SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT, "java search")).limit(2).build();
        var pages = new ArrayList<Object>(); var page = engine.search(SearchPageRequest.builder(search).totalHits(TotalHitsMode.EXACT).build());
        pages.add(Map.of("hits", hits(page.hits()), "total", page.totalHits().orElseThrow()));
        while (page.nextCursor().isPresent()) {
            page = engine.search(SearchPageRequest.builder(search).after(page.nextCursor().orElseThrow()).totalHits(TotalHitsMode.EXACT).build());
            pages.add(Map.of("hits", hits(page.hits()), "total", page.totalHits().orElseThrow()));
        }
        var explanations = ordered.stream().map(doc -> engine.explain(search, doc.id()).orElseThrow())
                .map(value -> Map.of("id", value.document().id(), "matched", value.matched(), "score", Double.toHexString(value.score()), "detail", explanation(value.detail()))).toList();
        var highlights = engine.search(HighlightedSearchRequest.<Doc>builder(search).field(TEXT).contextCharacters(3).maxFragmentsPerField(3).build()).hits()
                .stream().map(hit -> Map.of("id", hit.hit().document().id(), "score", Double.toHexString(hit.hit().score()), "fields",
                        hit.highlights().stream().map(field -> Map.of("field", field.fieldName(), "fragments", field.fragments().stream()
                                .map(fragment -> Map.of("start", fragment.startOffset(), "end", fragment.endOffset(), "text", fragment.text(),
                                        "spans", fragment.spans().stream().map(span -> List.of(span.startOffset(), span.endOffset())).toList())).toList())).toList())).toList();
        return Map.of("documents", ordered.stream().map(Doc::toString).toList(), "queries", queries.stream().map(query -> engine.search(query).stream().map(Doc::id).toList()).toList(),
                "ranking", hits(engine.searchTopK(RankedSearchRequest.of(TextScoringQuery.of(TEXT, "java search"), 20))),
                "phrase", hits(engine.search(SearchRequest.of(SearchQueries.phrase(TEXT, "java search"))).hits()),
                "fuzzy", hits(engine.search(SearchRequest.of(SearchQueries.fuzzy(TEXT, "serch"))).hits()),
                "pages", pages, "explanations", explanations, "highlights", highlights, "indexCount", engine.metrics().registeredIndexCount());
    }
    private static Object hits(List<SearchHit<Doc>> hits) {
        return hits.stream().map(hit -> Map.of("id", hit.document().id(), "score", Double.toHexString(hit.score()))).toList();
    }

    private static Object explanation(ExplanationNode node) {
        return Map.of("matched", node.matched(), "score", Double.toHexString(node.score()), "description", node.description(),
                "children", node.children().stream().map(AdmissionSemanticModel::explanation).toList());
    }
    public static final class Codec implements DurableCodec<Integer, Doc> {
        public String codecId() { return "semantic-codec"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer key) { return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) { return ByteBuffer.wrap(bytes).getInt(); }
        public byte[] encodeDocument(Doc doc) { return (doc.id() + "\n" + doc.title() + "\n" + doc.category() + "\n" + doc.price() + "\n" + doc.body()).getBytes(StandardCharsets.UTF_8); }
        public Doc decodeDocument(byte[] bytes) { String[] v = new String(bytes, StandardCharsets.UTF_8).split("\n", 5); return new Doc(Integer.parseInt(v[0]), v[1], v[2], Integer.parseInt(v[3]), v[4]); }
    }
}
