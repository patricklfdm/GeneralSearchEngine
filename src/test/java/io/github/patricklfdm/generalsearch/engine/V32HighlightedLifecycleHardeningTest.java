package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.engine.exception.IndexLifecycleException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.HighlightFragment;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchResult;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

class V32HighlightedLifecycleHardeningTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    @Timeout(20)
    void addUpdateRemoveAndBulkPublicationsCannotMixCapturedResults()
            throws Exception {
        BlockingOffsetAnalyzer analyzer = new BlockingOffsetAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        try (SearchEngine<Integer, Document> engine = engine(text, true)) {
            engine.add(new Document(1, "alpha old")).join();
            HighlightedSearchRequest<Document> request = request(
                    SearchQueries.text(text, "alpha"), text);

            HighlightedSearchResult<Document> beforeAdd = captureAcross(
                    engine,
                    analyzer,
                    request,
                    () -> engine.add(new Document(2, "alpha added")).join()
            );
            assertEquals(Set.of(1), ids(beforeAdd));
            assertExactSourceProjection(beforeAdd);

            HighlightedSearchResult<Document> beforeUpdate = captureAcross(
                    engine,
                    analyzer,
                    request,
                    () -> engine.update(new Document(1, "retired")).join()
            );
            assertEquals(Set.of(1, 2), ids(beforeUpdate));
            assertEquals("alpha old", document(beforeUpdate, 1).body());
            assertExactSourceProjection(beforeUpdate);

            HighlightedSearchResult<Document> beforeRemove = captureAcross(
                    engine,
                    analyzer,
                    request,
                    () -> engine.remove(2).join()
            );
            assertEquals(Set.of(2), ids(beforeRemove));
            assertExactSourceProjection(beforeRemove);

            engine.addAll(List.of(
                    new Document(3, "alpha three"),
                    new Document(4, "alpha four")
            )).join();
            HighlightedSearchResult<Document> beforeBulk = captureAcross(
                    engine,
                    analyzer,
                    request,
                    () -> engine.updateAll(List.of(
                            new Document(3, "retired three"),
                            new Document(4, "retired four")
                    )).join()
            );
            assertEquals(Set.of(3, 4), ids(beforeBulk));
            assertExactSourceProjection(beforeBulk);
            assertTrue(engine.search(request).hits().isEmpty());
        } finally {
            analyzer.release();
        }
    }

    @Test
    @Timeout(20)
    void dynamicTextBuildReplaysMutationsAndDropCreateRaceStaysCanonical()
            throws Exception {
        BlockingOffsetAnalyzer analyzer = new BlockingOffsetAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        try (SearchEngine<Integer, Document> engine = engine(text, false)) {
            engine.addAll(List.of(
                    new Document(1, "alpha old"),
                    new Document(2, "alpha remove")
            )).join();

            analyzer.blockNextBuild();
            CompletableFuture<Void> create = engine.createIndex(
                    IndexDefinition.text(text));
            assertTrue(analyzer.awaitBuild());
            engine.update(new Document(1, "beta alpha updated")).join();
            engine.remove(2).join();
            engine.add(new Document(3, "alpha added")).join();
            analyzer.releaseBuild();
            create.join();

            HighlightedSearchRequest<Document> request = request(
                    SearchQueries.text(text, "alpha"), text);
            HighlightedSearchResult<Document> replayed = engine.search(request);
            assertEquals(Set.of(1, 3), ids(replayed));
            assertExactSourceProjection(replayed);

            engine.dropIndex(BODY.name()).join();
            analyzer.blockNextBuild();
            CompletableFuture<Void> cancelled = engine.createIndex(
                    IndexDefinition.text(text));
            assertTrue(analyzer.awaitBuild());
            engine.dropIndex(BODY.name()).join();
            CompletionException failure = assertThrows(
                    CompletionException.class,
                    cancelled::join
            );
            assertEquals(
                    IndexLifecycleException.Reason.CANCELLED,
                    assertInstanceOf(
                            IndexLifecycleException.class,
                            failure.getCause()
                    ).reason()
            );
            analyzer.releaseBuild();
            engine.createIndex(IndexDefinition.text(text)).join();
            assertEquals(Set.of(1, 3), ids(engine.search(request)));
        } finally {
            analyzer.release();
            analyzer.releaseBuild();
        }
    }

    @Test
    @Timeout(20)
    void admittedHighlightedReadCompletesAfterClose() throws Exception {
        BlockingOffsetAnalyzer analyzer = new BlockingOffsetAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        SearchEngine<Integer, Document> engine = engine(text, true);
        try {
            engine.add(new Document(1, "alpha admitted")).join();
            HighlightedSearchRequest<Document> request = request(
                    SearchQueries.text(text, "alpha"), text);
            analyzer.blockNextOffset();
            CompletableFuture<HighlightedSearchResult<Document>> pending =
                    CompletableFuture.supplyAsync(() -> engine.search(request));
            assertTrue(analyzer.awaitOffset());

            CompletableFuture.runAsync(engine::close).get(5, TimeUnit.SECONDS);
            analyzer.releaseOffset();
            HighlightedSearchResult<Document> admitted = pending.get(
                    5,
                    TimeUnit.SECONDS
            );
            assertEquals(Set.of(1), ids(admitted));
            assertExactSourceProjection(admitted);

            EngineRejectedExecutionException rejected = assertThrows(
                    EngineRejectedExecutionException.class,
                    () -> engine.search(request)
            );
            assertEquals(
                    EngineRejectedExecutionException.Reason.CLOSED,
                    rejected.reason()
            );
        } finally {
            analyzer.release();
            engine.close();
        }
    }

    @Test
    void failedBulkAnalysisAndFailedHighlightAnalysisPublishNothing() {
        FailingOffsetAnalyzer analyzer = new FailingOffsetAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        try (SearchEngine<Integer, Document> engine = engine(text, true)) {
            engine.addAll(List.of(
                    new Document(1, "alpha one"),
                    new Document(2, "alpha two")
            )).join();
            HighlightedSearchRequest<Document> request = request(
                    SearchQueries.text(text, "alpha"), text);
            long before = engine.metrics().snapshotVersion();

            assertThrows(CompletionException.class, () -> engine.updateAll(List.of(
                    new Document(1, "beta one"),
                    new Document(2, "FAIL two")
            )).join());
            assertEquals(before, engine.metrics().snapshotVersion());
            assertEquals(Set.of(1, 2), ids(engine.search(request)));

            analyzer.failOffsets.set(true);
            assertThrows(IllegalStateException.class, () -> engine.search(request));
            assertEquals(before, engine.metrics().snapshotVersion());
            analyzer.failOffsets.set(false);
            assertEquals(Set.of(1, 2), ids(engine.search(request)));
        }
    }

    @Test
    @Timeout(30)
    void mixedHighlightedOrdinaryExplainReadersAndWriterMakeProgress()
            throws Exception {
        TextField<Document> text = TextField.of(BODY, Analyzer.simple());
        SnapshotEngineConfig config = new SnapshotEngineConfig(
                10_000,
                64,
                Duration.ofMillis(1)
        );
        SearchSchema<Document, Integer> schema = SearchSchema
                .builder(Document.class, ID)
                .textField(text)
                .build();
        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(schema)
                .config(config)
                .index(IndexDefinition.text(text))
                .build()) {
            for (int id = 0; id < 80; id++) {
                engine.add(new Document(id, source(id, 0))).join();
            }
            SearchQuery<Document> query = SearchQueries.<Document>bool()
                    .must(SearchQueries.text(text, "stable"))
                    .should(SearchQueries.phrase(text, "stable revision"))
                    .should(SearchQueries.fuzzy(text, "stble"))
                    .minimumShouldMatch(1)
                    .build()
                    .boost(1.5);
            SearchRequest<Document> search = SearchRequest.<Document>builder()
                    .query(query)
                    .limit(20)
                    .build();
            HighlightedSearchRequest<Document> highlighted =
                    HighlightedSearchRequest.<Document>builder(search)
                            .field(text)
                            .contextCharacters(4)
                            .maxFragmentsPerField(3)
                            .build();
            long initialVersion = engine.metrics().snapshotVersion();
            AtomicInteger publications = new AtomicInteger();
            CountDownLatch start = new CountDownLatch(1);
            ExecutorService workers = Executors.newFixedThreadPool(7);
            try {
                List<Future<?>> tasks = List.of(
                        workers.submit(() -> highlightedReader(
                                engine, highlighted, start, 180)),
                        workers.submit(() -> highlightedReader(
                                engine, highlighted, start, 180)),
                        workers.submit(() -> highlightedReader(
                                engine, highlighted, start, 180)),
                        workers.submit(() -> ordinaryReader(
                                engine, search, start, 260)),
                        workers.submit(() -> ordinaryReader(
                                engine, search, start, 260)),
                        workers.submit(() -> explainReader(
                                engine, search, start, 260)),
                        workers.submit(() -> writer(
                                engine, start, publications, 240))
                );
                start.countDown();
                for (Future<?> task : tasks) {
                    task.get(25, TimeUnit.SECONDS);
                }
            } finally {
                workers.shutdownNow();
                assertTrue(workers.awaitTermination(5, TimeUnit.SECONDS));
            }

            assertEquals(240, publications.get());
            assertTrue(engine.metrics().snapshotVersion() >= initialVersion + 240);
            assertEquals(0, engine.metrics().writerQueueDepth());
            assertEquals(
                    engine.search(search).hits(),
                    engine.search(highlighted).hits().stream()
                            .map(hit -> hit.hit())
                            .toList()
            );
        }
    }

    private static void highlightedReader(
            SearchEngine<Integer, Document> engine,
            HighlightedSearchRequest<Document> request,
            CountDownLatch start,
            int iterations
    ) {
        await(start);
        for (int iteration = 0; iteration < iterations; iteration++) {
            HighlightedSearchResult<Document> result = engine.search(request);
            assertEquals(20, result.hits().size());
            assertExactSourceProjection(result);
        }
    }

    private static void ordinaryReader(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request,
            CountDownLatch start,
            int iterations
    ) {
        await(start);
        for (int iteration = 0; iteration < iterations; iteration++) {
            var hits = engine.search(request).hits();
            assertEquals(20, hits.size());
            hits.forEach(hit -> assertTrue(hit.document().body().contains("stable")));
        }
    }

    private static void explainReader(
            SearchEngine<Integer, Document> engine,
            SearchRequest<Document> request,
            CountDownLatch start,
            int iterations
    ) {
        await(start);
        for (int iteration = 0; iteration < iterations; iteration++) {
            assertTrue(engine.explain(request, iteration % 80)
                    .orElseThrow()
                    .matched());
        }
    }

    private static void writer(
            SearchEngine<Integer, Document> engine,
            CountDownLatch start,
            AtomicInteger publications,
            int iterations
    ) {
        await(start);
        for (int revision = 1; revision <= iterations; revision++) {
            int id = revision % 80;
            engine.update(new Document(id, source(id, revision))).join();
            publications.incrementAndGet();
        }
    }

    private static String source(int id, int revision) {
        return "stable revision " + revision + " document " + id
                + (revision % 2 == 0 ? " alpha" : " beta");
    }

    private static HighlightedSearchResult<Document> captureAcross(
            SearchEngine<Integer, Document> engine,
            BlockingOffsetAnalyzer analyzer,
            HighlightedSearchRequest<Document> request,
            Runnable publication
    ) throws Exception {
        analyzer.blockNextOffset();
        CompletableFuture<HighlightedSearchResult<Document>> pending =
                CompletableFuture.supplyAsync(() -> engine.search(request));
        assertTrue(analyzer.awaitOffset());
        publication.run();
        analyzer.releaseOffset();
        return pending.get(5, TimeUnit.SECONDS);
    }

    private static SearchEngine<Integer, Document> engine(
            TextField<Document> text,
            boolean indexed
    ) {
        SearchSchema<Document, Integer> schema = SearchSchema
                .builder(Document.class, ID)
                .textField(text)
                .build();
        SearchEngineBuilder<Integer, Document> builder = SearchEngine.builder(schema);
        if (indexed) {
            builder.index(IndexDefinition.text(text));
        }
        return builder.build();
    }

    private static HighlightedSearchRequest<Document> request(
            SearchQuery<Document> query,
            TextField<Document> text
    ) {
        return HighlightedSearchRequest.<Document>builder(SearchRequest.of(query))
                .field(text)
                .contextCharacters(0)
                .maxFragmentsPerField(10)
                .build();
    }

    private static Set<Integer> ids(HighlightedSearchResult<Document> result) {
        Set<Integer> ids = new HashSet<>();
        result.hits().forEach(hit -> ids.add(hit.hit().document().id()));
        return ids;
    }

    private static Document document(
            HighlightedSearchResult<Document> result,
            int id
    ) {
        return result.hits().stream()
                .map(hit -> hit.hit().document())
                .filter(document -> document.id() == id)
                .findFirst()
                .orElseThrow();
    }

    private static void assertExactSourceProjection(
            HighlightedSearchResult<Document> result
    ) {
        result.hits().forEach(hit -> hit.highlights().forEach(field ->
                field.fragments().forEach(fragment -> {
                    String source = hit.hit().document().body();
                    assertEquals(
                            source.substring(
                                    fragment.startOffset(),
                                    fragment.endOffset()
                            ),
                            fragment.text()
                    );
                    fragment.spans().forEach(span -> {
                        assertTrue(span.startOffset() >= fragment.startOffset());
                        assertTrue(span.endOffset() <= fragment.endOffset());
                        assertTrue(span.startOffset() < span.endOffset());
                    });
                })));
    }

    private static void await(CountDownLatch latch) {
        try {
            assertTrue(latch.await(5, TimeUnit.SECONDS));
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new AssertionError("interrupted while awaiting start", failure);
        }
    }

    private record Document(int id, String body) {
    }

    private static class BlockingOffsetAnalyzer implements OffsetAnalyzer {
        private final Analyzer ordinary = Analyzer.simple();
        private final OffsetAnalyzer offsets = (OffsetAnalyzer) Analyzer.simple();
        private final AtomicBoolean blockOffset = new AtomicBoolean();
        private final AtomicBoolean blockBuild = new AtomicBoolean();
        private volatile CountDownLatch offsetEntered = new CountDownLatch(0);
        private volatile CountDownLatch offsetRelease = new CountDownLatch(0);
        private volatile CountDownLatch buildEntered = new CountDownLatch(0);
        private volatile CountDownLatch buildRelease = new CountDownLatch(0);

        @Override
        public List<Token> analyze(String text) {
            return ordinary.analyze(text);
        }

        @Override
        public List<AnalyzedToken> analyzeWithPositions(String text) {
            if (Thread.currentThread().getName()
                    .startsWith("snapshot-index-builder-")
                    && blockBuild.compareAndSet(true, false)) {
                buildEntered.countDown();
                awaitUnbounded(buildRelease);
            }
            return ordinary.analyzeWithPositions(text);
        }

        @Override
        public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
            if (blockOffset.compareAndSet(true, false)) {
                offsetEntered.countDown();
                awaitUnbounded(offsetRelease);
            }
            return offsets.analyzeWithOffsets(text);
        }

        private void blockNextOffset() {
            offsetEntered = new CountDownLatch(1);
            offsetRelease = new CountDownLatch(1);
            blockOffset.set(true);
        }

        private boolean awaitOffset() throws InterruptedException {
            return offsetEntered.await(5, TimeUnit.SECONDS);
        }

        private void releaseOffset() {
            offsetRelease.countDown();
        }

        private void blockNextBuild() {
            buildEntered = new CountDownLatch(1);
            buildRelease = new CountDownLatch(1);
            blockBuild.set(true);
        }

        private boolean awaitBuild() throws InterruptedException {
            return buildEntered.await(5, TimeUnit.SECONDS);
        }

        private void releaseBuild() {
            buildRelease.countDown();
        }

        private void release() {
            releaseOffset();
            releaseBuild();
        }

        private static void awaitUnbounded(CountDownLatch latch) {
            try {
                latch.await();
            } catch (InterruptedException failure) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("analyzer interrupted", failure);
            }
        }
    }

    private static final class FailingOffsetAnalyzer implements OffsetAnalyzer {
        private final Analyzer ordinary = Analyzer.simple();
        private final OffsetAnalyzer offsets = (OffsetAnalyzer) Analyzer.simple();
        private final AtomicBoolean failOffsets = new AtomicBoolean();

        @Override
        public List<Token> analyze(String text) {
            return ordinary.analyze(text);
        }

        @Override
        public List<AnalyzedToken> analyzeWithPositions(String text) {
            if (text.contains("FAIL")) {
                throw new IllegalArgumentException("synthetic indexing failure");
            }
            return ordinary.analyzeWithPositions(text);
        }

        @Override
        public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
            if (failOffsets.get()) {
                throw new IllegalStateException("synthetic offset failure");
            }
            return offsets.analyzeWithOffsets(text);
        }
    }
}
