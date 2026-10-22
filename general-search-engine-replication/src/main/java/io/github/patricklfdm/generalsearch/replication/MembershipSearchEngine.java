package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.function.Function;

/** Separate membership capability; legacy fixed-three engines do not implement it. */
public interface MembershipSearchEngine<K, T> extends DurableSearchEngine<K, T> {
    CompletableFuture<MembershipReplicationStatus> start();
    MembershipReplicationStatus leadershipStatus();
    MembershipView membershipStatus();
    CompletableFuture<MembershipView> membership();
    CompletableFuture<MembershipOperationStatus> submitMembershipChange(MembershipChangeRequest request);
    CompletableFuture<MembershipOperationStatus> membershipOperation(MembershipOperationId id);
    CompletableFuture<MembershipOperationStatus> cancelMembershipChange(MembershipOperationId id);
    CompletableFuture<Void> retireMembershipResults(long through);
    CompletableFuture<MembershipMaintenancePlan> planMaintenance(ReplicationNodeId target);
    CompletableFuture<Void> drainForMaintenance(MembershipMaintenancePlan plan);

    /** Existing history-bound read semantics; implementations must explicitly enable the capability. */
    default <R> CompletableFuture<ReplicaReadResult<R>> read(ReplicaReadOptions options,
            Function<ReplicaReadView<K, T>, R> reader) {
        Objects.requireNonNull(options, "options"); Objects.requireNonNull(reader, "reader");
        return CompletableFuture.failedFuture(new UnsupportedOperationException("membership reads are not enabled"));
    }
}
