package fixture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import java.nio.file.Files;
import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.replication.ReplicaState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V5StyleConsumerTest {
    @TempDir
    Path temporary;

    @Test
    void constructsStoppedHandleWithoutOpeningProductionAuthority() throws Exception {
        var builder = V5StyleConsumer.declaration(temporary);
        assertEquals(3, builder.configuration().members().size());
        try (var engine = builder.build()) {
            assertEquals(ReplicaState.STARTING, engine.replicationStatus().state());
            assertEquals(0, engine.replicationStatus().applicationSequence());
            assertFalse(engine.replicationStatus().writeQuorumAvailable());
        }
        try (var files = Files.list(temporary)) { assertEquals(0, files.count()); }
    }
}
