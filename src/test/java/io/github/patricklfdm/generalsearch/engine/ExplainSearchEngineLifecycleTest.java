package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;

class ExplainSearchEngineLifecycleTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);

    @Test
    void followsDynamicIndexMutationAndRemovalPublication() {
        TextField<Article> text = TextField.of(BODY, Analyzer.simple());
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .textField(text)
                .build();
        SearchRequest<Article> phrase = SearchRequest.of(
                SearchQueries.phrase(text, "quiet restaurant")
        );
        SearchRequest<Article> fuzzy = SearchRequest.of(
                SearchQueries.fuzzy(text, "restarant")
        );

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            Article original = new Article(1L, "quiet restaurant district");
            engine.add(original).join();
            assertThrows(
                    IllegalStateException.class,
                    () -> engine.explain(phrase, 1L)
            );

            engine.createIndex(IndexDefinition.text(text)).join();
            assertTrue(engine.explain(phrase, 1L).orElseThrow().matched());
            assertTrue(engine.explain(fuzzy, 1L).orElseThrow().matched());

            Article reordered = new Article(1L, "restaurant quiet district");
            engine.update(reordered).join();
            assertFalse(engine.explain(phrase, 1L).orElseThrow().matched());
            Article exactTypo = new Article(1L, "restarant quiet district");
            engine.update(exactTypo).join();
            SearchExplanation<Article> exact = engine.explain(fuzzy, 1L)
                    .orElseThrow();
            assertTrue(exact.matched());
            assertTrue(descriptions(exact.detail()).contains("exact-term priority"));

            engine.addAll(List.of(
                    new Article(2L, "quiet restaurant annex"),
                    new Article(3L, "restarant guide")
            )).join();
            assertTrue(engine.explain(fuzzy, 2L).orElseThrow().matched());
            assertTrue(engine.explain(fuzzy, 3L).orElseThrow().matched());
            engine.updateAll(List.of(
                    new Article(2L, "unrelated"),
                    new Article(3L, "restaurant guide")
            )).join();
            assertFalse(engine.explain(fuzzy, 2L).orElseThrow().matched());
            assertTrue(engine.explain(fuzzy, 3L).orElseThrow().matched());
            engine.removeAll(List.of(2L, 3L)).join();
            assertTrue(engine.explain(fuzzy, 2L).isEmpty());

            engine.dropIndex(BODY.name()).join();
            assertThrows(
                    IllegalStateException.class,
                    () -> engine.explain(fuzzy, 1L)
            );
            engine.createIndex(IndexDefinition.text(text)).join();
            assertTrue(engine.explain(fuzzy, 1L).orElseThrow().matched());

            engine.remove(1L).join();
            assertTrue(engine.explain(fuzzy, 1L).isEmpty());
        }
    }

    @Test
    void keepsOnePublishedStateWhileAnalysisIsBlocked() throws Exception {
        CountDownLatch analysisEntered = new CountDownLatch(1);
        CountDownLatch releaseAnalysis = new CountDownLatch(1);
        AtomicBoolean block = new AtomicBoolean();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("blocked") && block.get()) {
                    analysisEntered.countDown();
                    try {
                        if (!releaseAnalysis.await(5, TimeUnit.SECONDS)) {
                            throw new AssertionError("timed out releasing Explain");
                        }
                    } catch (InterruptedException failure) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError("Explain interrupted", failure);
                    }
                    return List.of(new AnalyzedToken("java", 1));
                }
                return Analyzer.super.analyzeWithPositions(text);
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        Article original = new Article(1L, "java");
        Article updated = new Article(1L, "other");

        try (SearchEngine<Long, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.add(original).join();
            block.set(true);
            CompletableFuture<SearchExplanation<Article>> pending =
                    CompletableFuture.supplyAsync(() -> engine.explain(
                            SearchRequest.of(SearchQueries.text(text, "blocked")),
                            1L
                    ).orElseThrow());

            assertTrue(analysisEntered.await(5, TimeUnit.SECONDS));
            engine.update(updated).join();
            releaseAnalysis.countDown();

            SearchExplanation<Article> captured = pending.get(5, TimeUnit.SECONDS);
            assertSame(original, captured.document());
            assertTrue(captured.matched());
            assertEquals(
                    original,
                    captured.document()
            );
            assertFalse(engine.explain(
                    SearchRequest.of(SearchQueries.text(text, "java")),
                    1L
            ).orElseThrow().matched());
        } finally {
            releaseAnalysis.countDown();
        }
    }

    @Test
    void keepsPendingDynamicIndexInvisibleUntilPublication() throws Exception {
        CountDownLatch buildEntered = new CountDownLatch(1);
        CountDownLatch releaseBuild = new CountDownLatch(1);
        AtomicBoolean blockBuild = new AtomicBoolean();
        Analyzer analyzer = text -> {
            if (Thread.currentThread().getName().startsWith(
                    "snapshot-index-builder-")
                    && blockBuild.compareAndSet(true, false)) {
                buildEntered.countDown();
                try {
                    if (!releaseBuild.await(5, TimeUnit.SECONDS)) {
                        throw new AssertionError("timed out releasing index build");
                    }
                } catch (InterruptedException failure) {
                    Thread.currentThread().interrupt();
                    throw new AssertionError("index build interrupted", failure);
                }
            }
            return Analyzer.simple().analyze(text);
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .textField(text)
                .build();
        SearchRequest<Article> request = SearchRequest.of(
                SearchQueries.text(text, "java")
        );

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Article(1L, "java search")).join();
            blockBuild.set(true);
            CompletableFuture<Void> creation = engine.createIndex(
                    IndexDefinition.text(text)
            );
            assertTrue(buildEntered.await(5, TimeUnit.SECONDS));
            assertThrows(
                    IllegalStateException.class,
                    () -> engine.explain(request, 1L)
            );

            releaseBuild.countDown();
            creation.get(5, TimeUnit.SECONDS);
            assertTrue(engine.explain(request, 1L).orElseThrow().matched());
        } finally {
            releaseBuild.countDown();
        }
    }

    private record Article(long id, String body) {
    }

    private static String descriptions(
            io.github.patricklfdm.generalsearch.search.ExplanationNode node
    ) {
        StringBuilder result = new StringBuilder(node.description());
        node.children().forEach(child -> result
                .append('\n')
                .append(descriptions(child)));
        return result.toString();
    }
}
