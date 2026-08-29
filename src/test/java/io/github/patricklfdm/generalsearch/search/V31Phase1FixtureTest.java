package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.OptionalLong;
import java.util.Set;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class V31Phase1FixtureTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void phraseReferenceFreezesOrderedExtraGapSemantics() {
        var adjacent = List.of(
                term("alpha", 0),
                term("beta", 1)
        );
        assertEquals(OptionalLong.of(0), minimumSlop(
                slots(slot(0, "alpha"), slot(1, "beta")),
                adjacent
        ));
        assertEquals(OptionalLong.of(2), minimumSlop(
                slots(slot(0, "alpha"), slot(1, "beta")),
                List.of(term("alpha", 0), term("beta", 3))
        ));
        assertEquals(OptionalLong.empty(), minimumSlop(
                slots(slot(0, "alpha"), slot(2, "beta")),
                adjacent
        ));
        assertEquals(OptionalLong.empty(), minimumSlop(
                slots(slot(0, "alpha"), slot(1, "beta")),
                List.of(term("beta", 0), term("alpha", 1))
        ));
    }

    @Test
    void phraseReferenceCoversRepeatedAlternativesGapsAndMinimumWitness() {
        assertEquals(OptionalLong.empty(), minimumSlop(
                slots(slot(0, "echo"), slot(1, "echo")),
                List.of(term("echo", 4))
        ));
        assertEquals(OptionalLong.of(1), minimumSlop(
                slots(slot(0, "echo"), slot(1, "echo")),
                List.of(term("echo", 4), term("echo", 6))
        ));
        assertEquals(OptionalLong.of(0), minimumSlop(
                slots(slot(0, "usa", "united_states"), slot(1, "travel")),
                List.of(term("united_states", 7), term("travel", 8))
        ));
        assertEquals(OptionalLong.of(0), minimumSlop(
                slots(slot(0, "quick"), slot(2, "brown")),
                List.of(term("quick", 5), term("brown", 7))
        ));
        assertEquals(OptionalLong.of(0), minimumSlop(
                slots(slot(0, "alpha"), slot(1, "beta")),
                List.of(
                        term("alpha", 0),
                        term("beta", 4),
                        term("alpha", 10),
                        term("beta", 11)
                )
        ));
        assertEquals(OptionalLong.of(0), minimumSlop(
                slots(slot(0, "single")),
                List.of(term("single", Integer.MAX_VALUE))
        ));
        assertEquals(OptionalLong.empty(), minimumSlop(
                List.of(),
                List.of(term("single", 0))
        ));
    }

    @Test
    void boolReferenceFreezesDefaultsThresholdCountingAndFullScoring() {
        var matchTwo = match(2.0);
        var matchThree = match(3.0);
        var noMatch = noMatch();

        assertEquals(matchTwo, V31TestReference.evaluateBool(
                List.of(matchTwo),
                List.of(noMatch),
                null
        ));
        assertEquals(matchThree, V31TestReference.evaluateBool(
                List.of(),
                List.of(noMatch, matchThree),
                null
        ));
        assertEquals(noMatch, V31TestReference.evaluateBool(
                List.of(),
                List.of(noMatch, noMatch),
                null
        ));
        assertEquals(match(5.0), V31TestReference.evaluateBool(
                List.of(),
                List.of(matchTwo, noMatch, matchThree),
                2
        ));
        assertEquals(match(7.0), V31TestReference.evaluateBool(
                List.of(matchTwo),
                List.of(matchThree, match(0.0), noMatch, matchTwo),
                2
        ));
        assertEquals(matchTwo, V31TestReference.evaluateBool(
                List.of(matchTwo),
                List.of(),
                0
        ));
    }

    @Test
    void boolReferenceRejectsFrozenInvalidShapes() {
        assertThrows(IllegalArgumentException.class, () ->
                V31TestReference.evaluateBool(List.of(), List.of(), null));
        assertThrows(IllegalArgumentException.class, () ->
                V31TestReference.evaluateBool(
                        List.of(), List.of(match(1.0)), -1));
        assertThrows(IllegalArgumentException.class, () ->
                V31TestReference.evaluateBool(
                        List.of(), List.of(match(1.0)), 0));
        assertThrows(IllegalArgumentException.class, () ->
                V31TestReference.evaluateBool(
                        List.of(match(1.0)), List.of(), 1));
    }

    @Test
    void oldPhraseAndBoolFactoriesRetainV30Defaults() {
        List<Document> documents = List.of(
                new Document(0, "alpha beta"),
                new Document(1, "alpha noise beta"),
                new Document(2, "alpha"),
                new Document(3, "beta")
        );
        SearchSnapshot<Document> snapshot = snapshot(documents);

        SearchRequest<Document> phrase = SearchRequest.of(
                SearchQueries.phrase(BODY_TEXT, "alpha beta"));
        SearchResult<Document> phraseResult = execute(snapshot, phrase);
        assertEquals(List.of(0), ids(phraseResult));
        SearchExplanation<Document> phraseExplanation = SearchExecutionAccess.explain(
                snapshot,
                phrase,
                0,
                new CandidatePlanner<>()
        );
        assertTrue(phraseExplanation.matched());
        assertEquals(phraseResult.hits().getFirst().score(), phraseExplanation.score());

        SearchQuery<Document> mustWithUnmatchedShould = SearchQueries.<Document>bool()
                .must(SearchQueries.text(BODY_TEXT, "alpha"))
                .should(SearchQueries.text(BODY_TEXT, "unknown"))
                .build();
        assertEquals(Set.of(0, 1, 2), idSet(execute(
                snapshot,
                SearchRequest.of(mustWithUnmatchedShould)
        )));

        SearchQuery<Document> shouldOnly = SearchQueries.<Document>bool()
                .should(SearchQueries.text(BODY_TEXT, "alpha"))
                .should(SearchQueries.text(BODY_TEXT, "unknown"))
                .build();
        assertEquals(Set.of(0, 1, 2), idSet(execute(
                snapshot,
                SearchRequest.of(shouldOnly)
        )));
        assertTrue(execute(
                snapshot,
                SearchRequest.of(SearchQueries.<Document>bool()
                        .should(SearchQueries.text(BODY_TEXT, "unknown"))
                        .build())
        ).hits().isEmpty());
    }

    @Test
    void analyzerAndPositionTokenRetainPublishedV30Shape() {
        long abstractMethods = Arrays.stream(Analyzer.class.getDeclaredMethods())
                .filter(method -> Modifier.isAbstract(method.getModifiers()))
                .count();
        assertEquals(1, abstractMethods);
        assertTrue(Analyzer.class.isAnnotationPresent(FunctionalInterface.class));
        assertEquals(
                List.of("term", "positionIncrement"),
                Arrays.stream(AnalyzedToken.class.getRecordComponents())
                        .map(component -> component.getName())
                        .toList()
        );
        Analyzer lambda = text -> List.of();
        assertFalse(lambda.analyzeWithPositions("ignored") == null);
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

    private static SearchSnapshot<Document> snapshot(List<Document> documents) {
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(BODY_TEXT)
        ));
        for (Document document : documents) {
            snapshot = snapshot.add(document.id(), document);
        }
        return snapshot;
    }

    private static List<Integer> ids(SearchResult<Document> result) {
        return result.hits().stream()
                .map(SearchHit::document)
                .map(Document::id)
                .toList();
    }

    private static Set<Integer> idSet(SearchResult<Document> result) {
        return result.hits().stream()
                .map(SearchHit::document)
                .map(Document::id)
                .collect(Collectors.toSet());
    }

    private static OptionalLong minimumSlop(
            List<V31TestReference.PhraseSlot> slots,
            List<V31TestReference.PositionedTerm> document
    ) {
        return V31TestReference.minimumConsumedSlop(slots, document);
    }

    private static List<V31TestReference.PhraseSlot> slots(
            V31TestReference.PhraseSlot... slots
    ) {
        return List.of(slots);
    }

    private static V31TestReference.PhraseSlot slot(
            int relativePosition,
            String... alternatives
    ) {
        return new V31TestReference.PhraseSlot(
                relativePosition,
                List.of(alternatives)
        );
    }

    private static V31TestReference.PositionedTerm term(
            String term,
            int position
    ) {
        return new V31TestReference.PositionedTerm(term, position);
    }

    private static V31TestReference.Evaluation match(double score) {
        return new V31TestReference.Evaluation(true, score);
    }

    private static V31TestReference.Evaluation noMatch() {
        return new V31TestReference.Evaluation(false, 0.0);
    }

    private record Document(int id, String body) {
    }
}
