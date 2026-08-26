package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
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
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExecutionAccess;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class FuzzySearchEngineLifecycleTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);

    @Test
    void publishesReplayCorrectVocabularyAcrossDynamicIndexLifecycle()
            throws Exception {
        BlockingAnalyzer analyzer = new BlockingAnalyzer();
        TextField<Article> text = TextField.of(BODY, analyzer);
        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .textField(text)
                .build();

        try (SnapshotSearchEngine<Long, Article> engine =
                     new SnapshotSearchEngine<>(schema, List.of())) {
            engine.add(new Article(0, "restarant original")).join();
            List<Article> stable = new ArrayList<>();
            for (long id = 1; id < 100; id++) {
                stable.add(new Article(id, "stable common"));
            }
            engine.addAll(stable).join();

            assertThrows(
                    IllegalStateException.class,
                    () -> fuzzyIds(engine, text, "restaurant")
            );

            analyzer.blockNextIndexBuild();
            CompletableFuture<Void> creation =
                    engine.createIndex(IndexDefinition.text(text));
            assertTrue(analyzer.awaitBuildStart());

            engine.update(new Article(0, "unrelated updated")).join();
            engine.remove(1L).join();
            engine.add(new Article(1_000, "restuarant added")).join();

            analyzer.releaseBuild();
            creation.join();

            assertEquals(
                    Set.of(1_000L),
                    fuzzyIds(engine, text, "restaurant")
            );

            engine.updateAll(List.of(
                    new Article(0, "restaurant restored"),
                    new Article(2, "restarant bulk")
            )).join();
            assertEquals(
                    Set.of(0L, 2L, 1_000L),
                    fuzzyIds(engine, text, "restaurant")
            );
            assertEquals(
                    0L,
                    fuzzyHits(engine, text, "restaurant")
                            .getFirst()
                            .document()
                            .id()
            );

            engine.removeAll(List.of(2L, 1_000L)).join();
            assertEquals(Set.of(0L), fuzzyIds(engine, text, "restaurant"));

            engine.dropIndex(BODY.name()).join();
            assertThrows(
                    IllegalStateException.class,
                    () -> fuzzyIds(engine, text, "restaurant")
            );

            engine.createIndex(IndexDefinition.text(text)).join();
            assertEquals(Set.of(0L), fuzzyIds(engine, text, "restaurant"));
        } finally {
            analyzer.releaseBuild();
        }
    }

    @Test
    void immutableSnapshotsKeepTheirOwnFuzzyTruthAndScores() {
        TextField<Article> text = TextField.of(BODY, Analyzer.simple());
        Article typo = new Article(4, "restarant filler");
        Article reorderedTypo = new Article(4, "filler restarant");
        Article exact = new Article(4, "restaurant filler");
        SearchSnapshot<Article> oldSnapshot = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(text)))
                .add(4, typo);
        SearchSnapshot<Article> reorderedSnapshot = oldSnapshot.update(
                4,
                reorderedTypo
        );
        SearchSnapshot<Article> exactSnapshot = reorderedSnapshot.update(4, exact);
        SearchSnapshot<Article> removedSnapshot = exactSnapshot.remove(4);
        SearchRequest<Article> request = SearchRequest.of(
                SearchQueries.fuzzy(text, "restaurant")
        );

        List<SearchHit<Article>> oldHits = execute(oldSnapshot, request);
        List<SearchHit<Article>> reorderedHits = execute(reorderedSnapshot, request);
        List<SearchHit<Article>> exactHits = execute(exactSnapshot, request);

        assertEquals(List.of(typo), documents(oldHits));
        assertEquals(List.of(reorderedTypo), documents(reorderedHits));
        assertEquals(oldHits.getFirst().score(), reorderedHits.getFirst().score());
        assertEquals(List.of(exact), documents(exactHits));
        assertTrue(exactHits.getFirst().score() > oldHits.getFirst().score());
        assertTrue(execute(removedSnapshot, request).isEmpty());
        assertEquals(oldHits, execute(oldSnapshot, request));
    }

    @Test
    void fuzzyRequestUsesTheSnapshotCapturedBeforeQueryAnalysis()
            throws Exception {
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
                if (text.equals("blocked-fuzzy") && blockQuery.get()) {
                    queryEntered.countDown();
                    try {
                        if (!releaseQuery.await(5, TimeUnit.SECONDS)) {
                            throw new AssertionError(
                                    "timed out releasing fuzzy query");
                        }
                    } catch (InterruptedException failure) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError("fuzzy query interrupted", failure);
                    }
                    return List.of(new AnalyzedToken("restaurant", 1));
                }
                return Analyzer.super.analyzeWithPositions(text);
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        Article original = new Article(0, "restarant engine");
        Article changed = new Article(0, "unrelated engine");

        try (SearchEngine<Long, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.add(original).join();
            blockQuery.set(true);
            CompletableFuture<SearchResult<Article>> result =
                    CompletableFuture.supplyAsync(() -> engine.search(
                            SearchRequest.of(SearchQueries.fuzzy(
                                    text,
                                    "blocked-fuzzy"
                            ))
                    ));

            assertTrue(queryEntered.await(5, TimeUnit.SECONDS));
            engine.update(changed).join();
            releaseQuery.countDown();

            assertEquals(
                    List.of(original),
                    result.get(5, TimeUnit.SECONDS).hits().stream()
                            .map(SearchHit::document)
                            .toList()
            );
            assertTrue(fuzzyIds(engine, text, "restaurant").isEmpty());
        } finally {
            releaseQuery.countDown();
        }
    }

    @Test
    void fuzzyExecutionUsesTheSnapshotCapturedBeforeConcurrentPublication()
            throws Exception {
        TextField<Article> text = TextField.of(BODY, Analyzer.simple());
        Article original = new Article(0, "restarant engine");
        Article changed = new Article(0, "unrelated engine");
        CountDownLatch executionEntered = new CountDownLatch(1);
        CountDownLatch releaseExecution = new CountDownLatch(1);
        SearchRequest<Article> blocked = SearchRequest.<Article>builder()
                .query(SearchQueries.fuzzy(text, "restaurant"))
                .filter(article -> {
                    executionEntered.countDown();
                    try {
                        if (!releaseExecution.await(5, TimeUnit.SECONDS)) {
                            throw new AssertionError(
                                    "timed out releasing fuzzy execution");
                        }
                    } catch (InterruptedException failure) {
                        Thread.currentThread().interrupt();
                        throw new AssertionError(
                                "fuzzy execution interrupted",
                                failure
                        );
                    }
                    return true;
                })
                .build();

        try (SearchEngine<Long, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.add(original).join();
            CompletableFuture<SearchResult<Article>> result =
                    CompletableFuture.supplyAsync(() -> engine.search(blocked));

            assertTrue(executionEntered.await(5, TimeUnit.SECONDS));
            engine.update(changed).join();
            releaseExecution.countDown();

            assertEquals(
                    List.of(original),
                    result.get(5, TimeUnit.SECONDS).hits().stream()
                            .map(SearchHit::document)
                            .toList()
            );
            assertTrue(fuzzyIds(engine, text, "restaurant").isEmpty());
        } finally {
            releaseExecution.countDown();
        }
    }

    private static Set<Long> fuzzyIds(
            SearchEngine<Long, Article> engine,
            TextField<Article> text,
            String term
    ) {
        return fuzzyHits(engine, text, term).stream()
                .map(hit -> hit.document().id())
                .collect(Collectors.toSet());
    }

    private static List<SearchHit<Article>> fuzzyHits(
            SearchEngine<Long, Article> engine,
            TextField<Article> text,
            String term
    ) {
        return engine.search(SearchRequest.of(SearchQueries.fuzzy(text, term)))
                .hits();
    }

    private static List<SearchHit<Article>> execute(
            SearchSnapshot<Article> snapshot,
            SearchRequest<Article> request
    ) {
        return SearchExecutionAccess.search(
                snapshot,
                request,
                new CandidatePlanner<>()
        ).hits();
    }

    private static List<Article> documents(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    private record Article(long id, String body) {
    }

    private static final class BlockingAnalyzer implements Analyzer {
        private final AtomicBoolean armed = new AtomicBoolean();
        private volatile CountDownLatch started = new CountDownLatch(0);
        private volatile CountDownLatch release = new CountDownLatch(0);

        @Override
        public List<Token> analyze(String text) {
            if (Thread.currentThread().getName().startsWith(
                    "snapshot-index-builder-")
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
