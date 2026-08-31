package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.OptionalLong;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.engine.exception.SearchCursorException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

class SearchAfterEngineTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> GROUP =
            Field.of("group", String.class, Document::group);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void denseTieWalkUsesHiddenInsertionOrderAcrossEveryPageSize() {
        List<Document> documents = List.of(
                document(90, "tie", "eligible"),
                document(10, "tie", "eligible"),
                document(70, "tie", "eligible"),
                document(20, "tie", "eligible"),
                document(60, "tie", "eligible"),
                document(30, "tie", "eligible"),
                document(50, "tie", "eligible"),
                document(40, "tie", "eligible")
        );
        try (SearchEngine<Integer, Document> engine = engine(TEXT, documents)) {
            SearchQuery<Document> query = SearchQueries.text(TEXT, "tie");
            for (int limit = 1; limit <= documents.size() + 1; limit++) {
                Walk<Document> walk = walk(
                        engine,
                        request(query, limit, false, Bm25Config.DEFAULT),
                        TotalHitsMode.EXACT
                );

                assertEquals(documents, walk.hits().stream()
                        .map(SearchHit::document)
                        .toList());
                assertEquals(OptionalLong.of(documents.size()), walk.totalHits());
            }
        }
    }

    @Test
    void queryFilterBm25AndLimitMatrixMatchesOrdinaryExhaustiveOrder() {
        List<Document> documents = new ArrayList<>();
        for (int id = 0; id < 24; id++) {
            String body = switch (id % 4) {
                case 0 -> "alpha beta beta";
                case 1 -> "alpha beta";
                case 2 -> "alpha gamma";
                default -> "unrelated stable";
            };
            documents.add(document(
                    1_000 - id,
                    body,
                    id % 2 == 0 ? "eligible" : "other"
            ));
        }
        List<SearchQuery<Document>> queries = List.of(
                SearchQueries.text(TEXT, "alpha"),
                SearchQueries.phrase(TEXT, "alpha beta"),
                SearchQueries.phrase(TEXT, "alpha beta", 2),
                SearchQueries.fuzzy(TEXT, "alhpa"),
                SearchQueries.text(TEXT, "alpha")
                        .boost(Double.MIN_VALUE)
                        .boost(Double.MAX_VALUE),
                SearchQueries.<Document>bool()
                        .must(SearchQueries.text(TEXT, "alpha"))
                        .should(SearchQueries.text(TEXT, "beta").boost(1.25))
                        .minimumShouldMatch(0)
                        .build()
                        .boost(1.5)
        );
        List<Bm25Config> bm25Configs = List.of(
                Bm25Config.DEFAULT,
                new Bm25Config(1.6, 0.45)
        );
        try (SearchEngine<Integer, Document> engine = engine(TEXT, documents)) {
            for (SearchQuery<Document> query : queries) {
                for (Bm25Config bm25 : bm25Configs) {
                    for (boolean filtered : List.of(false, true)) {
                        List<SearchHit<Document>> expected = engine.search(
                                request(query, 100, filtered, bm25)).hits();
                        for (int limit : List.of(1, 2, 5, 50)) {
                            SearchRequest<Document> paged = request(
                                    query,
                                    limit,
                                    filtered,
                                    bm25
                            );
                            Walk<Document> exact = walk(
                                    engine,
                                    paged,
                                    TotalHitsMode.EXACT
                            );
                            Walk<Document> disabled = walk(
                                    engine,
                                    paged,
                                    TotalHitsMode.DISABLED
                            );

                            assertHitIdentityAndBits(expected, exact.hits());
                            assertHitIdentityAndBits(expected, disabled.hits());
                            assertEquals(
                                    OptionalLong.of(expected.size()),
                                    exact.totalHits()
                            );
                            assertTrue(disabled.totalHits().isEmpty());
                        }
                    }
                }
            }
        }
    }

    @Test
    void cursorReuseBranchesDeterministicallyAndAllowsTotalModeChange() {
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible"),
                document(3, "tie", "eligible"),
                document(4, "tie", "eligible"),
                document(5, "tie", "eligible")
        );
        try (SearchEngine<Integer, Document> engine = engine(TEXT, documents)) {
            SearchRequest<Document> request = request(
                    SearchQueries.text(TEXT, "tie"),
                    2,
                    false,
                    Bm25Config.DEFAULT
            );
            SearchPageResult<Document> first = engine.search(
                    SearchPageRequest.builder(request).build());
            SearchAfterCursor cursor = first.nextCursor().orElseThrow();

            SearchPageResult<Document> exactBranch = engine.search(
                    SearchPageRequest.builder(request)
                            .after(cursor)
                            .totalHits(TotalHitsMode.EXACT)
                            .build()
            );
            SearchPageResult<Document> disabledBranch = engine.search(
                    SearchPageRequest.builder(request)
                            .after(cursor)
                            .build()
            );
            SearchPageResult<Document> repeatedExact = engine.search(
                    SearchPageRequest.builder(request)
                            .after(cursor)
                            .totalHits(TotalHitsMode.EXACT)
                            .build()
            );

            assertHitIdentityAndBits(exactBranch.hits(), disabledBranch.hits());
            assertHitIdentityAndBits(exactBranch.hits(), repeatedExact.hits());
            assertEquals(OptionalLong.of(5L), exactBranch.totalHits());
            assertEquals(exactBranch.totalHits(), repeatedExact.totalHits());
            assertTrue(disabledBranch.totalHits().isEmpty());
            assertTrue(exactBranch.nextCursor().isPresent());
            assertTrue(disabledBranch.nextCursor().isPresent());
        }
    }

    @Test
    void exactContinuationCountsFullMatchesWithoutASecondFilterPass() {
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible"),
                document(3, "tie", "eligible"),
                document(4, "tie", "other"),
                document(5, "tie", "eligible")
        );
        AtomicInteger filterEvaluations = new AtomicInteger();
        try (SearchEngine<Integer, Document> engine = engine(TEXT, documents)) {
            SearchRequest<Document> request = SearchRequest
                    .<Document>builder()
                    .query(SearchQueries.text(TEXT, "tie"))
                    .filter(document -> {
                        filterEvaluations.incrementAndGet();
                        return document.group().equals("eligible");
                    })
                    .limit(2)
                    .build();
            SearchPageResult<Document> first = engine.search(
                    SearchPageRequest.builder(request)
                            .totalHits(TotalHitsMode.EXACT)
                            .build()
            );
            assertEquals(OptionalLong.of(4L), first.totalHits());
            assertEquals(5, filterEvaluations.get());

            filterEvaluations.set(0);
            SearchPageResult<Document> second = engine.search(
                    SearchPageRequest.builder(request)
                            .after(first.nextCursor().orElseThrow())
                            .totalHits(TotalHitsMode.EXACT)
                            .build()
            );
            assertEquals(OptionalLong.of(4L), second.totalHits());
            assertEquals(5, filterEvaluations.get());
            assertEquals(List.of(documents.get(2), documents.get(4)),
                    second.hits().stream().map(SearchHit::document).toList());
            assertTrue(second.nextCursor().isEmpty());
        }
    }

    @Test
    void cursorValidationUsesFrozenReasonPrecedenceBeforePlanning() {
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible"),
                document(3, "tie", "eligible")
        );
        try (SearchEngine<Integer, Document> first = engine(TEXT, documents);
             SearchEngine<Integer, Document> second = engine(TEXT, documents)) {
            SearchQuery<Document> query = SearchQueries.text(TEXT, "tie");
            SearchRequest<Document> request = request(
                    query,
                    1,
                    false,
                    Bm25Config.DEFAULT
            );
            SearchAfterCursor cursor = first.search(
                    SearchPageRequest.builder(request).build())
                    .nextCursor()
                    .orElseThrow();
            SearchRequest<Document> equivalentRequest = request(
                    query,
                    1,
                    false,
                    Bm25Config.DEFAULT
            );

            assertReason(
                    SearchCursorException.Reason.UNSUPPORTED_CURSOR,
                    () -> first.search(SearchPageRequest
                            .builder(equivalentRequest)
                            .after(new ForeignCursor())
                            .build())
            );
            assertReason(
                    SearchCursorException.Reason.DIFFERENT_ENGINE,
                    () -> second.search(SearchPageRequest
                            .builder(equivalentRequest)
                            .after(cursor)
                            .build())
            );
            assertReason(
                    SearchCursorException.Reason.DIFFERENT_REQUEST,
                    () -> first.search(SearchPageRequest
                            .builder(equivalentRequest)
                            .after(cursor)
                            .build())
            );

            first.add(document(4, "tie", "eligible")).join();
            assertReason(
                    SearchCursorException.Reason.DIFFERENT_REQUEST,
                    () -> first.search(SearchPageRequest
                            .builder(equivalentRequest)
                            .after(cursor)
                            .build())
            );
            assertReason(
                    SearchCursorException.Reason.STALE_SNAPSHOT,
                    () -> first.search(SearchPageRequest
                            .builder(request)
                            .after(cursor)
                            .build())
            );

            Field<Document, String> missingBody = Field.of(
                    "missingBody",
                    String.class,
                    Document::body
            );
            TextField<Document> missing = TextField.of(
                    missingBody,
                    Analyzer.simple()
            );
            SearchRequest<Document> invalid = SearchRequest.of(
                    SearchQueries.text(missing, "tie"));
            assertReason(
                    SearchCursorException.Reason.DIFFERENT_REQUEST,
                    () -> first.search(SearchPageRequest
                            .builder(invalid)
                            .after(cursor)
                            .build())
            );
        }
    }

    @Test
    void failedPublicationLeavesCursorValidAndSuccessfulPublicationStalesIt() {
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible"),
                document(3, "tie", "eligible")
        );
        try (SearchEngine<Integer, Document> engine = engine(TEXT, documents)) {
            SearchRequest<Document> request = request(
                    SearchQueries.text(TEXT, "tie"),
                    1,
                    false,
                    Bm25Config.DEFAULT
            );
            SearchAfterCursor cursor = engine.search(
                    SearchPageRequest.builder(request).build())
                    .nextCursor()
                    .orElseThrow();

            assertThrows(
                    CompletionException.class,
                    () -> engine.update(document(
                            999,
                            "tie",
                            "eligible"
                    )).join()
            );
            SearchPageResult<Document> accepted = engine.search(
                    SearchPageRequest.builder(request)
                            .after(cursor)
                            .build()
            );
            assertEquals(List.of(documents.get(1)), accepted.hits().stream()
                    .map(SearchHit::document)
                    .toList());

            engine.add(document(4, "tie added", "eligible")).join();
            assertReason(
                    SearchCursorException.Reason.STALE_SNAPSHOT,
                    () -> engine.search(SearchPageRequest.builder(request)
                            .after(cursor)
                            .build())
            );
        }
    }

    @Test
    void closedAdmissionWinsOverBuiltInCursorValidation() {
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible")
        );
        SearchEngine<Integer, Document> engine = engine(TEXT, documents);
        SearchRequest<Document> request = request(
                SearchQueries.text(TEXT, "tie"),
                1,
                false,
                Bm25Config.DEFAULT
        );
        SearchAfterCursor cursor = engine.search(
                SearchPageRequest.builder(request).build())
                .nextCursor()
                .orElseThrow();
        engine.close();

        EngineRejectedExecutionException rejected = assertThrows(
                EngineRejectedExecutionException.class,
                () -> engine.search(SearchPageRequest.builder(request)
                        .after(cursor)
                        .build())
        );
        assertEquals(
                EngineRejectedExecutionException.Reason.CLOSED,
                rejected.reason()
        );
    }

    @Test
    @Timeout(20)
    void admittedContinuationCompletesFromCapturedSnapshotAcrossMutationAndClose()
            throws Exception {
        BlockingAnalyzer analyzer = new BlockingAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible"),
                document(3, "tie", "eligible")
        );
        SearchEngine<Integer, Document> engine = engine(text, documents);
        try {
            SearchRequest<Document> request = request(
                    SearchQueries.text(text, "tie"),
                    1,
                    false,
                    Bm25Config.DEFAULT
            );
            SearchAfterCursor cursor = engine.search(
                    SearchPageRequest.builder(request).build())
                    .nextCursor()
                    .orElseThrow();
            analyzer.block.set(true);
            CompletableFuture<SearchPageResult<Document>> pending =
                    CompletableFuture.supplyAsync(() -> engine.search(
                            SearchPageRequest.builder(request)
                                    .after(cursor)
                                    .totalHits(TotalHitsMode.EXACT)
                                    .build()
                    ));
            assertTrue(analyzer.entered.await(5, TimeUnit.SECONDS));

            engine.add(document(4, "tie added", "eligible")).join();
            CompletableFuture.runAsync(engine::close).get(5, TimeUnit.SECONDS);
            analyzer.release.countDown();

            SearchPageResult<Document> admitted = pending.get(5, TimeUnit.SECONDS);
            assertEquals(List.of(documents.get(1)), admitted.hits().stream()
                    .map(SearchHit::document)
                    .toList());
            assertEquals(OptionalLong.of(3L), admitted.totalHits());
            assertTrue(admitted.nextCursor().isPresent());
        } finally {
            analyzer.release.countDown();
            engine.close();
        }
    }

    @Test
    void builtInCursorIsPrivateConstantSizedAndRetainsOnlyOwnerAndRequest() {
        List<Document> documents = List.of(
                document(1, "tie", "eligible"),
                document(2, "tie", "eligible")
        );
        try (SearchEngine<Integer, Document> engine = engine(TEXT, documents)) {
            SearchRequest<Document> request = request(
                    SearchQueries.text(TEXT, "tie"),
                    1,
                    false,
                    Bm25Config.DEFAULT
            );
            SearchAfterCursor cursor = engine.search(
                    SearchPageRequest.builder(request).build())
                    .nextCursor()
                    .orElseThrow();

            Class<?> implementation = cursor.getClass();
            assertFalse(Modifier.isPublic(implementation.getModifiers()));
            assertEquals(0, Arrays.stream(implementation.getDeclaredMethods())
                    .filter(method -> Modifier.isPublic(method.getModifiers()))
                    .count());
            assertEquals(5, Arrays.stream(implementation.getDeclaredFields())
                    .filter(field -> !Modifier.isStatic(field.getModifiers()))
                    .count());
            assertEquals(3, Arrays.stream(implementation.getDeclaredFields())
                    .filter(field -> !Modifier.isStatic(field.getModifiers()))
                    .filter(field -> field.getType().isPrimitive())
                    .count());

            Set<Object> references =
                    V33TestReference.directReferenceValues(cursor);
            assertEquals(2, references.size());
            assertTrue(references.contains(request));
            assertFalse(references.contains(engine));
            for (Document document : documents) {
                assertFalse(references.contains(document));
            }
        }
    }

    private static Walk<Document> walk(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request,
            TotalHitsMode mode
    ) {
        List<SearchHit<Document>> collected = new ArrayList<>();
        SearchAfterCursor after = null;
        OptionalLong totalHits = OptionalLong.empty();
        int pageCount = 0;
        while (true) {
            SearchPageRequest.Builder<Document> builder =
                    SearchPageRequest.builder(request).totalHits(mode);
            if (after != null) {
                builder.after(after);
            }
            SearchPageResult<Document> page = engine.search(builder.build());
            collected.addAll(page.hits());
            if (mode == TotalHitsMode.EXACT) {
                if (totalHits.isPresent()) {
                    assertEquals(totalHits, page.totalHits());
                } else {
                    totalHits = page.totalHits();
                }
            } else {
                assertTrue(page.totalHits().isEmpty());
            }
            pageCount++;
            if (page.nextCursor().isEmpty()) {
                return new Walk<>(collected, totalHits, pageCount);
            }
            assertEquals(request.limit(), page.hits().size());
            after = page.nextCursor().orElseThrow();
            assertTrue(pageCount <= 1_000, "cursor walk did not terminate");
        }
    }

    private static SearchRequest<Document> request(
            SearchQuery<Document> query,
            int limit,
            boolean filtered,
            Bm25Config bm25
    ) {
        SearchRequest.Builder<Document> builder = SearchRequest
                .<Document>builder()
                .query(query)
                .limit(limit)
                .bm25(bm25);
        if (filtered) {
            builder.filter(document -> document.group().equals("eligible"));
        }
        return builder.build();
    }

    private static SearchEngine<Integer, Document> engine(
            TextField<Document> text,
            List<Document> documents
    ) {
        SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .field(GROUP)
                .index(IndexDefinition.text(text))
                .build();
        engine.addAll(documents).join();
        return engine;
    }

    private static Document document(int id, String body, String group) {
        return new Document(id, body, group);
    }

    private static void assertReason(
            SearchCursorException.Reason expected,
            Runnable invocation
    ) {
        SearchCursorException rejected = assertThrows(
                SearchCursorException.class,
                invocation::run
        );
        assertEquals(expected, rejected.reason());
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

    private record Document(int id, String body, String group) {
    }

    private record Walk<T>(
            List<SearchHit<T>> hits,
            OptionalLong totalHits,
            int pageCount
    ) {
        private Walk {
            hits = List.copyOf(hits);
        }
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
            if (text.equals("tie") && block.get()) {
                entered.countDown();
                await(release);
            }
            return Analyzer.super.analyzeWithPositions(text);
        }
    }
}
