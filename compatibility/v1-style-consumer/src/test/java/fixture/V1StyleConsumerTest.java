package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import java.util.List;
import org.junit.jupiter.api.Test;

class V1StyleConsumerTest {
    @Test void originalManualSchemaAndStructuredQueryStillExecute() {
        assertEquals(List.of(new V1StyleConsumer.Item(1L,"books",20)),V1StyleConsumer.search());
    }
}
