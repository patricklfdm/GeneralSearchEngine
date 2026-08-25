package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.util.List;
import org.junit.jupiter.api.Test;

class V2StyleConsumerTest {
    @Test
    void generatedConfigurationSupportsTheCompleteTravelFlow() {
        V2StyleConsumer.SearchResult result = V2StyleConsumer.search();

        assertEquals(List.of(1L, 2L), result.structured().stream()
                .map(TravelPlace::id)
                .toList());
        assertEquals(List.of(1L, 2L), result.ranked().stream()
                .map(hit -> hit.document().id())
                .toList());
        assertEquals(List.of(1L, 3L), result.highlyRated().stream()
                .map(TravelPlace::id)
                .toList());
        assertSame(TravelPlaceSearchFields.RATING,
                TravelPlaceSearchFields.SCHEMA.requireField("rating"));
        assertSame(TravelPlaceSearchFields.DESCRIPTION,
                TravelPlaceSearchFields.SCHEMA.requireField("description"));
    }
}
