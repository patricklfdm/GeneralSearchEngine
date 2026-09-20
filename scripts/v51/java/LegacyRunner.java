package fixture.v51;

/** Compiled with the exact published 5.0 JARs, then run with current artifacts. */
public final class LegacyRunner {
    public static void main(String[] args) {
        var builder=fixture.V5StyleConsumer.declaration(java.nio.file.Path.of(args[0]));
        try(var handle=builder.build()) {
            if(!handle.replicationStatus().localNodeId().equals(builder.configuration().localNodeId()))
                throw new AssertionError("legacy node identity");
        }
        System.out.println("v51LegacyBinaryConsumer=PASS compiledAgainst=published-5.0.0");
    }
}
