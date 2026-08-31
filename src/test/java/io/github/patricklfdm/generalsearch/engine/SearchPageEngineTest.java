package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.OptionalLong;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.engine.exception.SearchCursorException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchAfterCursor;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageResult;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import io.github.patricklfdm.generalsearch.search.TotalHitsMode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

class SearchPageEngineTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void disabledFirstPageIsBitForBitOrdinarySearch() {
        try (SearchEngine<Integer, Document> engine = populatedEngine(TEXT)) {
            SearchRequest<Document> search = SearchRequest.<Document>builder()
                    .query(SearchQueries.text(TEXT, "java"))
                    .limit(2)
                    .build();

            SearchResult<Document> ordinary = engine.search(search);
            SearchPageResult<Document> page = engine.search(
                    SearchPageRequest.builder(search).build());

            assertHitIdentityAndBits(ordinary.hits(), page.hits());
            assertTrue(page.totalHits().isEmpty());
            assertTrue(page.nextCursor().isEmpty(),
                    "built-in cursor emission starts in Phase 3");
        }
    }

    @Test
    void exactTotalCountsFullQueryAndFilterMatchesBeforeLimit() {
        AtomicInteger filterEvaluations = new AtomicInteger();
        Query<Document> eligible = document -> {
            filterEvaluations.incrementAndGet();
            return document.category().equals("eligible");
        };
        try (SearchEngine<Integer, Document> engine = populatedEngine(TEXT)) {
            SearchRequest<Document> search = SearchRequest.<Document>builder()
                    .query(SearchQueries.text(TEXT, "java"))
                    .filter(eligible)
                    .limit(2)
                    .build();

            SearchPageResult<Document> exact = engine.search(SearchPageRequest
                    .builder(search)
                    .totalHits(TotalHitsMode.EXACT)
                    .build());

            assertEquals(2, exact.hits().size());
            assertEquals(OptionalLong.of(3L), exact.totalHits());
            assertEquals(4, filterEvaluations.get(),
                    "exact totals must not run the filter a second time");

            filterEvaluations.set(0);
            SearchPageResult<Document> disabled = engine.search(
                    SearchPageRequest.builder(search).build());
            assertHitIdentityAndBits(exact.hits(), disabled.hits());
            assertEquals(4, filterEvaluations.get());
            assertTrue(disabled.totalHits().isEmpty());
        }
    }

    @Test
    void exactTotalReportsZeroForNoMatches() {
        try (SearchEngine<Integer, Document> engine = populatedEngine(TEXT)) {
            SearchRequest<Document> search = SearchRequest.of(
                    SearchQueries.text(TEXT, "absent"));

            SearchPageResult<Document> result = engine.search(SearchPageRequest
                    .builder(search)
                    .totalHits(TotalHitsMode.EXACT)
                    .build());

            assertTrue(result.hits().isEmpty());
            assertTrue(result.nextCursor().isEmpty());
            assertEquals(OptionalLong.of(0L), result.totalHits());
        }
    }

    @Test
    void firstPageMatrixPreservesOrdinaryHitsAndExactFullCount() {
        List<SearchQuery<Document>> queries = List.of(
                SearchQueries.text(TEXT, "java"),
                SearchQueries.text(TEXT, "absent"),
                SearchQueries.phrase(TEXT, "java search"),
                SearchQueries.phrase(TEXT, "java search", 2),
                SearchQueries.fuzzy(TEXT, "jvaa"),
                SearchQueries.<Document>bool()
                        .must(SearchQueries.text(TEXT, "java"))
                        .should(SearchQueries.phrase(TEXT, "java search", 2)
                                .boost(1.25))
                        .minimumShouldMatch(0)
                        .build()
                        .boost(1.5)
        );
        List<Bm25Config> bm25Configs = List.of(
                Bm25Config.DEFAULT,
                new Bm25Config(1.5, 0.55)
        );
        List<Integer> limits = List.of(1, 2, 10, 100);
        try (SearchEngine<Integer, Document> engine = populatedEngine(TEXT)) {
            for (SearchQuery<Document> query : queries) {
                for (Bm25Config bm25 : bm25Configs) {
                    for (boolean filtered : List.of(false, true)) {
                        SearchRequest.Builder<Document> exhaustiveBuilder =
                                SearchRequest.<Document>builder()
                                        .query(query)
                                        .bm25(bm25)
                                        .limit(100);
                        if (filtered) {
                            exhaustiveBuilder.filter(document ->
                                    document.category().equals("eligible"));
                        }
                        List<SearchHit<Document>> exhaustive = engine.search(
                                exhaustiveBuilder.build()).hits();

                        for (int limit : limits) {
                            SearchRequest.Builder<Document> limitedBuilder =
                                    SearchRequest.<Document>builder()
                                            .query(query)
                                            .bm25(bm25)
                                            .limit(limit);
                            if (filtered) {
                                limitedBuilder.filter(document ->
                                        document.category().equals("eligible"));
                            }
                            SearchRequest<Document> limited =
                                    limitedBuilder.build();
                            List<SearchHit<Document>> expected = exhaustive.subList(
                                    0,
                                    Math.min(limit, exhaustive.size())
                            );
                            SearchPageResult<Document> disabled = engine.search(
                                    SearchPageRequest.builder(limited).build()
                            );
                            SearchPageResult<Document> exact = engine.search(
                                    SearchPageRequest.builder(limited)
                                            .totalHits(TotalHitsMode.EXACT)
                                            .build()
                            );

                            assertHitIdentityAndBits(expected, disabled.hits());
                            assertHitIdentityAndBits(expected, exact.hits());
                            assertTrue(disabled.totalHits().isEmpty());
                            assertEquals(
                                    OptionalLong.of(exhaustive.size()),
                                    exact.totalHits()
                            );
                        }
                    }
                }
            }
        }
    }

    @Test
    void openFirstPagePreservesOrdinaryPlanningFailure() {
        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .textField(TEXT)
                .build()) {
            SearchRequest<Document> search = SearchRequest.of(
                    SearchQueries.text(TEXT, "java"));

            RuntimeException ordinary = assertThrows(
                    RuntimeException.class,
                    () -> engine.search(search)
            );
            RuntimeException paged = assertThrows(
                    RuntimeException.class,
                    () -> engine.search(SearchPageRequest.builder(search).build())
            );

            assertEquals(ordinary.getClass(), paged.getClass());
            assertEquals(ordinary.getMessage(), paged.getMessage());
        }
    }

    @Test
    void phase2RejectsForeignCursorAfterLifecycleAdmission() {
        SearchEngine<Integer, Document> engine = populatedEngine(TEXT);
        SearchPageRequest<Document> continuation = SearchPageRequest
                .builder(SearchRequest.of(SearchQueries.text(TEXT, "java")))
                .after(new ForeignCursor())
                .build();
        try {
            SearchCursorException unsupported = assertThrows(
                    SearchCursorException.class,
                    () -> engine.search(continuation)
            );
            assertEquals(
                    SearchCursorException.Reason.UNSUPPORTED_CURSOR,
                    unsupported.reason()
            );

            engine.close();
            EngineRejectedExecutionException closed = assertThrows(
                    EngineRejectedExecutionException.class,
                    () -> engine.search(continuation)
            );
            assertEquals(
                    EngineRejectedExecutionException.Reason.CLOSED,
                    closed.reason()
            );
        } finally {
            engine.close();
        }
    }

    @Test
    @Timeout(20)
    void admittedFirstPageCompletesFromCapturedSnapshotAcrossMutationAndClose()
            throws Exception {
        BlockingAnalyzer analyzer = new BlockingAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .field(CATEGORY)
                .index(IndexDefinition.text(text))
                .build();
        Document original = new Document(1, "java original", "eligible");
        Document added = new Document(2, "java added", "eligible");
        try {
            engine.add(original).join();
            analyzer.block.set(true);
            SearchPageRequest<Document> request = SearchPageRequest
                    .builder(SearchRequest.of(
                            SearchQueries.text(text, "blocked-query")))
                    .totalHits(TotalHitsMode.EXACT)
                    .build();
            CompletableFuture<SearchPageResult<Document>> pending =
                    CompletableFuture.supplyAsync(() -> engine.search(request));
            assertTrue(analyzer.entered.await(5, TimeUnit.SECONDS));

            engine.add(added).join();
            CompletableFuture.runAsync(engine::close).get(5, TimeUnit.SECONDS);
            analyzer.release.countDown();

            SearchPageResult<Document> admitted = pending.get(5, TimeUnit.SECONDS);
            assertEquals(List.of(original), admitted.hits().stream()
                    .map(SearchHit::document)
                    .toList());
            assertEquals(OptionalLong.of(1L), admitted.totalHits());
        } finally {
            analyzer.release.countDown();
            engine.close();
        }
    }

    private static SearchEngine<Integer, Document> populatedEngine(
            TextField<Document> text
    ) {
        SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .field(CATEGORY)
                .index(IndexDefinition.text(text))
                .build();
        engine.addAll(List.of(
                new Document(1, "java search", "eligible"),
                new Document(2, "java java", "eligible"),
                new Document(3, "java engine", "other"),
                new Document(4, "search only", "eligible"),
                new Document(5, "java stable", "eligible")
        )).join();
        return engine;
    }

    private static <T> void assertHitIdentityAndBits(
            List<SearchHit<T>> expected,
            List<SearchHit<T>> observed
    ) {
        assertEquals(expected.size(), observed.size());
        for (int index = 0; index < expected.size(); index++) {
            assertSame(
                    expected.get(index).document(),
                    observed.get(index).document()
            );
            assertEquals(
                    Double.doubleToRawLongBits(expected.get(index).score()),
                    Double.doubleToRawLongBits(observed.get(index).score())
            );
        }
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("timed out waiting for query release");
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new AssertionError("query analysis interrupted", interrupted);
        }
    }

    private record Document(int id, String body, String category) {
    }

    private static final class ForeignCursor implements SearchAfterCursor {
    }

    private static final class BlockingAnalyzer implements Analyzer {
        private final AtomicBoolean block = new AtomicBoolean();
        private final CountDownLatch entered = new CountDownLatch(1);
        private final CountDownLatch release = new CountDownLatch(1);

        @Override
        public List<Token> analyze(String text) {
            return Analyzer.simple().analyze(text);
        }

        @Override
        public List<AnalyzedToken> analyzeWithPositions(String text) {
            if (text.equals("blocked-query") && block.get()) {
                entered.countDown();
                await(release);
                return List.of(new AnalyzedToken("java", 1));
            }
            return Analyzer.super.analyzeWithPositions(text);
        }
    }
}
