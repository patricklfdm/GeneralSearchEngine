package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class V3StyleConsumerTest {
    @Test
    void executesSupportedTextRequestThroughPublishedApiOnly() {
        assertEquals(
                List.of(1L, 2L),
                V3StyleConsumer.supportedTextSearch().hits().stream()
                        .map(hit -> hit.document().id())
                        .toList()
        );
    }

    @Test
    void executesStructuredTextHighlightingThroughPublishedApiOnly() {
        var result = V3StyleConsumer.supportedHighlightedTextSearch();

        assertEquals(List.of(1L), result.hits().stream()
                .map(hit -> hit.hit().document().id())
                .toList());
        assertEquals(
                List.of("museum", "museum"),
                result.hits().getFirst().highlights().getFirst().fragments().stream()
                        .map(fragment -> fragment.text())
                        .toList()
        );
    }

    @Test
    void executesExactSearchAfterThroughPublishedApiOnly() {
        var pages = V3StyleConsumer.supportedExactPagination();

        assertEquals(
                List.of(1L, 2L),
                pages.stream()
                        .flatMap(page -> page.hits().stream())
                        .map(hit -> hit.document().id())
                        .toList()
        );
        assertEquals(2L, pages.get(0).totalHits().orElseThrow());
        assertEquals(2L, pages.get(1).totalHits().orElseThrow());
        assertTrue(pages.get(0).nextCursor().isPresent());
        assertTrue(pages.get(1).nextCursor().isEmpty());
    }

    @Test
    void executesBoolBoostAndCrossFieldRequestThroughPublishedApiOnly() {
        assertEquals(
                List.of(1L),
                V3StyleConsumer.supportedCompositionSearch().hits().stream()
                        .map(hit -> hit.document().id())
                        .toList()
        );
    }

    @Test
    void executesExactPhraseThroughPublishedApiOnly() {
        assertEquals(
                List.of(1L, 2L),
                V3StyleConsumer.supportedPhraseSearch().hits().stream()
                        .map(hit -> hit.document().id())
                        .toList()
        );
    }

    @Test
    void executesSingleTermFuzzySearchThroughPublishedApiOnly() {
        assertEquals(
                List.of(1L),
                V3StyleConsumer.supportedFuzzySearch().hits().stream()
                        .map(hit -> hit.document().id())
                        .toList()
        );
    }

    @Test
    void executesOrderedPhraseSlopThroughPublishedApiOnly() {
        assertEquals(
                List.of(1L, 2L),
                V3StyleConsumer.supportedPhraseSlopSearch().hits().stream()
                        .map(hit -> hit.document().id())
                        .toList()
        );
    }

    @Test
    void executesMinimumShouldMatchThroughPublishedApiOnly() {
        assertEquals(
                List.of(1L),
                V3StyleConsumer.supportedMinimumShouldMatchSearch().hits().stream()
                        .map(hit -> hit.document().id())
                        .toList()
        );
    }

    @Test
    void explainsOneBusinessDocumentThroughPublishedApiOnly() {
        var explanation = V3StyleConsumer.supportedExplain();

        assertEquals(1L, explanation.document().id());
        assertTrue(explanation.matched());
        assertTrue(explanation.score() > 0.0);
        assertEquals("SEARCH REQUEST", explanation.detail().description());
    }
}
