package fixture.v52;

import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletionException;
import io.github.patricklfdm.generalsearch.replication.*;

/** New caller, unchanged old implementation bytecode, candidate runtime only. */
public final class DefaultReadProbe {
    public static void main(String[] args) {
        LegacyRunner.main(args);
        AutomaticReplicatedSearchEngine<Object, Object> engine = new LegacyImplementation();
        var token = new ReplicaReadToken(1, new ReplicationGroupId(new UUID(1, 2)), new UUID(3, 4), "00".repeat(32), 0);
        for (var policy : ReplicaReadPolicy.values()) {
            var options = new ReplicaReadOptions(policy,
                    policy == ReplicaReadPolicy.AT_LEAST_INDEX ? Optional.of(token) : Optional.empty(), 0);
            var future = engine.read(options, view -> { throw new AssertionError("default invoked callback"); });
            if (!future.isCompletedExceptionally()) throw new AssertionError("default did not reject immediately");
            try { future.join(); throw new AssertionError("default succeeded"); }
            catch (CompletionException error) {
                if (!(error.getCause() instanceof UnsupportedOperationException)) throw error;
            }
        }
        System.out.println("v52LegacyBinary=PASS compiledAgainst=published-5.1.0 defaultRead=unsupported");
    }
}
