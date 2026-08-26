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
    void explainsOneBusinessDocumentThroughPublishedApiOnly() {
        var explanation = V3StyleConsumer.supportedExplain();

        assertEquals(1L, explanation.document().id());
        assertTrue(explanation.matched());
        assertTrue(explanation.score() > 0.0);
        assertEquals("SEARCH REQUEST", explanation.detail().description());
    }
}
