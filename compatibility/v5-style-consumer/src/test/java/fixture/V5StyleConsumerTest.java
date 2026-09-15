package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V5StyleConsumerTest {
    @TempDir
    Path temporary;

    @Test
    void compilesFrozenDeclarationWithoutOpeningProductionAuthority() {
        var builder = V5StyleConsumer.declaration(temporary);
        assertEquals(3, builder.configuration().members().size());
        assertThrows(UnsupportedOperationException.class, builder::build);
    }
}
