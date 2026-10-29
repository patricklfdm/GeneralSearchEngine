package fixture.v52;

/** Old application bytecode links and runs against new packaged artifacts. */
public final class LegacyRunner {
    public static void main(String[] args) {
        var config = fixture.V51StyleConsumer.request(java.nio.file.Path.of(args[0]), null).replicas().getFirst();
        try (var handle = fixture.V51StyleConsumer.stopped(config)) {
            if (!handle.leadershipStatus().localNodeId().equals(config.localNodeId()))
                throw new AssertionError("legacy node identity");
        }
    }
}
