package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;

/** Shared deterministic production-shape corpus for the V3 performance suite. */
final class V3ProductionBenchmarkSupport {
    static final Field<Document, Long> ID =
            Field.of("id", Long.class, Document::id);
    static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    static final Field<Document, Integer> POPULARITY =
            Field.of("popularity", Integer.class, Document::popularity);
    static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    static final Field<Document, String> TAGS =
            Field.of("tags", String.class, Document::tags);
    static final Field<Document, String> SUMMARY =
            Field.of("summary", String.class, Document::summary);
    static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    static final TextField<Document> TAGS_TEXT =
            TextField.of(TAGS, Analyzer.simple());
    static final TextField<Document> SUMMARY_TEXT =
            TextField.of(SUMMARY, Analyzer.simple());

    private static final String[] CATEGORIES = {
            "travel", "reference", "news", "shopping"
    };
    private static final String[] ENGLISH_TERMS = {
            "search", "engine", "java", "snapshot", "ranking", "index",
            "query", "memory", "thread", "stable", "travel", "museum",
            "river", "hotel", "guide", "modern", "history", "flight",
            "station", "coast", "mountain", "forest", "market", "city",
            "local", "family", "quiet", "popular", "budget", "luxury",
            "weekend", "route"
    };
    private static final String[] CHINESE_TERMS = {
            "搜索", "引擎", "旅行", "博物馆", "河流", "酒店", "指南", "城市",
            "历史", "现代", "航班", "车站", "海岸", "山地", "森林", "市场",
            "本地", "家庭", "安静", "热门", "经济", "豪华", "周末", "路线"
    };

    private V3ProductionBenchmarkSupport() {
    }

    static Fixture createFixture(int documentCount, String profile) {
        CorpusProfile shape = CorpusProfile.parse(profile);
        var builder = SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.equality(CATEGORY))
                .field(POPULARITY)
                .index(IndexDefinition.text(BODY_TEXT));
        if (shape.fieldCount() == 4) {
            builder.index(IndexDefinition.text(TITLE_TEXT))
                    .index(IndexDefinition.text(TAGS_TEXT))
                    .index(IndexDefinition.text(SUMMARY_TEXT));
        }
        SearchEngine<Long, Document> engine = builder.build();
        List<Document> batch = new ArrayList<>(1_000);
        for (int id = 0; id < documentCount; id++) {
            batch.add(document(id, 0, shape));
            if (batch.size() == 1_000) {
                engine.addAll(batch).join();
                batch.clear();
            }
        }
        if (!batch.isEmpty()) {
            engine.addAll(batch).join();
        }
        return new Fixture(engine, shape);
    }

    static List<SearchRequest<Document>> requests(
            Fixture fixture,
            int topK
    ) {
        CorpusProfile profile = fixture.profile();
        SearchRequest<Document> text = request(
                SearchQueries.text(BODY_TEXT, "search"), topK);
        SearchRequest<Document> phrase = request(
                SearchQueries.phrase(BODY_TEXT, "search engine"), topK);
        SearchRequest<Document> fuzzy = request(
                SearchQueries.fuzzy(BODY_TEXT, "serach"), topK);
        var bool = SearchQueries.<Document>bool()
                .must(SearchQueries.text(BODY_TEXT, "search"));
        if (profile.fieldCount() == 4) {
            bool.should(SearchQueries.text(TITLE_TEXT, "java").boost(1.5))
                    .should(SearchQueries.phrase(
                            SUMMARY_TEXT,
                            profile.bilingual() ? "旅行 搜索" : "travel search"
                    ).boost(2.0));
        } else {
            bool.should(SearchQueries.text(BODY_TEXT, "travel").boost(1.5));
        }
        SearchRequest<Document> composed = SearchRequest.<Document>builder()
                .query(bool.build())
                .filter(Query.eq(CATEGORY, "travel"))
                .limit(topK)
                .build();
        return List.of(text, composed, phrase, fuzzy);
    }

    static SearchRequest<Document> requestFor(
            Fixture fixture,
            String queryType,
            int topK
    ) {
        int index = switch (queryType) {
            case "TEXT" -> 0;
            case "BOOL" -> 1;
            case "PHRASE" -> 2;
            case "FUZZY" -> 3;
            default -> throw new IllegalArgumentException(
                    "unknown query type: " + queryType);
        };
        return requests(fixture, topK).get(index);
    }

    static Document replacement(long id, int revision, CorpusProfile profile) {
        return document(Math.toIntExact(id), revision, profile);
    }

    private static SearchRequest<Document> request(
            io.github.patricklfdm.generalsearch.search.SearchQuery<Document> query,
            int topK
    ) {
        return SearchRequest.<Document>builder()
                .query(query)
                .limit(topK)
                .build();
    }

    private static Document document(int id, int revision, CorpusProfile profile) {
        String title = profile.fieldCount() == 4
                ? text(id, revision, profile, Math.max(4, profile.tokenCount() / 8), 11)
                : "";
        String body = text(id, revision, profile, profile.tokenCount(), 17);
        String tags = profile.fieldCount() == 4
                ? text(id, revision, profile, Math.max(4, profile.tokenCount() / 16), 23)
                : "";
        String summary = profile.fieldCount() == 4
                ? text(id, revision, profile, Math.max(8, profile.tokenCount() / 4), 31)
                : "";
        return new Document(
                (long) id,
                CATEGORIES[Math.floorMod(id + revision, CATEGORIES.length)],
                Math.floorMod(id * 37 + revision * 101, 10_001),
                title,
                body,
                tags,
                summary
        );
    }

    private static String text(
            int id,
            int revision,
            CorpusProfile profile,
            int tokenCount,
            int salt
    ) {
        StringBuilder result = new StringBuilder(tokenCount * 9);
        for (int position = 0; position < tokenCount; position++) {
            if (!result.isEmpty()) {
                result.append(' ');
            }
            if (position == 0 && Math.floorMod(id + salt, 7) == 0) {
                result.append("search");
            } else if (position == 1 && Math.floorMod(id + salt, 7) == 0) {
                result.append("engine");
            } else if (profile.bilingual()
                    && position == 2
                    && Math.floorMod(id + salt, 11) == 0) {
                result.append("旅行");
            } else if (profile.bilingual()
                    && position == 3
                    && Math.floorMod(id + salt, 11) == 0) {
                result.append("搜索");
            } else {
                result.append(corpusTerm(id, revision, position, salt, profile));
            }
        }
        return result.toString();
    }

    private static String corpusTerm(
            int id,
            int revision,
            int position,
            int salt,
            CorpusProfile profile
    ) {
        long mixed = mix64((long) id * 1_000_003L
                + (long) revision * 65_537L
                + (long) position * 257L
                + salt);
        boolean chinese = profile.bilingual() && (mixed & 3L) == 0L;
        String[] vocabulary = chinese ? CHINESE_TERMS : ENGLISH_TERMS;
        int rank;
        if (profile.zipf()) {
            double unit = (mixed >>> 11) * 0x1.0p-53;
            rank = Math.min(
                    vocabulary.length - 1,
                    (int) (unit * unit * unit * vocabulary.length));
        } else {
            rank = (int) Math.floorMod(mixed, vocabulary.length);
        }
        return vocabulary[rank];
    }

    private static long mix64(long value) {
        value = (value ^ (value >>> 33)) * 0xff51afd7ed558ccdl;
        value = (value ^ (value >>> 33)) * 0xc4ceb9fe1a85ec53l;
        return value ^ (value >>> 33);
    }

    record Fixture(
            SearchEngine<Long, Document> engine,
            CorpusProfile profile
    ) implements AutoCloseable {
        @Override
        public void close() {
            engine.close();
        }
    }

    record CorpusProfile(
            boolean zipf,
            boolean bilingual,
            int tokenCount,
            int fieldCount
    ) {
        private static CorpusProfile parse(String name) {
            return switch (name) {
                case "uniform-en-short-1" -> new CorpusProfile(false, false, 8, 1);
                case "zipf-en-medium-4" -> new CorpusProfile(true, false, 64, 4);
                case "zipf-bilingual-long-4" ->
                        new CorpusProfile(true, true, 256, 4);
                default -> throw new IllegalArgumentException(
                        "unknown corpus profile: " + name);
            };
        }
    }

    record Document(
            long id,
            String category,
            int popularity,
            String title,
            String body,
            String tags,
            String summary
    ) {
    }
}
