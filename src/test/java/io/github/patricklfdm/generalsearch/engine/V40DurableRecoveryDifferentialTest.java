package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.exception.SearchCursorException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchAfterCursor;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageResult;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.TotalHitsMode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V40DurableRecoveryDifferentialTest {
    private static final Field<Article, Integer> ID =
            Field.of("id", Integer.class, Article::id);
    private static final Field<Article, String> TITLE =
            Field.of("title", String.class, Article::title);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final Field<Article, Integer> PRICE =
            Field.of("price", Integer.class, Article::price);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, SimpleAnalyzer.INSTANCE);

    @Test
    void recoveredEngineMatchesUninterruptedOracleAcrossV34Capabilities(
            @TempDir Path directory
    ) {
        SearchEngine<Integer, Article> oracle = builder().build();
        DurableStorageConfig<Integer, Article> storage =
                DurableStorageConfig.builder(directory, new ArticleCodec())
                        .storageIdentity("phase3-differential-store-v1")
                        .schemaIdentity("phase3-differential-schema-v1")
                        .build();
        DurableSearchEngine<Integer, Article> durable =
                builder().buildDurable(storage);
        SearchAfterCursor oldCursor;
        try {
            applyHistory(oracle);
            applyHistory(durable);
            assertEquivalent(oracle, durable);
            SearchPageResult<Article> preCrash = durable.search(pageRequest());
            oldCursor = preCrash.nextCursor().orElseThrow();
            assertEquals(10, durable.currentSequence());
        } finally {
            durable.close();
        }

        try (DurableSearchEngine<Integer, Article> recovered =
                     builder().buildDurable(storage)) {
            assertEquals(10, recovered.currentSequence());
            assertEquals(0, recovered.metrics().snapshotVersion());
            assertEquivalent(oracle, recovered);
            assertThrows(SearchCursorException.class, () -> recovered.search(
                    SearchPageRequest.builder(searchRequest())
                            .after(oldCursor)
                            .totalHits(TotalHitsMode.EXACT)
                            .build()));
        } finally {
            oracle.close();
        }
    }

    private static void applyHistory(SearchEngine<Integer, Article> engine) {
        engine.addAll(List.of(
                article(1, "Java Search", "guide", 10, "java search engine"),
                article(2, "Java Memory", "guide", 20, "java memory memory"),
                article(3, "Engine Notes", "reference", 30, "search engine notes"),
                article(4, "Archive", "news", 40, "old archive"),
                article(5, "Java Query", "guide", 50, "java query search"),
                article(6, "Prefix Alpha", "news", 60, "alpha search"),
                article(7, "Prefix Beta", "reference", 70, "beta java"),
                article(8, "Removal", "guide", 80, "remove this"))).join();
        engine.update(article(
                1, "Updated Java Search", "guide", 11, "java java search engine"))
                .join();
        engine.update(article(
                3, "Updated Notes", "reference", 33, "search notes"))
                .join();
        engine.remove(4).join();
        engine.remove(99).join();
        engine.createIndex(IndexDefinition.range(PRICE)).join();
        engine.dropIndex(TITLE.name()).join();
        engine.createIndex(IndexDefinition.prefix(TITLE)).join();
        engine.updateAll(List.of(
                article(2, "Java Memory", "guide", 22, "java memory tuned"),
                article(5, "Java Query", "guide", 55, "java query query search")))
                .join();
        engine.removeAll(List.of(6, 8)).join();
    }

    private static void assertEquivalent(
            SearchEngine<Integer, Article> expected,
            SearchEngine<Integer, Article> actual
    ) {
        for (int id = 1; id <= 9; id++) {
            assertEquals(expected.get(id), actual.get(id), "get(" + id + ")");
        }
        List<Query<Article>> queries = List.of(
                Query.eq(CATEGORY, "guide"),
                Query.prefix(TITLE, "Updated"),
                Query.between(PRICE, 20, 60),
                Query.term(TEXT, "java"),
                Query.and(
                        Query.eq(CATEGORY, "guide"),
                        Query.term(TEXT, "search")),
                Query.or(
                        Query.prefix(TITLE, "Prefix"),
                        Query.eq(CATEGORY, "reference")),
                Query.not(Query.eq(CATEGORY, "news")));
        for (Query<Article> query : queries) {
            assertEquals(expected.search(query), actual.search(query), query.toString());
        }

        RankedSearchRequest<Article> ranked = RankedSearchRequest.filtered(
                TextScoringQuery.of(TEXT, "java search"),
                Query.not(Query.eq(CATEGORY, "news")),
                20);
        List<SearchHit<Article>> expectedRanked = expected.searchTopK(ranked);
        List<SearchHit<Article>> actualRanked = actual.searchTopK(ranked);
        assertEquals(expectedRanked, actualRanked);
        for (int index = 0; index < expectedRanked.size(); index++) {
            assertEquals(
                    Double.doubleToLongBits(expectedRanked.get(index).score()),
                    Double.doubleToLongBits(actualRanked.get(index).score()));
        }

        SearchPageResult<Article> expectedPage = expected.search(pageRequest());
        SearchPageResult<Article> actualPage = actual.search(pageRequest());
        assertEquals(expectedPage.hits(), actualPage.hits());
        assertEquals(expectedPage.totalHits(), actualPage.totalHits());
        assertEquals(expectedPage.nextCursor().isPresent(),
                actualPage.nextCursor().isPresent());

        for (int id : List.of(1, 2, 3, 5, 7)) {
            var expectedExplanation = expected.explain(searchRequest(), id).orElseThrow();
            var actualExplanation = actual.explain(searchRequest(), id).orElseThrow();
            assertEquals(expectedExplanation.matched(), actualExplanation.matched());
            assertEquals(
                    Double.doubleToLongBits(expectedExplanation.score()),
                    Double.doubleToLongBits(actualExplanation.score()));
            assertEquals(expectedExplanation.detail().description(),
                    actualExplanation.detail().description());
        }
    }

    private static SearchRequest<Article> searchRequest() {
        return SearchRequest.<Article>builder()
                .query(io.github.patricklfdm.generalsearch.search.SearchQueries.text(
                        TEXT, "java search"))
                .filter(Query.not(Query.eq(CATEGORY, "news")))
                .limit(2)
                .build();
    }

    private static SearchPageRequest<Article> pageRequest() {
        return SearchPageRequest.builder(searchRequest())
                .totalHits(TotalHitsMode.EXACT)
                .build();
    }

    private static SearchEngineBuilder<Integer, Article> builder() {
        return SearchEngine.builder(Article.class, ID)
                .field(TITLE)
                .field(CATEGORY)
                .field(PRICE)
                .textField(TEXT)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.prefix(TITLE))
                .index(IndexDefinition.text(TEXT));
    }

    private static Article article(
            int id,
            String title,
            String category,
            int price,
            String body
    ) {
        return new Article(id, title, category, price, body);
    }

    private record Article(
            int id,
            String title,
            String category,
            int price,
            String body
    ) {
    }

    private static final class ArticleCodec implements DurableCodec<Integer, Article> {
        @Override
        public String codecId() {
            return "phase3-article-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(Integer.BYTES).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid article key");
            }
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Article document) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    writeString(output, document.title());
                    writeString(output, document.category());
                    output.writeInt(document.price());
                    writeString(output, document.body());
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        @Override
        public Article decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Article article = new Article(
                        input.readInt(),
                        readString(input),
                        readString(input),
                        input.readInt(),
                        readString(input));
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing article bytes");
                }
                return article;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid article", failure);
            }
        }

        private static void writeString(DataOutputStream output, String value)
                throws IOException {
            byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
            output.writeInt(bytes.length);
            output.write(bytes);
        }

        private static String readString(DataInputStream input) throws IOException {
            int length = input.readInt();
            if (length < 0 || length > input.available()) {
                throw new IllegalArgumentException("invalid article string");
            }
            return new String(input.readNBytes(length), StandardCharsets.UTF_8);
        }
    }
}
