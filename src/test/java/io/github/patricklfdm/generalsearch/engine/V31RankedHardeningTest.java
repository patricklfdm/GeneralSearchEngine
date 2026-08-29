package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReferenceArray;
import java.util.function.Predicate;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import org.junit.jupiter.api.RepeatedTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

class V31RankedHardeningTest {
    private static final int DOCUMENT_COUNT = 80;
    private static final String[] TERMS = {
            "alpha", "beta", "gamma", "delta", "noise"
    };
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void matchesSourceOracleAcrossLongMutationAndBulkHistory() {
        Random random = new Random(0x31_04_5005L);
        Map<Integer, Document> oracle = new LinkedHashMap<>();

        try (SearchEngine<Integer, Document> engine = engine(BODY_TEXT)) {
            List<Document> initial = new ArrayList<>();
            for (int id = 0; id < 40; id++) {
                Document document = randomDocument(random, id, 0);
                initial.add(document);
                oracle.put(id, document);
            }
            engine.addAll(initial).join();

            for (int iteration = 0; iteration < 120; iteration++) {
                int id = random.nextInt(55);
                switch (random.nextInt(4)) {
                    case 0 -> upsert(engine, oracle, randomDocument(
                            random,
                            id,
                            iteration + 1
                    ));
                    case 1 -> {
                        engine.remove(id).join();
                        oracle.remove(id);
                    }
                    case 2 -> bulkUpdate(engine, oracle, random, iteration);
                    default -> {
                        engine.remove(id).join();
                        oracle.remove(id);
                        Document replacement = randomDocument(
                                random,
                                id,
                                iteration + 1
                        );
                        engine.add(replacement).join();
                        oracle.put(id, replacement);
                    }
                }
                if (iteration % 6 == 0) {
                    verifyAll(engine, oracle);
                }
            }
            verifyAll(engine, oracle);
            assertEquals(oracle.size(), engine.metrics().documentCount());
            assertEquals(0, engine.metrics().writerQueueDepth());
        }
    }

    @Test
    void rollsBackFailedBulkAndRebuildsDynamicTextIndexWithoutSemanticDrift() {
        Analyzer failingAnalyzer = text -> {
            if (text.equals("explode")) {
                throw new IllegalStateException("synthetic analysis failure");
            }
            return Analyzer.simple().analyze(text);
        };
        TextField<Document> text = TextField.of(BODY, failingAnalyzer);
        Map<Integer, Document> oracle = new LinkedHashMap<>();
        Document first = new Document(1, "alpha noise beta gamma", "guide");
        Document second = new Document(2, "alpha delta", "reference");
        Document third = new Document(3, "beta gamma delta", "guide");
        oracle.put(1, first);
        oracle.put(2, second);
        oracle.put(3, third);

        try (SearchEngine<Integer, Document> engine = engine(text)) {
            engine.addAll(oracle.values()).join();
            verifyAll(engine, oracle, text);
            long versionBeforeFailure = engine.metrics().snapshotVersion();

            CompletionException failure = assertThrows(
                    CompletionException.class,
                    () -> engine.updateAll(List.of(
                            new Document(1, "alpha beta delta", "guide"),
                            new Document(2, "explode", "reference")
                    )).join()
            );
            assertTrue(failure.getCause() instanceof IllegalStateException);
            assertEquals(versionBeforeFailure, engine.metrics().snapshotVersion());
            assertSame(first, engine.get(1));
            assertSame(second, engine.get(2));
            verifyAll(engine, oracle, text);

            Document recovered = new Document(
                    2,
                    "alpha beta gamma delta",
                    "guide"
            );
            engine.update(recovered).join();
            oracle.put(2, recovered);
            verifyAll(engine, oracle, text);

            engine.dropIndex(BODY.name()).join();
            assertThrows(
                    IllegalStateException.class,
                    () -> engine.search(queries(text).getFirst().request())
            );
            assertThrows(
                    IllegalStateException.class,
                    () -> engine.explain(queries(text).get(1).request(), 1)
            );

            engine.createIndex(IndexDefinition.text(text)).join();
            verifyAll(engine, oracle, text);
            engine.remove(3).join();
            oracle.remove(3);
            assertTrue(engine.explain(queries(text).getFirst().request(), 3).isEmpty());
            verifyAll(engine, oracle, text);
        }
    }

    @RepeatedTest(3)
    @Timeout(30)
    void concurrentReadersObserveOnlyValidRankedSnapshotsDuringBulkUpdates()
            throws Exception {
        AtomicReferenceArray<Document> finalOracle =
                new AtomicReferenceArray<>(DOCUMENT_COUNT);
        try (SearchEngine<Integer, Document> engine = engine(BODY_TEXT)) {
            List<Document> initial = new ArrayList<>();
            for (int id = 0; id < DOCUMENT_COUNT; id++) {
                Document document = deterministicDocument(id, 0);
                initial.add(document);
                finalOracle.set(id, document);
            }
            engine.addAll(initial).join();

            int readerCount = 4;
            ExecutorService workers = Executors.newFixedThreadPool(readerCount + 1);
            CountDownLatch start = new CountDownLatch(1);
            List<Future<?>> tasks = new ArrayList<>();
            try {
                for (int reader = 0; reader < readerCount; reader++) {
                    int seed = 31_040 + reader;
                    tasks.add(workers.submit(() -> runReader(engine, start, seed)));
                }
                tasks.add(workers.submit(() -> runWriter(
                        engine,
                        finalOracle,
                        start
                )));
                start.countDown();
                for (Future<?> task : tasks) {
                    task.get(25, TimeUnit.SECONDS);
                }
            } finally {
                workers.shutdownNow();
                assertTrue(workers.awaitTermination(5, TimeUnit.SECONDS));
            }

            Map<Integer, Document> expected = new LinkedHashMap<>();
            for (int id = 0; id < DOCUMENT_COUNT; id++) {
                expected.put(id, finalOracle.get(id));
            }
            verifyAll(engine, expected);
            assertEquals(DOCUMENT_COUNT, engine.metrics().documentCount());
            assertEquals(0, engine.metrics().writerQueueDepth());
            assertEquals(0, engine.metrics().failedMutations());
        }
    }

    private static void runReader(
            SearchEngine<Integer, Document> engine,
            CountDownLatch start,
            int seed
    ) {
        await(start);
        Random random = new Random(seed);
        List<OracleQuery> queries = queries(BODY_TEXT);
        for (int iteration = 0; iteration < 300; iteration++) {
            OracleQuery query = queries.get(random.nextInt(queries.size()));
            SearchResult<Document> result = engine.search(query.request());
            assertValidResult(result, query.matches());

            int id = random.nextInt(DOCUMENT_COUNT);
            Optional<SearchExplanation<Document>> explanation = engine.explain(
                    query.request(),
                    id
            );
            explanation.ifPresent(value -> {
                boolean expected = query.matches().test(value.document());
                assertEquals(expected, value.matched());
                if (expected) {
                    assertTrue(Double.isFinite(value.score()));
                    assertTrue(value.score() >= 0.0);
                } else {
                    assertEquals(0.0, value.score());
                }
            });
        }
    }

    private static void runWriter(
            SearchEngine<Integer, Document> engine,
            AtomicReferenceArray<Document> oracle,
            CountDownLatch start
    ) {
        await(start);
        for (int revision = 1; revision <= 180; revision++) {
            if (revision % 9 == 0) {
                List<Document> replacements = new ArrayList<>();
                for (int offset = 0; offset < 4; offset++) {
                    int id = (revision * 7 + offset * 13) % DOCUMENT_COUNT;
                    replacements.add(deterministicDocument(id, revision));
                }
                engine.updateAll(replacements).join();
                replacements.forEach(document -> oracle.set(
                        document.id(),
                        document
                ));
            } else {
                int id = (revision * 17) % DOCUMENT_COUNT;
                Document replacement = deterministicDocument(id, revision);
                engine.update(replacement).join();
                oracle.set(id, replacement);
            }
        }
    }

    private static void verifyAll(
            SearchEngine<Integer, Document> engine,
            Map<Integer, Document> oracle
    ) {
        verifyAll(engine, oracle, BODY_TEXT);
    }

    private static void verifyAll(
            SearchEngine<Integer, Document> engine,
            Map<Integer, Document> oracle,
            TextField<Document> text
    ) {
        for (OracleQuery query : queries(text)) {
            SearchResult<Document> result = engine.search(query.request());
            Set<Integer> expectedIds = oracle.values().stream()
                    .filter(query.matches())
                    .map(Document::id)
                    .collect(Collectors.toSet());
            Map<Integer, Double> actualScores = result.hits().stream()
                    .collect(Collectors.toMap(
                            hit -> hit.document().id(),
                            SearchHit::score
                    ));
            assertEquals(expectedIds, actualScores.keySet());
            assertValidResult(result, query.matches());

            for (Document document : oracle.values()) {
                SearchExplanation<Document> explanation = engine.explain(
                        query.request(),
                        document.id()
                ).orElseThrow();
                boolean expected = query.matches().test(document);
                assertEquals(expected, explanation.matched());
                assertEquals(
                        expected ? actualScores.get(document.id()) : 0.0,
                        explanation.score()
                );
            }
        }
    }

    private static void assertValidResult(
            SearchResult<Document> result,
            Predicate<Document> expected
    ) {
        Set<Integer> ids = new HashSet<>();
        double previousScore = Double.POSITIVE_INFINITY;
        for (SearchHit<Document> hit : result.hits()) {
            assertTrue(expected.test(hit.document()));
            assertTrue(ids.add(hit.document().id()));
            assertTrue(Double.isFinite(hit.score()));
            assertTrue(hit.score() >= 0.0);
            assertTrue(hit.score() <= previousScore);
            previousScore = hit.score();
        }
    }

    private static List<OracleQuery> queries(TextField<Document> text) {
        Predicate<Document> sloppyPhrase = document -> phraseMatches(
                document.body(),
                "alpha",
                "beta",
                2
        );
        SearchRequest<Document> phraseRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.phrase(text, "alpha beta", 2))
                .limit(500)
                .build();

        Predicate<Document> threshold = document -> document.category().equals("guide")
                && matchedCount(
                        phraseMatches(document.body(), "alpha", "beta", 1),
                        contains(document.body(), "gamma"),
                        contains(document.body(), "delta")
                ) >= 2;
        SearchRequest<Document> thresholdRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .should(SearchQueries.phrase(text, "alpha beta", 1))
                        .should(SearchQueries.text(text, "gamma"))
                        .should(SearchQueries.text(text, "delta"))
                        .minimumShouldMatch(2)
                        .build())
                .filter(io.github.patricklfdm.generalsearch.query.Query.eq(
                        CATEGORY,
                        "guide"
                ))
                .limit(500)
                .build();

        Predicate<Document> duplicateThreshold = document ->
                contains(document.body(), "alpha")
                        && matchedCount(
                                contains(document.body(), "beta"),
                                contains(document.body(), "beta"),
                                phraseMatches(
                                        document.body(),
                                        "gamma",
                                        "delta",
                                        2
                                )
                        ) >= 2;
        SearchRequest<Document> duplicateRequest = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .must(SearchQueries.text(text, "alpha"))
                        .should(SearchQueries.text(text, "beta"))
                        .should(SearchQueries.text(text, "beta"))
                        .should(SearchQueries.phrase(text, "gamma delta", 2))
                        .minimumShouldMatch(2)
                        .build()
                        .boost(1.5))
                .limit(500)
                .build();

        return List.of(
                new OracleQuery(phraseRequest, sloppyPhrase),
                new OracleQuery(thresholdRequest, threshold),
                new OracleQuery(duplicateRequest, duplicateThreshold)
        );
    }

    private static SearchEngine<Integer, Document> engine(
            TextField<Document> text
    ) {
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY)
                .textField(text)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.text(text))
                .build();
    }

    private static void upsert(
            SearchEngine<Integer, Document> engine,
            Map<Integer, Document> oracle,
            Document replacement
    ) {
        if (oracle.containsKey(replacement.id())) {
            engine.update(replacement).join();
        } else {
            engine.add(replacement).join();
        }
        oracle.put(replacement.id(), replacement);
    }

    private static void bulkUpdate(
            SearchEngine<Integer, Document> engine,
            Map<Integer, Document> oracle,
            Random random,
            int revision
    ) {
        List<Integer> ids = new ArrayList<>(oracle.keySet());
        if (ids.isEmpty()) {
            return;
        }
        List<Document> replacements = new ArrayList<>();
        for (int index = 0; index < Math.min(3, ids.size()); index++) {
            int id = ids.get(random.nextInt(ids.size()));
            if (replacements.stream().anyMatch(value -> value.id() == id)) {
                continue;
            }
            replacements.add(randomDocument(random, id, revision + index + 1));
        }
        engine.updateAll(replacements).join();
        replacements.forEach(document -> oracle.put(document.id(), document));
    }

    private static Document randomDocument(Random random, int id, int revision) {
        int tokenCount = 2 + random.nextInt(7);
        StringBuilder body = new StringBuilder();
        for (int index = 0; index < tokenCount; index++) {
            if (!body.isEmpty()) {
                body.append(' ');
            }
            body.append(TERMS[random.nextInt(TERMS.length)]);
        }
        return new Document(
                id,
                body.toString(),
                (id + revision) % 2 == 0 ? "guide" : "reference"
        );
    }

    private static Document deterministicDocument(int id, int revision) {
        int selector = Math.floorMod(id * 7 + revision * 11, 6);
        String body = switch (selector) {
            case 0 -> "alpha beta gamma delta";
            case 1 -> "alpha noise beta gamma";
            case 2 -> "alpha delta noise";
            case 3 -> "beta gamma delta";
            case 4 -> "gamma noise beta alpha";
            default -> "alpha gamma noise delta beta";
        };
        return new Document(
                id,
                body,
                (id + revision) % 3 == 0 ? "guide" : "reference"
        );
    }

    private static boolean phraseMatches(
            String body,
            String first,
            String second,
            int slop
    ) {
        List<String> terms = tokens(body);
        for (int left = 0; left < terms.size(); left++) {
            if (!terms.get(left).equals(first)) {
                continue;
            }
            for (int right = left + 1; right < terms.size(); right++) {
                if (terms.get(right).equals(second)
                        && right - left - 1 <= slop) {
                    return true;
                }
            }
        }
        return false;
    }

    private static boolean contains(String body, String term) {
        return tokens(body).contains(term);
    }

    private static List<String> tokens(String body) {
        return Analyzer.simple().analyze(body).stream()
                .map(Token::term)
                .toList();
    }

    private static int matchedCount(boolean... matches) {
        int count = 0;
        for (boolean matched : matches) {
            if (matched) {
                count++;
            }
        }
        return count;
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("timed out starting concurrent hardening");
            }
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new AssertionError("concurrent hardening interrupted", failure);
        }
    }

    private record OracleQuery(
            SearchRequest<Document> request,
            Predicate<Document> matches
    ) {
    }

    private record Document(int id, String body, String category) {
    }
}
