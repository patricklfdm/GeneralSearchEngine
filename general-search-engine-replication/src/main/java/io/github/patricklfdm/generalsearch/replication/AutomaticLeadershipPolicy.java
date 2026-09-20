package io.github.patricklfdm.generalsearch.replication;

import java.util.Objects;

/** Finite, bootstrap-bound automatic-mode timing policy; not a measured failover SLA. */
public record AutomaticLeadershipPolicy(
        int heartbeatIntervalMillis,
        int minElectionTimeoutMillis,
        int maxElectionTimeoutMillis,
        int operationTimeoutMillis
) {
    public AutomaticLeadershipPolicy {
        if (heartbeatIntervalMillis < 1 || heartbeatIntervalMillis > 300_000
                || minElectionTimeoutMillis < 3L * heartbeatIntervalMillis
                || maxElectionTimeoutMillis < (long) minElectionTimeoutMillis + heartbeatIntervalMillis
                || maxElectionTimeoutMillis > 1_500_000
                || operationTimeoutMillis < 1 || operationTimeoutMillis > 1_200_000) {
            throw new IllegalArgumentException("invalid automatic leadership timing policy");
        }
    }

    /** Derives heartbeat R, election 3R..5R and operation 4R from the request timeout. */
    public static AutomaticLeadershipPolicy forBounds(ReplicationBounds bounds) {
        int request = Objects.requireNonNull(bounds, "bounds").requestTimeoutMillis();
        return new AutomaticLeadershipPolicy(request, Math.multiplyExact(3, request),
                Math.multiplyExact(5, request), Math.multiplyExact(4, request));
    }
}
