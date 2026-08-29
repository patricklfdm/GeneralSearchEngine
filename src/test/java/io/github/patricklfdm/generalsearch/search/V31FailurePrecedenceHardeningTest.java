package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class V31FailurePrecedenceHardeningTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void boolShapeValidationRunsBeforeAnyAnalyzerOrSnapshotWork() {
        AtomicInteger analysisCalls = new AtomicInteger();
        TextField<Document> text = TextField.of(BODY, counting(
                analysisCalls,
                ignored -> List.of(new AnalyzedToken("alpha", 1))
        ));
        SearchQuery<Document> leaf = SearchQueries.text(text, "alpha");

        SearchQueries.BoolBuilder<Document> aboveCount = SearchQueries
                .<Document>bool()
                .should(leaf)
                .minimumShouldMatch(2);
        assertThrows(IllegalArgumentException.class, aboveCount::build);
        assertThrows(
                IllegalArgumentException.class,
                () -> SearchQueries.<Document>bool()
                        .should(leaf)
                        .minimumShouldMatch(0)
                        .build()
        );
        assertThrows(
                IllegalArgumentException.class,
                () -> SearchQueries.<Document>bool().minimumShouldMatch(-1)
        );
        assertEquals(0, analysisCalls.get());

        SearchQuery<Document> repaired = aboveCount
                .should(leaf)
                .build();
        assertEquals(2, ((BoolSearchQueryNode<?>) repaired.node())
                .minimumShouldMatch());
        assertEquals(0, analysisCalls.get());
    }

    @Test
    void logicalNormalizationFailurePrecedesLaterLeavesAndStructuredFilter() {
        AtomicInteger missingCalls = new AtomicInteger();
        AtomicInteger malformedCalls = new AtomicInteger();
        AtomicInteger filterCalls = new AtomicInteger();
        TextField<Document> missing = TextField.of(BODY, counting(
                missingCalls,
                ignored -> List.of(new AnalyzedToken("alpha", 1))
        ));
        TextField<Document> malformed = TextField.of(BODY, counting(
                malformedCalls,
                ignored -> List.of(new AnalyzedToken("broken", 0))
        ));
        Query<Document> filter = document -> {
            filterCalls.incrementAndGet();
            throw new AssertionError("filter must not run before ranked planning");
        };
        SearchQuery<Document> query = SearchQueries.<Document>bool()
                .must(SearchQueries.text(missing, "alpha"))
                .should(SearchQueries.phrase(malformed, "broken", 2))
                .minimumShouldMatch(0)
                .build();

        IllegalStateException failure = assertThrows(
                IllegalStateException.class,
                () -> execute(new SearchSnapshot<>(List.of()), request(query, filter))
        );
        assertTrue(failure.getMessage().contains("body"));
        assertEquals(1, missingCalls.get());
        assertEquals(0, malformedCalls.get());
        assertEquals(0, filterCalls.get());
    }

    @Test
    void emptyLeavesSkipMissingIndexesButMalformedLaterAnalysisStillWins() {
        AtomicInteger emptyCalls = new AtomicInteger();
        AtomicInteger malformedCalls = new AtomicInteger();
        AtomicInteger filterCalls = new AtomicInteger();
        TextField<Document> empty = TextField.of(BODY, counting(
                emptyCalls,
                ignored -> List.of()
        ));
        TextField<Document> malformed = TextField.of(BODY, counting(
                malformedCalls,
                ignored -> List.of(new AnalyzedToken("broken", 0))
        ));
        Query<Document> filter = document -> {
            filterCalls.incrementAndGet();
            return true;
        };
        SearchQuery<Document> query = SearchQueries.<Document>bool()
                .should(SearchQueries.phrase(empty, "empty", 4))
                .should(SearchQueries.text(malformed, "broken"))
                .minimumShouldMatch(1)
                .build();

        assertThrows(
                IllegalArgumentException.class,
                () -> execute(new SearchSnapshot<>(List.of()), request(query, filter))
        );
        assertEquals(1, emptyCalls.get());
        assertEquals(1, malformedCalls.get());
        assertEquals(0, filterCalls.get());

        SearchQuery<Document> allEmpty = SearchQueries.<Document>bool()
                .should(SearchQueries.text(empty, "first"))
                .should(SearchQueries.phrase(empty, "second", 7))
                .minimumShouldMatch(2)
                .build();
        assertTrue(execute(
                new SearchSnapshot<>(List.of()),
                request(allEmpty, filter)
        ).hits().isEmpty());
        assertEquals(0, filterCalls.get());
    }

    @Test
    void missingBusinessIdReturnsBeforeRankedAnalysisAndIndexResolution() {
        AtomicInteger analysisCalls = new AtomicInteger();
        TextField<Document> missing = TextField.of(BODY, counting(
                analysisCalls,
                ignored -> List.of(new AnalyzedToken("alpha", 1))
        ));
        SearchRequest<Document> request = SearchRequest.of(
                SearchQueries.<Document>bool()
                        .should(SearchQueries.phrase(missing, "alpha beta", 2))
                        .minimumShouldMatch(1)
                        .build()
        );

        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .textField(missing)
                .build()) {
            engine.add(new Document(1, "alpha beta")).join();
            assertTrue(engine.explain(request, 999).isEmpty());
            assertEquals(0, analysisCalls.get());
            assertThrows(IllegalStateException.class, () -> engine.explain(request, 1));
            assertEquals(1, analysisCalls.get());
        }
    }

    private static SearchRequest<Document> request(
            SearchQuery<Document> query,
            Query<Document> filter
    ) {
        return SearchRequest.<Document>builder()
                .query(query)
                .filter(filter)
                .limit(10)
                .build();
    }

    private static SearchResult<Document> execute(
            SearchSnapshot<Document> snapshot,
            SearchRequest<Document> request
    ) {
        return SearchExecutionAccess.search(
                snapshot,
                request,
                new CandidatePlanner<>()
        );
    }

    private static Analyzer counting(
            AtomicInteger calls,
            java.util.function.Function<String, List<AnalyzedToken>> analysis
    ) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return analysis.apply(text).stream()
                        .map(token -> new Token(token.term()))
                        .toList();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                calls.incrementAndGet();
                return analysis.apply(text);
            }
        };
    }

    private record Document(int id, String body) {
    }
}
