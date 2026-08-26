package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import org.junit.jupiter.api.Test;

class PhraseSearchEngineLifecycleTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);

    @Test
    void publishesReplayCorrectPhrasePositionsAcrossDynamicLifecycle()
            throws Exception {
        BlockingAnalyzer analyzer = new BlockingAnalyzer();
        TextField<Article> text = TextField.of(BODY, analyzer);
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .textField(text)
                .build();

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Article(0, "java search original")).join();
            for (long id = 1; id < 100; id++) {
                engine.add(new Article(id, "stable common")).join();
            }

            assertThrows(
                    IllegalStateException.class,
                    () -> phraseIds(engine, text, "java search")
            );

            analyzer.blockNextIndexBuild();
            CompletableFuture<Void> creation =
                    engine.createIndex(IndexDefinition.text(text));
            assertTrue(analyzer.awaitBuildStart());

            engine.update(new Article(0, "search java updated")).join();
            engine.remove(1L).join();
            engine.add(new Article(1_000, "java search added")).join();

            analyzer.releaseBuild();
            creation.join();

            assertEquals(Set.of(1_000L), phraseIds(engine, text, "java search"));
            assertEquals(Set.of(0L), phraseIds(engine, text, "search java"));

            engine.updateAll(List.of(
                    new Article(0, "java search restored"),
                    new Article(2, "java search bulk")
            )).join();
            assertEquals(
                    Set.of(0L, 2L, 1_000L),
                    phraseIds(engine, text, "java search")
            );

            engine.removeAll(List.of(2L, 1_000L)).join();
            assertEquals(Set.of(0L), phraseIds(engine, text, "java search"));

            engine.dropIndex(BODY.name()).join();
            assertThrows(
                    IllegalStateException.class,
                    () -> phraseIds(engine, text, "java search")
            );

            engine.createIndex(IndexDefinition.text(text)).join();
            assertEquals(Set.of(0L), phraseIds(engine, text, "java search"));
        } finally {
            analyzer.releaseBuild();
        }
    }

    @Test
    void phraseRequestUsesTheSnapshotCapturedBeforeQueryAnalysis() throws Exception {
        CountDownLatch queryEntered = new CountDownLatch(1);
        CountDownLatch releaseQuery = new CountDownLatch(1);
        AtomicBoolean blockQuery = new AtomicBoolean();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("blocked-phrase") && blockQuery.get()) {
                    queryEntered.countDown();
                    try {
                        if (!releaseQuery.await(5, TimeUnit.SECONDS)) {
                            throw new AssertionError("timed out releasing phrase query");
                        }
                    } catch (InterruptedException failure) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError("phrase query interrupted", failure);
                    }
                    return List.of(
                            new AnalyzedToken("java", 1),
                            new AnalyzedToken("search", 1)
                    );
                }
                return Analyzer.super.analyzeWithPositions(text);
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        Article original = new Article(0, "java search engine");
        Article reordered = new Article(0, "search java engine");

        try (SearchEngine<Long, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.add(original).join();
            blockQuery.set(true);
            CompletableFuture<SearchResult<Article>> result =
                    CompletableFuture.supplyAsync(() -> engine.search(
                            SearchRequest.of(SearchQueries.phrase(
                                    text,
                                    "blocked-phrase"
                            ))
                    ));

            assertTrue(queryEntered.await(5, TimeUnit.SECONDS));
            engine.update(reordered).join();
            releaseQuery.countDown();

            assertEquals(
                    List.of(original),
                    result.get(5, TimeUnit.SECONDS).hits().stream()
                            .map(hit -> hit.document())
                            .toList()
            );
            assertTrue(phraseIds(engine, text, "java search").isEmpty());
        } finally {
            releaseQuery.countDown();
        }
    }

    private static Set<Long> phraseIds(
            SearchEngine<Long, Article> engine,
            TextField<Article> text,
            String phrase
    ) {
        return engine.search(SearchRequest.of(
                        SearchQueries.phrase(text, phrase)))
                .hits()
                .stream()
                .map(hit -> hit.document().id())
                .collect(Collectors.toSet());
    }

    private record Article(long id, String body) {
    }

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
                    throw new IllegalStateException(
                            "index build was interrupted",
                            failure
                    );
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
