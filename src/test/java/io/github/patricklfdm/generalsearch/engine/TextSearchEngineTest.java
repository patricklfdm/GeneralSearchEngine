package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class TextSearchEngineTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void searchesTextAndStructuredPredicatesAcrossIndexLifecycle() {
        try (SearchEngine<Long, Article> engine = SearchEngine.builder(Article.class, ID)
                .index(IndexDefinition.text(TEXT))
                .index(IndexDefinition.equality(CATEGORY))
                .build()) {
            add(engine,
                    new Article(1, "Fast Java search", "guide"),
                    new Article(2, "JAVA memory model", "reference"),
                    new Article(3, "Search engine design", "guide"),
                    new Article(4, null, "guide"));

            assertSame(TEXT, engine.schema().requireTextField("body"));
            assertEquals(Set.of(1L, 2L), ids(engine.search(Query.term(TEXT, "java"))));
            assertEquals(Set.of(1L, 2L, 3L),
                    ids(engine.search(Query.anyTerms(TEXT, "java, SEARCH"))));
            assertEquals(Set.of(1L),
                    ids(engine.search(Query.allTerms(TEXT, "search fast search"))));
            assertEquals(Set.of(1L, 3L), ids(engine.search(Query.and(
                    Query.term(TEXT, "search"),
                    Query.eq(CATEGORY, "guide")))));
            assertEquals(Set.of(2L, 3L, 4L), ids(engine.search(Query.or(
                    Query.term(TEXT, "memory"),
                    Query.not(Query.term(TEXT, "java"))))));
            assertTrue(engine.search(Query.anyTerms(TEXT, "!!!")).isEmpty());
            assertTrue(engine.search(Query.allTerms(TEXT, "")).isEmpty());

            engine.dropIndex("body").join();
            assertEquals(Set.of(1L, 2L), ids(engine.search(Query.term(TEXT, "java"))));
            engine.createIndex(IndexDefinition.text(TEXT)).join();
            assertEquals(Set.of(3L),
                    ids(engine.search(Query.allTerms(TEXT, "search engine"))));
        }
    }

    @Test
    void rejectsNonCanonicalTextConfigurationAtStartupAndDynamicCreation() {
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .field(CATEGORY)
                .textField(TEXT)
                .build();
        TextField<Article> competing = TextField.of(BODY, Analyzer.simple());

        assertThrows(IllegalArgumentException.class,
                () -> SearchEngine.builder(schema)
                        .index(IndexDefinition.text(competing)));
        assertThrows(IllegalArgumentException.class,
                () -> new SnapshotSearchEngine<>(
                        schema, List.of(IndexDefinition.text(competing))));

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            CompletionException failure = assertThrows(CompletionException.class,
                    () -> engine.createIndex(IndexDefinition.text(competing)).join());
            assertTrue(failure.getCause() instanceof IllegalArgumentException);
        }
    }

    @Test
    void replaysTextMutationsThatCompleteDuringBackgroundBuild() throws Exception {
        BlockingAnalyzer analyzer = new BlockingAnalyzer();
        TextField<Article> text = TextField.of(BODY, analyzer);
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .field(CATEGORY)
                .textField(text)
                .build();

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            for (long id = 0; id < 100; id++) {
                engine.add(new Article(id, "stable common", "base")).join();
            }

            analyzer.blockNextIndexBuild();
            CompletableFuture<Void> creation =
                    engine.createIndex(IndexDefinition.text(text));
            assertTrue(analyzer.awaitBuildStart());

            engine.update(new Article(0, "replacement replay", "updated")).join();
            engine.remove(1L).join();
            engine.add(new Article(1_000, "replay added", "new")).join();

            analyzer.releaseBuild();
            creation.join();

            assertEquals(Set.of(0L, 1_000L),
                    ids(engine.search(Query.term(text, "replay"))));
            assertEquals(98, engine.search(Query.term(text, "common")).size());
            TextIndexSnapshot<?> index = (TextIndexSnapshot<?>) engine
                    .snapshotForTesting()
                    .indexes()
                    .indexes()
                    .stream()
                    .filter(TextIndexSnapshot.class::isInstance)
                    .findFirst()
                    .orElseThrow();
            assertEquals(new IndexStatistics(100, 5), index.statistics());
            assertEquals(2, index.documentLength(
                    engine.internalDocIdForTesting(0L)));
            assertEquals(2, index.documentLength(
                    engine.internalDocIdForTesting(1_000L)));
            assertEquals(200, index.totalDocumentLength());
            assertEquals(2.0, index.averageDocumentLength());
        } finally {
            analyzer.releaseBuild();
        }
    }

    @Test
    void failedAnalyzerBuildLeavesEngineUsableAndCanBeRetried() {
        AtomicBoolean failBuild = new AtomicBoolean(true);
        Analyzer analyzer = text -> {
            if (failBuild.get()
                    && Thread.currentThread().getName()
                    .startsWith("snapshot-index-builder-")) {
                throw new IllegalStateException("synthetic analyzer failure");
            }
            return Analyzer.simple().analyze(text);
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .field(CATEGORY)
                .textField(text)
                .build();

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Article(1, "java search", "guide")).join();
            assertThrows(CompletionException.class,
                    () -> engine.createIndex(IndexDefinition.text(text)).join());

            engine.update(new Article(1, "engine search", "guide")).join();
            assertEquals(Set.of(1L), ids(engine.search(Query.term(text, "engine"))));
            failBuild.set(false);
            engine.createIndex(IndexDefinition.text(text)).join();

            assertEquals(Set.of(1L), ids(engine.search(Query.term(text, "engine"))));
            assertTrue(engine.search(Query.term(text, "java")).isEmpty());
        }
    }

    @Test
    void failedAnalyzerMutationPublishesNeitherDocumentNorRankingMetadata() {
        Analyzer analyzer = text -> {
            if (text != null && text.contains("explode")) {
                throw new IllegalStateException("synthetic analyzer failure");
            }
            return Analyzer.simple().analyze(text);
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .field(CATEGORY)
                .textField(text)
                .build();
        Article original = new Article(1, "stable java", "guide");

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(
                             schema, List.of(IndexDefinition.text(text)))) {
            engine.add(original).join();
            long version = engine.metrics().snapshotVersion();

            assertThrows(CompletionException.class,
                    () -> engine.update(
                            new Article(1, "explode update", "news")).join());
            assertThrows(CompletionException.class,
                    () -> engine.add(
                            new Article(2, "explode add", "guide")).join());

            assertEquals(version, engine.metrics().snapshotVersion());
            assertEquals(original, engine.get(1L));
            assertEquals(null, engine.get(2L));
            assertEquals(Set.of(1L), ids(engine.search(Query.term(text, "stable"))));
            assertTrue(engine.search(Query.term(text, "update")).isEmpty());
        }
    }

    @SafeVarargs
    private static void add(SearchEngine<Long, Article> engine, Article... articles) {
        for (Article article : articles) {
            engine.add(article).join();
        }
    }

    private static Set<Long> ids(List<Article> articles) {
        Set<Long> ids = new HashSet<>();
        articles.forEach(article -> ids.add(article.id()));
        return ids;
    }

    private record Article(long id, String body, String category) {}

    private static final class BlockingAnalyzer implements Analyzer {
        private final AtomicBoolean armed = new AtomicBoolean();
        private volatile CountDownLatch started = new CountDownLatch(0);
        private volatile CountDownLatch release = new CountDownLatch(0);

        @Override
        public List<Token> analyze(String text) {
            if (Thread.currentThread().getName().startsWith("snapshot-index-builder-")
                    && armed.compareAndSet(true, false)) {
                started.countDown();
                try {
                    release.await();
                } catch (InterruptedException failure) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("index build was interrupted", failure);
                }
            }
            return Analyzer.simple().analyze(text);
        }

        private void blockNextIndexBuild() {
            started = new CountDownLatch(1);
            release = new CountDownLatch(1);
            armed.set(true);
        }

        private boolean awaitBuildStart() throws InterruptedException {
            return started.await(5, TimeUnit.SECONDS);
        }

        private void releaseBuild() {
            release.countDown();
        }
    }
}
