package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/** Phase 1 declarations only. No code path opens storage or starts a worker. */
final class DisabledMembershipEngine<K, T> implements MembershipSearchEngine<K, T> {
    private final SearchEngineConfiguration<K, T> application;
    private final MembershipReplicaConfig<K, T> configuration;
    private volatile boolean closed;

    DisabledMembershipEngine(SearchEngineConfiguration<K, T> application, MembershipReplicaConfig<K, T> configuration) {
        this.application = application; this.configuration = configuration;
    }
    private static UnsupportedOperationException disabled() {
        return new UnsupportedOperationException("V5.3 membership runtime requires Phase 2/3 qualification");
    }
    private static <R> CompletableFuture<R> unavailable() { return CompletableFuture.failedFuture(disabled()); }
    @Override public CompletableFuture<MembershipReplicationStatus> start() { return unavailable(); }
    @Override public MembershipReplicationStatus leadershipStatus() {
        return new MembershipReplicationStatus(configuration.localIdentity().nodeId(),
                closed ? AutomaticReplicationState.CLOSED : AutomaticReplicationState.STOPPED,
                Optional.empty(), Optional.empty(), 0, Optional.empty(), 0, 0, 0, 0, 0, Optional.empty(), List.of());
    }
    @Override public MembershipView membershipStatus() { throw disabled(); }
    @Override public CompletableFuture<MembershipView> membership() { return unavailable(); }
    @Override public CompletableFuture<MembershipOperationStatus> submitMembershipChange(MembershipChangeRequest request) {
        Objects.requireNonNull(request, "request"); return unavailable();
    }
    @Override public CompletableFuture<MembershipOperationStatus> membershipOperation(MembershipOperationId id) {
        Objects.requireNonNull(id, "id"); return unavailable();
    }
    @Override public CompletableFuture<MembershipOperationStatus> cancelMembershipChange(MembershipOperationId id) {
        Objects.requireNonNull(id, "id"); return unavailable();
    }
    @Override public CompletableFuture<Void> retireMembershipResults(long through) {
        MembershipValidation.position(through); return unavailable();
    }
    @Override public CompletableFuture<MembershipMaintenancePlan> planMaintenance(ReplicationNodeId target) {
        Objects.requireNonNull(target, "target"); return unavailable();
    }
    @Override public CompletableFuture<Void> drainForMaintenance(MembershipMaintenancePlan plan) {
        Objects.requireNonNull(plan, "plan"); return unavailable();
    }
    @Override public CompletableFuture<Void> add(T document) { Objects.requireNonNull(document, "document"); return unavailable(); }
    @Override public CompletableFuture<Void> update(T document) { Objects.requireNonNull(document, "document"); return unavailable(); }
    @Override public CompletableFuture<Void> remove(K id) { Objects.requireNonNull(id, "id"); return unavailable(); }
    @Override public CompletableFuture<Void> addAll(Collection<? extends T> documents) { return bulk(documents); }
    @Override public CompletableFuture<Void> updateAll(Collection<? extends T> documents) { return bulk(documents); }
    @Override public CompletableFuture<Void> removeAll(Collection<? extends K> ids) { return bulk(ids); }
    private static CompletableFuture<Void> bulk(Collection<?> values) {
        Objects.requireNonNull(values, "values"); values.forEach(Objects::requireNonNull); return unavailable();
    }
    @Override public CompletableFuture<Void> createIndex(IndexDefinition<T> definition) {
        Objects.requireNonNull(definition, "definition"); return unavailable();
    }
    @Override public CompletableFuture<Void> dropIndex(String fieldName) { Objects.requireNonNull(fieldName, "fieldName"); return unavailable(); }
    @Override public T get(K id) { Objects.requireNonNull(id, "id"); throw disabled(); }
    @Override public List<T> search(Query<T> query) { Objects.requireNonNull(query, "query"); throw disabled(); }
    @Override public SearchSchema<T, K> schema() { return application.schema(); }
    @Override public SearchEngineMetrics metrics() { throw disabled(); }
    @Override public long currentSequence() { throw disabled(); }
    @Override public CompletableFuture<Void> checkpoint() { return unavailable(); }
    @Override public DurabilityMetrics durabilityMetrics() { throw disabled(); }
    @Override public CompletableFuture<DurableBackupResult> backup(DurableBackupRequest request) {
        Objects.requireNonNull(request, "request"); return unavailable();
    }
    @Override public void close() { closed = true; }
}
