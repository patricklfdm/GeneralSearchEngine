package fixture;

import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.util.concurrent.CompletionException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53StyleConsumerTest {
    @TempDir Path root;
    @Test void publicSurfaceRejectsExecutionForEveryStableSizeWithoutIoOrCodecCalls() throws Exception {
        for (int count : new int[] {3, 4, 5}) {
            var config = V53StyleConsumer.configuration(root, count);
            var request = V53StyleConsumer.bootstrap(root, count);
            V53StyleConsumer.CODEC_CALLS.set(0);
            try (var engine = MembershipSearchEngines.builder(V53StyleConsumer.application(), config).build()) {
                for (var future : V53StyleConsumer.surface(engine)) {
                    assertTrue(future.isCompletedExceptionally());
                    assertInstanceOf(UnsupportedOperationException.class, assertThrows(CompletionException.class, future::join).getCause());
                }
                assertEquals(AutomaticReplicationState.STOPPED, engine.leadershipStatus().state());
                assertTrue(engine.leadershipStatus().membership().isEmpty());
                assertThrows(UnsupportedOperationException.class, () -> MembershipStorageOperations.planBootstrap(V53StyleConsumer.application(), request));
            }
            assertEquals(0, V53StyleConsumer.CODEC_CALLS.get());
            try (var files = Files.list(root)) { assertEquals(0, files.count()); }
        }
    }
}
