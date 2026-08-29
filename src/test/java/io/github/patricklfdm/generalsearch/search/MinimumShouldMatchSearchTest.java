package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class MinimumShouldMatchSearchTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void preservesDefaultsAndAppliesZeroIntermediateAndAllThresholds() {
        SearchSnapshot<Document> snapshot = snapshot();
        SearchQuery<Document> alpha = SearchQueries.text(BODY_TEXT, "alpha");
        SearchQuery<Document> beta = SearchQueries.text(BODY_TEXT, "beta");
        SearchQuery<Document> gamma = SearchQueries.text(BODY_TEXT, "gamma");

        SearchQuery<Document> defaultShould = SearchQueries.<Document>bool()
                .should(alpha)
                .should(beta)
                .should(gamma)
                .build();
        SearchQuery<Document> explicitOne = SearchQueries.<Document>bool()
                .should(alpha)
                .should(beta)
                .should(gamma)
                .minimumShouldMatch(1)
                .build();
        assertEquals(
                execute(snapshot, defaultShould).hits(),
                execute(snapshot, explicitOne).hits()
        );

        SearchResult<Document> atLeastTwo = execute(
                snapshot,
                SearchQueries.<Document>bool()
                        .should(alpha)
                        .should(beta)
                        .should(gamma)
                        .minimumShouldMatch(2)
                        .build()
        );
        SearchResult<Document> allThree = execute(
                snapshot,
                SearchQueries.<Document>bool()
                        .should(alpha)
                        .should(beta)
                        .should(gamma)
                        .minimumShouldMatch(3)
                        .build()
        );
        assertEquals(Set.of(0, 1, 3, 4), ids(atLeastTwo));
        assertEquals(Set.of(0), ids(allThree));

        Map<Integer, Double> completeScores = scores(execute(snapshot, defaultShould));
        atLeastTwo.hits().forEach(hit -> assertEquals(
                completeScores.get(hit.document().id()),
                hit.score()
        ));

        SearchQuery<Document> defaultMust = SearchQueries.<Document>bool()
                .must(alpha)
                .should(beta)
                .should(gamma)
                .build();
        SearchQuery<Document> explicitZero = SearchQueries.<Document>bool()
                .must(alpha)
                .should(beta)
                .should(gamma)
                .minimumShouldMatch(0)
                .build();
        assertEquals(
                execute(snapshot, defaultMust).hits(),
                execute(snapshot, explicitZero).hits()
        );
        assertEquals(Set.of(0, 1, 2), ids(execute(snapshot, defaultMust)));
        assertEquals(Set.of(0, 1), ids(execute(
                snapshot,
                SearchQueries.<Document>bool()
                        .must(alpha)
                        .should(beta)
                        .should(gamma)
                        .minimumShouldMatch(1)
                        .build()
        )));
        assertEquals(Set.of(0), ids(execute(
                snapshot,
                SearchQueries.<Document>bool()
                        .must(alpha)
                        .should(beta)
                        .should(gamma)
                        .minimumShouldMatch(2)
                        .build()
                )));

        assertTrue(render(((BoolPlan<?>) plan(
                snapshot,
                SearchRequest.of(defaultShould)
        ).root()).explain(2)).contains("effectiveMinimumShouldMatch=1"));
        assertTrue(render(((BoolPlan<?>) plan(
                snapshot,
                SearchRequest.of(defaultMust)
        ).root()).explain(2)).contains("effectiveMinimumShouldMatch=0"));
    }

    @Test
    void countsOccurrencesZeroTermAndMatchedZeroScoreWithoutEarlyScoringStop() {
        SearchSnapshot<Document> snapshot = snapshot();
        SearchQuery<Document> alpha = SearchQueries.text(BODY_TEXT, "alpha");
        SearchQuery<Document> gamma = SearchQueries.text(BODY_TEXT, "gamma");

        SearchQuery<Document> duplicates = SearchQueries.<Document>bool()
                .should(alpha)
                .should(alpha)
                .should(gamma)
                .minimumShouldMatch(2)
                .build();
        assertEquals(Set.of(0, 1, 2), ids(execute(snapshot, duplicates)));

        double alphaScore = execute(snapshot, alpha).hits().stream()
                .filter(hit -> hit.document().id() == 2)
                .findFirst()
                .orElseThrow()
                .score();
        assertEquals(
                alphaScore * 2.0,
                scoreFor(execute(snapshot, duplicates), 2)
        );

        SearchQuery<Document> sameMustAndShould = SearchQueries.<Document>bool()
                .must(alpha)
                .should(alpha)
                .minimumShouldMatch(1)
                .build();
        assertEquals(Set.of(0, 1, 2), ids(execute(snapshot, sameMustAndShould)));

        SearchQuery<Document> zeroTerm = SearchQueries.text(BODY_TEXT, "---");
        SearchQuery<Document> requiresBoth = SearchQueries.<Document>bool()
                .should(alpha)
                .should(zeroTerm)
                .minimumShouldMatch(2)
                .build();
        assertTrue(execute(snapshot, requiresBoth).hits().isEmpty());

        SearchQuery<Document> matchedZeroScore = alpha
                .boost(Double.MIN_VALUE)
                .boost(Double.MIN_VALUE);
        SearchResult<Document> zeroScoreMatches = execute(
                snapshot,
                SearchQueries.<Document>bool()
                        .should(matchedZeroScore)
                        .minimumShouldMatch(1)
                        .build()
        );
        assertEquals(Set.of(0, 1, 2), ids(zeroScoreMatches));
        assertTrue(zeroScoreMatches.hits().stream()
                .allMatch(hit -> hit.score() == 0.0));
    }

    @Test
    void plansThresholdCandidatesAndExplainsNestedComposedTruth() {
        SearchSnapshot<Document> snapshot = snapshot();
        SearchQuery<Document> alpha = SearchQueries.text(BODY_TEXT, "alpha");
        SearchQuery<Document> beta = SearchQueries.text(BODY_TEXT, "beta");
        SearchQuery<Document> gamma = SearchQueries.text(BODY_TEXT, "gamma");
        SearchQuery<Document> threshold = SearchQueries.<Document>bool()
                .should(alpha)
                .should(beta)
                .should(gamma)
                .minimumShouldMatch(2)
                .build();
        SearchPlan<Document> thresholdPlan = plan(
                snapshot,
                SearchRequest.of(threshold)
        );
        assertEquals(
                Set.of(0, 1, 3, 4),
                candidateIds(thresholdPlan.root().candidates())
        );

        BoolPlan<?> boolPlan = (BoolPlan<?>) thresholdPlan.root();
        assertEquals(2, boolPlan.minimumShouldMatch());
        String matchingExplain = render(boolPlan.explain(1));
        String nonMatchingExplain = render(boolPlan.explain(2));
        assertTrue(matchingExplain.contains("effectiveMinimumShouldMatch=2"));
        assertTrue(matchingExplain.contains("matchedShouldCount=2"));
        assertTrue(nonMatchingExplain.contains("matchedShouldCount=1"));
        assertEquals(3, count(matchingExplain, "SHOULD clause"));

        SearchQuery<Document> phrase = SearchQueries.phrase(
                BODY_TEXT,
                "beta gamma",
                1
        );
        SearchQuery<Document> fuzzy = SearchQueries.fuzzy(BODY_TEXT, "gama");
        SearchQuery<Document> nested = SearchQueries.<Document>bool()
                .should(phrase.boost(2.0))
                .should(fuzzy)
                .minimumShouldMatch(2)
                .build();
        SearchRequest<Document> request = SearchRequest.<Document>builder()
                .query(nested)
                .filter(Query.eq(CATEGORY, "guide"))
                .limit(100)
                .build();
        SearchPlan<Document> nestedPlan = plan(snapshot, request);
        assertTrue(nestedPlan.root().candidates().get(4));
        assertFalse(nestedPlan.root().evaluate(4).matched());
        assertEquals(Set.of(0), ids(execute(snapshot, request)));

        SearchExplanation<Document> matched = explain(snapshot, request, 0);
        SearchExplanation<Document> filtered = explain(snapshot, request, 3);
        assertTrue(matched.matched());
        assertFalse(filtered.matched());
        assertTrue(render(filtered.detail()).contains(
                "effectiveMinimumShouldMatch=2"));
    }

    private static SearchSnapshot<Document> snapshot() {
        List<Document> documents = List.of(
                new Document(0, "alpha beta gamma", "guide"),
                new Document(1, "alpha beta", "guide"),
                new Document(2, "alpha", "guide"),
                new Document(3, "beta gamma", "reference"),
                new Document(4, "gamma beta delta", "guide")
        );
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(BODY_TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
        for (Document document : documents) {
            snapshot = snapshot.add(document.id(), document);
        }
        return snapshot;
    }

    private static SearchResult<Document> execute(
            SearchSnapshot<Document> snapshot,
            SearchQuery<Document> query
    ) {
        return execute(snapshot, SearchRequest.of(query));
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

    private static SearchPlan<Document> plan(
            SearchSnapshot<Document> snapshot,
            SearchRequest<Document> request
    ) {
        return new SearchPlanner<Document>(new CandidatePlanner<>()).plan(
                RankedSearchInput.from(snapshot, request)
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

    private static Set<Integer> ids(SearchResult<Document> result) {
        return result.hits().stream()
                .map(SearchHit::document)
                .map(Document::id)
                .collect(Collectors.toSet());
    }

    private static Map<Integer, Double> scores(SearchResult<Document> result) {
        return result.hits().stream().collect(Collectors.toMap(
                hit -> hit.document().id(),
                SearchHit::score
        ));
    }

    private static double scoreFor(SearchResult<Document> result, int id) {
        return result.hits().stream()
                .filter(hit -> hit.document().id() == id)
                .findFirst()
                .orElseThrow()
                .score();
    }

    private static Set<Integer> candidateIds(
            io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap candidates
    ) {
        Set<Integer> expectedRange = Set.of(0, 1, 2, 3, 4);
        return expectedRange.stream()
                .filter(candidates::get)
                .collect(Collectors.toSet());
    }

    private static String render(ExplanationNode node) {
        StringBuilder result = new StringBuilder(node.description());
        node.children().forEach(child -> result.append('\n').append(render(child)));
        return result.toString();
    }

    private static long count(String value, String needle) {
        return value.lines().filter(Predicate.isEqual(needle)).count();
    }

    private record Document(int id, String body, String category) {
    }
}
