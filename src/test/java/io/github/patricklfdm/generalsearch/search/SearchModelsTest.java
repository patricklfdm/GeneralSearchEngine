package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.ArrayList;
import java.util.List;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import org.junit.jupiter.api.Test;

class SearchModelsTest {
    @Test
    void resultCopiesPreservesAndExposesImmutableHits() {
        SearchHit<String> first = new SearchHit<>("first", 2.0);
        SearchHit<String> second = new SearchHit<>("second", 1.0);
        List<SearchHit<String>> supplied = new ArrayList<>(List.of(first, second));
        SearchResult<String> result = new SearchResult<>(supplied);
        supplied.clear();

        assertEquals(List.of(first, second), result.hits());
        assertThrows(UnsupportedOperationException.class,
                () -> result.hits().add(first));
        assertEquals(List.of(), new SearchResult<String>(List.of()).hits());
        assertThrows(NullPointerException.class,
                () -> new SearchResult<String>(null));
        assertThrows(NullPointerException.class,
                () -> new SearchResult<>(java.util.Arrays.asList(first, null)));
    }

    @Test
    void explanationModelsEnforceScoresAndImmutableChildren() {
        ExplanationNode child = new ExplanationNode(true, 0.0, "", List.of());
        List<ExplanationNode> supplied = new ArrayList<>(List.of(child));
        ExplanationNode root = new ExplanationNode(true, 2.0, "root", supplied);
        SearchExplanation<String> explanation =
                new SearchExplanation<>("document", true, 2.0, root);
        supplied.clear();

        assertEquals("document", explanation.document());
        assertEquals(root, explanation.detail());
        assertEquals(List.of(child), root.children());
        assertThrows(UnsupportedOperationException.class,
                () -> root.children().add(child));

        ExplanationNode unmatched = new ExplanationNode(false, 0.0, "miss", List.of());
        SearchExplanation<String> missed =
                new SearchExplanation<>("document", false, 0.0, unmatched);
        assertEquals(0.0, missed.score());
    }

    @Test
    void explanationModelsRejectInvalidConstruction() {
        ExplanationNode matched = new ExplanationNode(true, 1.0, "match", List.of());

        assertThrows(IllegalArgumentException.class,
                () -> new ExplanationNode(false, 1.0, "miss", List.of()));
        assertThrows(IllegalArgumentException.class,
                () -> new ExplanationNode(true, -1.0, "bad", List.of()));
        assertThrows(IllegalArgumentException.class,
                () -> new ExplanationNode(true, Double.NaN, "bad", List.of()));
        assertThrows(IllegalArgumentException.class,
                () -> new ExplanationNode(true, Double.POSITIVE_INFINITY, "bad", List.of()));
        assertThrows(NullPointerException.class,
                () -> new ExplanationNode(true, 0.0, null, List.of()));
        assertThrows(NullPointerException.class,
                () -> new ExplanationNode(true, 0.0, "bad", null));
        assertThrows(NullPointerException.class,
                () -> new ExplanationNode(
                        true, 0.0, "bad", java.util.Arrays.asList(matched, null)));

        assertThrows(NullPointerException.class,
                () -> new SearchExplanation<>(null, true, 1.0, matched));
        assertThrows(NullPointerException.class,
                () -> new SearchExplanation<>("document", true, 1.0, null));
        assertThrows(IllegalArgumentException.class,
                () -> new SearchExplanation<>("document", false, 1.0, matched));
        assertThrows(IllegalArgumentException.class,
                () -> new SearchExplanation<>("document", true, -1.0, matched));
        assertThrows(IllegalArgumentException.class,
                () -> new SearchExplanation<>("document", true, Double.NaN, matched));
        assertThrows(IllegalArgumentException.class,
                () -> new SearchExplanation<>(
                        "document", false, 0.0, new ExplanationNode(true, 0.0, "root", List.of())));
        assertThrows(IllegalArgumentException.class,
                () -> new SearchExplanation<>("document", true, 2.0, matched));
    }
}
