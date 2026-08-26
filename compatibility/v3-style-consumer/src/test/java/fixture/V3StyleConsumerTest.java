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
}
