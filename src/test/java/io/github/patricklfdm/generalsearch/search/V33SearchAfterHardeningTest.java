package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.OptionalLong;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.engine.exception.SearchCursorException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

class V33SearchAfterHardeningTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> GROUP =
            Field.of("group", String.class, Document::group);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    @Timeout(30)
    void everySuccessfulPublicationKindStalesEarlierCursor() {
        for (PublicationCase publication : successfulPublicationCases()) {
            try (SearchEngine<Integer, Document> engine = engine(
                    TEXT,
                    publication.groupIndexed()
            )) {
                SearchRequest<Document> request = request(TEXT, 1);
                SearchAfterCursor cursor = firstCursor(engine, request);
                long before = engine.metrics().snapshotVersion();

                publication.action().publish(engine);

                assertTrue(
                        engine.metrics().snapshotVersion() > before,
                        publication.name()
                );
                assertStale(engine, request, cursor, publication.name());
            }
        }
    }

    @Test
    @Timeout(30)
    void everyPublicationKindAfterCapturePreservesTheAdmittedSnapshot()
            throws Exception {
        for (PublicationCase publication : successfulPublicationCases()) {
            BranchGateAnalyzer analyzer = new BranchGateAnalyzer();
            TextField<Document> text = TextField.of(BODY, analyzer);
            try (SearchEngine<Integer, Document> engine = engine(
                    text,
                    publication.groupIndexed()
            )) {
                SearchRequest<Document> request = request(text, 2);
                SearchAfterCursor cursor = firstCursor(engine, request);
                SearchPageResult<Document> expected = continuation(
                        engine,
                        request,
                        cursor,
                        TotalHitsMode.EXACT
                );
                long before = engine.metrics().snapshotVersion();

                analyzer.blockNextQueries(1);
                CompletableFuture<SearchPageResult<Document>> admitted = branch(
                        engine,
                        request,
                        cursor,
                        TotalHitsMode.EXACT
                );
                assertTrue(analyzer.awaitEntered(), publication.name());
                publication.action().publish(engine);
                assertTrue(
                        engine.metrics().snapshotVersion() > before,
                        publication.name()
                );
                analyzer.release();

                SearchPageResult<Document> observed = admitted.get(
                        5,
                        TimeUnit.SECONDS
                );
                assertHits(expected.hits(), observed.hits());
                assertEquals(OptionalLong.of(6L), observed.totalHits());
                assertEquals(
                        expected.nextCursor().isPresent(),
                        observed.nextCursor().isPresent(),
                        publication.name()
                );
                assertStale(engine, request, cursor, publication.name());
            } finally {
                analyzer.release();
            }
        }
    }

    @Test
    @Timeout(30)
    void failedAndNonPublishingWorkLeavesCursorValid() {
        List<NonPublicationCase> cases = List.of(
                new NonPublicationCase("duplicate add", false, true, engine ->
                        engine.add(document(1, "gate duplicate")).join()),
                new NonPublicationCase("missing update", false, true, engine ->
                        engine.update(document(999, "gate missing")).join()),
                new NonPublicationCase("failed bulk add", false, true, engine ->
                        engine.addAll(List.of(
                                document(100, "gate new"),
                                document(1, "gate duplicate")
                        )).join()),
                new NonPublicationCase("failed bulk update", false, true, engine ->
                        engine.updateAll(List.of(
                                document(1, "gate changed"),
                                document(999, "gate missing")
                        )).join()),
                new NonPublicationCase("duplicate dynamic create", true, true,
                        engine -> engine.createIndex(
                                IndexDefinition.equality(GROUP)).join()),
                new NonPublicationCase("idempotent missing-index drop", false, false,
                        engine -> engine.dropIndex(GROUP.name()).join())
        );

        for (NonPublicationCase nonPublication : cases) {
            try (SearchEngine<Integer, Document> engine = engine(
                    TEXT,
                    nonPublication.groupIndexed()
            )) {
                SearchRequest<Document> request = request(TEXT, 1);
                SearchAfterCursor cursor = firstCursor(engine, request);
                long before = engine.metrics().snapshotVersion();

                if (nonPublication.fails()) {
                    assertThrows(
                            CompletionException.class,
                            () -> nonPublication.action().publish(engine),
                            nonPublication.name()
                    );
                } else {
                    nonPublication.action().publish(engine);
                }

                assertEquals(
                        before,
                        engine.metrics().snapshotVersion(),
                        nonPublication.name()
                );
                SearchPageResult<Document> accepted = continuation(
                        engine,
                        request,
                        cursor,
                        TotalHitsMode.EXACT
                );
                assertEquals(OptionalLong.of(6L), accepted.totalHits());
                assertEquals(1, accepted.hits().size());
            }
        }
    }

    @Test
    @Timeout(30)
    void admittedBranchesReuseOneCursorWhileWriterPublishesAndMakesProgress()
            throws Exception {
        BranchGateAnalyzer analyzer = new BranchGateAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        try (SearchEngine<Integer, Document> engine = engine(text, false)) {
            SearchRequest<Document> request = request(text, 2);
            SearchAfterCursor cursor = firstCursor(engine, request);
            SearchPageResult<Document> expected = continuation(
                    engine,
                    request,
                    cursor,
                    TotalHitsMode.EXACT
            );
            long before = engine.metrics().snapshotVersion();

            analyzer.blockNextQueries(3);
            List<CompletableFuture<SearchPageResult<Document>>> branches = List.of(
                    branch(engine, request, cursor, TotalHitsMode.EXACT),
                    branch(engine, request, cursor, TotalHitsMode.DISABLED),
                    branch(engine, request, cursor, TotalHitsMode.EXACT)
            );
            assertTrue(analyzer.awaitEntered());

            engine.update(document(6, "gate writer publication")).get(
                    5,
                    TimeUnit.SECONDS
            );
            assertTrue(engine.metrics().snapshotVersion() > before);
            assertEquals(0, engine.metrics().writerQueueDepth());
            analyzer.release();

            SearchPageResult<Document> exactOne = branches.get(0).get(
                    5,
                    TimeUnit.SECONDS
            );
            SearchPageResult<Document> disabled = branches.get(1).get(
                    5,
                    TimeUnit.SECONDS
            );
            SearchPageResult<Document> exactTwo = branches.get(2).get(
                    5,
                    TimeUnit.SECONDS
            );
            assertHits(expected.hits(), exactOne.hits());
            assertHits(expected.hits(), disabled.hits());
            assertHits(expected.hits(), exactTwo.hits());
            assertEquals(OptionalLong.of(6L), exactOne.totalHits());
            assertTrue(disabled.totalHits().isEmpty());
            assertEquals(OptionalLong.of(6L), exactTwo.totalHits());
            assertStale(engine, request, cursor, "post-capture writer publication");
        } finally {
            analyzer.release();
        }
    }

    @Test
    @Timeout(30)
    void oneHundredThousandLiveCursorsCreateNoEngineRegistryOrWriterDependency() {
        try (SearchEngine<Integer, Document> engine = engine(TEXT, false)) {
            SearchRequest<Document> request = request(TEXT, 1);
            long version = engine.metrics().snapshotVersion();
            int documentCount = engine.metrics().documentCount();
            int indexCount = engine.metrics().registeredIndexCount();
            List<SearchAfterCursor> retained = new ArrayList<>(100_000);

            for (int cursor = 0; cursor < 100_000; cursor++) {
                retained.add(firstCursor(engine, request));
            }

            assertEquals(100_000, retained.size());
            assertEquals(version, engine.metrics().snapshotVersion());
            assertEquals(documentCount, engine.metrics().documentCount());
            assertEquals(indexCount, engine.metrics().registeredIndexCount());
            assertEquals(0, engine.metrics().writerQueueDepth());
            assertCursorShape(retained.getFirst(), request, engine);
            assertCursorShape(retained.get(999), request, engine);
            assertCursorShape(retained.getLast(), request, engine);

            engine.update(document(6, "gate retained cursor writer")).join();
            assertEquals(0, engine.metrics().writerQueueDepth());
            assertStale(engine, request, retained.getFirst(), "first retained cursor");
            assertStale(engine, request, retained.get(999), "1,000th retained cursor");
            assertStale(engine, request, retained.getLast(), "100,000th retained cursor");

            retained.clear();
            assertTrue(retained.isEmpty());
        }
    }

    private static CompletableFuture<SearchPageResult<Document>> branch(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request,
            SearchAfterCursor cursor,
            TotalHitsMode mode
    ) {
        return CompletableFuture.supplyAsync(() -> continuation(
                engine,
                request,
                cursor,
                mode
        ));
    }

    private static SearchAfterCursor firstCursor(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request
    ) {
        return engine.search(SearchPageRequest.builder(request).build())
                .nextCursor()
                .orElseThrow();
    }

    private static SearchPageResult<Document> continuation(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request,
            SearchAfterCursor cursor,
            TotalHitsMode mode
    ) {
        return engine.search(SearchPageRequest.builder(request)
                .after(cursor)
                .totalHits(mode)
                .build());
    }

    private static void assertCursorShape(
            SearchAfterCursor cursor,
            SearchRequest<Document> request,
            SearchEngine<Integer, Document> engine
    ) {
        assertEquals(BuiltInSearchAfterCursor.class, cursor.getClass());
        var references = V33TestReference.directReferenceValues(cursor);
        assertEquals(2, references.size());
        assertTrue(references.contains(request));
        assertFalse(references.contains(engine));
    }

    private static void assertStale(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request,
            SearchAfterCursor cursor,
            String message
    ) {
        SearchCursorException stale = assertThrows(
                SearchCursorException.class,
                () -> continuation(
                        engine,
                        request,
                        cursor,
                        TotalHitsMode.DISABLED
                ),
                message
        );
        assertEquals(
                SearchCursorException.Reason.STALE_SNAPSHOT,
                stale.reason(),
                message
        );
    }

    private static void assertHits(
            List<SearchHit<Document>> expected,
            List<SearchHit<Document>> observed
    ) {
        assertEquals(expected.size(), observed.size());
        for (int index = 0; index < expected.size(); index++) {
            assertEquals(expected.get(index).document(), observed.get(index).document());
            assertEquals(
                    Double.doubleToRawLongBits(expected.get(index).score()),
                    Double.doubleToRawLongBits(observed.get(index).score())
            );
        }
    }

    private static SearchRequest<Document> request(
            TextField<Document> text,
            int limit
    ) {
        return SearchRequest.<Document>builder()
                .query(SearchQueries.text(text, "gate"))
                .limit(limit)
                .build();
    }

    private static SearchEngine<Integer, Document> engine(
            TextField<Document> text,
            boolean groupIndexed
    ) {
        var builder = SearchEngine.builder(Document.class, ID)
                .field(GROUP)
                .config(new SnapshotEngineConfig(
                        10_000,
                        64,
                        Duration.ofMillis(1)
                ))
                .index(IndexDefinition.text(text));
        if (groupIndexed) {
            builder.index(IndexDefinition.equality(GROUP));
        }
        SearchEngine<Integer, Document> engine = builder.build();
        engine.addAll(List.of(
                document(1, "gate stable one"),
                document(2, "gate stable two"),
                document(3, "gate stable three"),
                document(4, "gate stable four"),
                document(5, "gate stable five"),
                document(6, "gate stable six")
        )).join();
        return engine;
    }

    private static Document document(int id, String body) {
        return new Document(id, body, id % 2 == 0 ? "even" : "odd");
    }

    private static List<PublicationCase> successfulPublicationCases() {
        return List.of(
                new PublicationCase("add", false, engine ->
                        engine.add(document(100, "gate added")).join()),
                new PublicationCase("update", false, engine ->
                        engine.update(document(1, "gate updated")).join()),
                new PublicationCase("remove", false, engine ->
                        engine.remove(6).join()),
                new PublicationCase("bulk add", false, engine ->
                        engine.addAll(List.of(
                                document(100, "gate bulk added"),
                                document(101, "gate bulk added")
                        )).join()),
                new PublicationCase("bulk update", false, engine ->
                        engine.updateAll(List.of(
                                document(1, "gate bulk updated"),
                                document(2, "gate bulk updated")
                        )).join()),
                new PublicationCase("bulk remove", false, engine ->
                        engine.removeAll(List.of(5, 6)).join()),
                new PublicationCase("dynamic create", false, engine ->
                        engine.createIndex(IndexDefinition.equality(GROUP)).join()),
                new PublicationCase("dynamic drop", true, engine ->
                        engine.dropIndex(GROUP.name()).join())
        );
    }

    private record Document(int id, String body, String group) {
    }

    private record PublicationCase(
            String name,
            boolean groupIndexed,
            Publication action
    ) {
    }

    private record NonPublicationCase(
            String name,
            boolean groupIndexed,
            boolean fails,
            Publication action
    ) {
    }

    @FunctionalInterface
    private interface Publication {
        void publish(SearchEngine<Integer, Document> engine);
    }

    private static final class BranchGateAnalyzer implements Analyzer {
        private final Analyzer delegate = Analyzer.simple();
        private final AtomicInteger remaining = new AtomicInteger();
        private volatile CountDownLatch entered = new CountDownLatch(0);
        private volatile CountDownLatch release = new CountDownLatch(0);

        @Override
        public List<Token> analyze(String text) {
            return delegate.analyze(text);
        }

        @Override
        public List<AnalyzedToken> analyzeWithPositions(String text) {
            if (text.equals("gate") && remaining.getAndUpdate(value ->
                    Math.max(0, value - 1)) > 0) {
                entered.countDown();
                await(release);
            }
            return delegate.analyzeWithPositions(text);
        }

        private void blockNextQueries(int count) {
            entered = new CountDownLatch(count);
            release = new CountDownLatch(1);
            remaining.set(count);
        }

        private boolean awaitEntered() throws InterruptedException {
            return entered.await(5, TimeUnit.SECONDS);
        }

        private void release() {
            release.countDown();
        }

        private static void await(CountDownLatch latch) {
            try {
                if (!latch.await(5, TimeUnit.SECONDS)) {
                    throw new AssertionError("timed out awaiting branch release");
                }
            } catch (InterruptedException failure) {
                Thread.currentThread().interrupt();
                throw new AssertionError("branch analysis interrupted", failure);
            }
        }
    }
}
