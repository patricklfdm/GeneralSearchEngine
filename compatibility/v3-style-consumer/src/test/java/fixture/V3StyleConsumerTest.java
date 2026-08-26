package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;

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
}
