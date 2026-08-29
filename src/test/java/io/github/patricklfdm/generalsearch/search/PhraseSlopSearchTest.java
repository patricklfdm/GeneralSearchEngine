package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class PhraseSlopSearchTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void appliesOrderedExtraGapBudgetWithoutChangingBm25Scoring() {
        List<Document> documents = List.of(
                new Document(0, "alpha beta", "guide"),
                new Document(1, "alpha noise beta", "guide"),
                new Document(2, "alpha noise noise beta", "guide"),
                new Document(3, "beta noise alpha", "guide"),
                new Document(4, "alpha only", "guide")
        );
        SearchSnapshot<Document> snapshot = snapshot(BODY_TEXT, documents);

        SearchResult<Document> legacy = execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(BODY_TEXT, "alpha beta"))
        );
        SearchResult<Document> explicitZero = execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(BODY_TEXT, "alpha beta", 0))
        );
        assertEquals(legacy.hits(), explicitZero.hits());
        assertEquals(Set.of(0), ids(legacy));
        assertEquals(Set.of(0, 1), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(BODY_TEXT, "alpha beta", 1))
        )));
        SearchResult<Document> slopTwo = execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(BODY_TEXT, "alpha beta", 2))
        );
        assertEquals(Set.of(0, 1, 2), ids(slopTwo));
        assertFalse(ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(
                        BODY_TEXT,
                        "alpha beta",
                        Integer.MAX_VALUE
                ))
        )).contains(3));

        Map<Integer, Double> textScores = scores(execute(
                snapshot,
                SearchRequest.of(SearchQueries.text(BODY_TEXT, "alpha beta"))
        ));
        for (SearchHit<Document> hit : slopTwo.hits()) {
            assertEquals(textScores.get(hit.document().id()), hit.score());
        }

        SearchPlan<Document> plan = plan(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(BODY_TEXT, "alpha beta", 2))
        );
        PhrasePlan<?> phrasePlan = (PhrasePlan<?>) plan.root();
        assertEquals(2, phrasePlan.requestedSlop());
        assertTrue(phrasePlan.candidates().get(3));
        assertFalse(phrasePlan.evaluate(3).matched());
    }

    @Test
    void preservesQueryGapsAlternativesRepeatedTermsAndSingleSlots() {
        Analyzer analyzer = positioned(text -> switch (text) {
            case "gap-query" -> List.of(
                    new AnalyzedToken("alpha", 5),
                    new AnalyzedToken("beta", 2)
            );
            case "contracted" -> List.of(
                    new AnalyzedToken("alpha", 1),
                    new AnalyzedToken("beta", 1)
            );
            case "minimum-gap" -> List.of(
                    new AnalyzedToken("alpha", 1),
                    new AnalyzedToken("beta", 2)
            );
            case "expanded-gap" -> List.of(
                    new AnalyzedToken("alpha", 1),
                    new AnalyzedToken("beta", 3)
            );
            case "alternative-query" -> List.of(
                    new AnalyzedToken("usa", 4),
                    new AnalyzedToken("united_states", 0),
                    new AnalyzedToken("travel", 1)
            );
            case "alternative-document" -> List.of(
                    new AnalyzedToken("united_states", 1),
                    new AnalyzedToken("travel", 2)
            );
            case "repeat-query" -> List.of(
                    new AnalyzedToken("echo", 1),
                    new AnalyzedToken("echo", 1)
            );
            case "one-echo" -> List.of(new AnalyzedToken("echo", 1));
            case "two-echo" -> List.of(
                    new AnalyzedToken("echo", 1),
                    new AnalyzedToken("echo", 2)
            );
            case "single-query", "single-document" ->
                    List.of(new AnalyzedToken("single", 1));
            case "boundary-query", "boundary-document" -> List.of(
                    new AnalyzedToken("alpha", 1),
                    new AnalyzedToken("beta", Integer.MAX_VALUE)
            );
            default -> List.of();
        });
        TextField<Document> field = TextField.of(BODY, analyzer);
        List<Document> documents = List.of(
                new Document(0, "contracted", "guide"),
                new Document(1, "minimum-gap", "guide"),
                new Document(2, "expanded-gap", "guide"),
                new Document(3, "alternative-document", "guide"),
                new Document(4, "one-echo", "guide"),
                new Document(5, "two-echo", "guide"),
                new Document(6, "single-document", "guide"),
                new Document(7, "boundary-document", "guide")
        );
        SearchSnapshot<Document> snapshot = snapshot(field, documents);

        assertEquals(Set.of(1), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(field, "gap-query", 0))
        )));
        assertEquals(Set.of(1, 2), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(field, "gap-query", 1))
        )));
        assertFalse(ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(
                        field,
                        "gap-query",
                        Integer.MAX_VALUE
                ))
        )).contains(0));
        assertEquals(Set.of(3), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(
                        field,
                        "alternative-query",
                        1
                ))
        )));
        assertEquals(Set.of(5), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(field, "repeat-query", 1))
        )));
        assertEquals(Set.of(6), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(
                        field,
                        "single-query",
                        Integer.MAX_VALUE
                ))
        )));
        assertEquals(Set.of(7), ids(execute(
                snapshot,
                SearchRequest.of(SearchQueries.phrase(
                        field,
                        "boundary-query",
                        Integer.MAX_VALUE
                ))
        )));
    }

    @Test
    void reportsRequestedAndMinimumConsumedSlopAndComposesNormally() {
        List<Document> documents = List.of(
                new Document(0, "alpha noise noise beta alpha beta", "guide"),
                new Document(1, "alpha noise beta", "guide"),
                new Document(2, "alpha noise beta", "reference"),
                new Document(3, "beta noise alpha", "guide")
        );
        SearchSnapshot<Document> snapshot = snapshot(BODY_TEXT, documents);
        SearchQuery<Document> phrase = SearchQueries.phrase(
                BODY_TEXT,
                "alpha beta",
                2
        );
        SearchQuery<Document> composed = SearchQueries.<Document>bool()
                .must(SearchQueries.text(BODY_TEXT, "alpha"))
                .should(phrase.boost(2.0))
                .build();
        SearchRequest<Document> request = SearchRequest.<Document>builder()
                .query(composed)
                .filter(Query.eq(CATEGORY, "guide"))
                .limit(100)
                .build();
        SearchResult<Document> result = execute(snapshot, request);
        assertEquals(Set.of(0, 1, 3), ids(result));

        SearchExplanation<Document> exactWitness = explain(snapshot, request, 0);
        SearchExplanation<Document> sloppyWitness = explain(snapshot, request, 1);
        SearchExplanation<Document> filtered = explain(snapshot, request, 2);
        SearchExplanation<Document> reversed = explain(snapshot, request, 3);
        assertTrue(exactWitness.matched());
        assertTrue(render(exactWitness.detail()).contains("requestedSlop=2"));
        assertTrue(render(exactWitness.detail()).contains("minimumConsumedSlop=0"));
        assertTrue(sloppyWitness.matched());
        assertTrue(render(sloppyWitness.detail()).contains("minimumConsumedSlop=1"));
        assertFalse(filtered.matched());
        assertTrue(reversed.matched());
        assertFalse(render(reversed.detail()).contains("minimumConsumedSlop="));
        assertEquals(scores(result).get(0), exactWitness.score());
        assertEquals(scores(result).get(1), sloppyWitness.score());
    }

    @Test
    void emptySloppyPhraseReturnsBeforeMissingIndexResolution() {
        Analyzer empty = positioned(ignored -> List.of());
        TextField<Document> missing = TextField.of(BODY, empty);
        SearchRequest<Document> request = SearchRequest.of(
                SearchQueries.phrase(missing, "ignored", 7)
        );
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of());

        assertTrue(execute(snapshot, request).hits().isEmpty());
    }

    private static SearchSnapshot<Document> snapshot(
            TextField<Document> textField,
            List<Document> documents
    ) {
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(textField),
                IndexDefinition.equality(CATEGORY)
        ));
        for (Document document : documents) {
            snapshot = snapshot.add(document.id(), document);
        }
        return snapshot;
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

    private static SearchExplanation<Document> explain(
            SearchSnapshot<Document> snapshot,
            SearchRequest<Document> request,
            int docId
    ) {
        return SearchExecutionAccess.explain(
                snapshot,
                request,
                docId,
                new CandidatePlanner<>()
        );
    }

    private static SearchPlan<Document> plan(
            SearchSnapshot<Document> snapshot,
            SearchRequest<Document> request
    ) {
        return new SearchPlanner<Document>(new CandidatePlanner<>()).plan(
                RankedSearchInput.from(snapshot, request)
        );
    }

    private static Set<Integer> ids(SearchResult<Document> result) {
        return result.hits().stream()
                .map(SearchHit::document)
                .map(Document::id)
                .collect(Collectors.toSet());
    }

    private static Map<Integer, Double> scores(SearchResult<Document> result) {
        Map<Integer, Double> scores = new HashMap<>();
        for (SearchHit<Document> hit : result.hits()) {
            scores.put(hit.document().id(), hit.score());
        }
        return Map.copyOf(scores);
    }

    private static String render(ExplanationNode node) {
        StringBuilder result = new StringBuilder(node.description());
        node.children().forEach(child -> result.append('\n').append(render(child)));
        return result.toString();
    }

    private static Analyzer positioned(
            Function<String, List<AnalyzedToken>> positioned
    ) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return positioned.apply(text).stream()
                        .map(token -> new Token(token.term()))
                        .toList();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return positioned.apply(text);
            }
        };
    }

    private record Document(int id, String body, String category) {
    }
}
