package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.function.Supplier;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.schema.*;
import io.github.patricklfdm.generalsearch.search.*;

/** A stopped configuration handle. Only start acquires resources; callers never own shared futures. */
final class PublicReplicaEngine<K, T> implements ReplicatedSearchEngine<K, T> {
    private final SearchEngineConfiguration<K, T> application;
    private final ReplicationGroupConfig<K, T> config;
    private volatile ReplicaNode<K, T> node;
    private volatile ReplicaState state = ReplicaState.STARTING;
    private volatile ReplicationException.Reason lastFailure;
    private volatile boolean closing;
    private CompletableFuture<ReplicationStatus> starting, activating;
    private Thread starter;

    PublicReplicaEngine(SearchEngineConfiguration<K, T> application, ReplicationGroupConfig<K, T> config) {
        this.application = application; this.config = config;
        // Pure validation: no filesystem identity lookup, engines, codecs, DNS or threads.
        AdmissionConfiguration.application(application);
        require(config.bounds().maxFrameBytes() >= 4096, CAPACITY_EXCEEDED, "runtime requires at least a 4096-byte frame bound");
        var replica = config.replicaDirectory().toAbsolutePath().normalize();
        var materialization = config.materialization().directory().toAbsolutePath().normalize();
        require(!replica.startsWith(materialization) && !materialization.startsWith(replica), STORAGE_FAILURE, "authority and materialization paths overlap");
    }

    @Override public synchronized CompletableFuture<ReplicationStatus> start() {
        if (closing) return failed(CLOSED, "replica handle closed");
        if (starting == null) {
            starting = new CompletableFuture<>();
            starter = Thread.ofPlatform().daemon().name("gse-replica-start-" + config.localNodeId().value()).unstarted(this::open);
            starter.start();
        }
        return starting.copy();
    }
    private void open() {
        ReplicaStore store = null;
        ReplicaApplication<K, T> materialized = null;
        ReplicaNode<K, T> opened = null;
        long begin = System.nanoTime();
        try {
            store = ReplicaStore.openAdmitted(config, application);
            ReplicaRuntimeHooks.CURRENT.get().node().at("AFTER_PUBLIC_AUTHORITY_OPEN", 0);
            require(!closing, CLOSED, "closed during startup");
            materialized = new ReplicaApplication<>(application, config.materialization(), config.bounds());
            materialized.validateManifest(store.manifest());
            opened = new ReplicaNode<>(config.replicaDirectory(), store.manifest(), config.localNodeId(), config.bounds(),
                    materialized, store, ReplicaRuntimeHooks.CURRENT.get().node(), ReplicaRuntimeHooks.CURRENT.get().network());
            store = null; materialized = null; // Node owns both, including incomplete-close retry.
            opened.recoveryDuration(System.nanoTime() - begin);
            synchronized (this) {
                node = opened;
                require(!closing, CLOSED, "closed during startup");
                state = ReplicaState.CATCHING_UP;
            }
            starting.complete(opened.status());
        } catch (Throwable error) {
            try { if (opened != null) opened.close(); }
            catch (Throwable cleanup) { error.addSuppressed(cleanup); node = opened; }
            try { if (materialized != null) materialized.close(); }
            catch (Throwable cleanup) { error.addSuppressed(cleanup); }
            try { if (store != null) store.close(); }
            catch (Throwable cleanup) { error.addSuppressed(cleanup); }
            lastFailure = error instanceof ReplicationException r ? r.reason() : STORAGE_FAILURE;
            state = closing ? ReplicaState.CLOSED : ReplicaState.FAILED;
            starting.completeExceptionally(error);
        }
    }

    private void leader() {
        require(config.localNodeId().equals(config.configuredLeaderId()), NOT_CONFIGURED_LEADER, "follower rejects application and leader commands");
    }
    private ReplicaNode<K, T> started() {
        require(!closing, CLOSED, "replica handle closed");
        var value = node;
        require(value != null && state == ReplicaState.CATCHING_UP, QUORUM_UNAVAILABLE, "replica has not successfully started");
        return value;
    }
    private <R> CompletableFuture<R> async(Supplier<CompletableFuture<R>> action) {
        try { return action.get(); } catch (RuntimeException error) { return CompletableFuture.failedFuture(error); }
    }
    private static <R> CompletableFuture<R> failed(ReplicationException.Reason reason, String message) {
        return CompletableFuture.failedFuture(new ReplicationException(reason, message));
    }
    @Override public CompletableFuture<ReplicationStatus> activateConfiguredLeader() { return activation(false); }
    @Override public CompletableFuture<ReplicationStatus> reconstructConfiguredLeader() { return activation(true); }
    private synchronized CompletableFuture<ReplicationStatus> activation(boolean replacement) {
        return async(() -> {
            leader(); var value = started();
            if (activating != null && !activating.isDone()) return activating.copy();
            if (replacement) require(!value.voter(), CONFLICTING_HISTORY, "reconstruction requires non-voter leader replacement");
            if (!replacement && value.status().state() == ReplicaState.READY) return CompletableFuture.completedFuture(value.status());
            activating = replacement ? value.reconstructLeader() : value.activate();
            return activating.copy();
        });
    }
    @Override public CompletableFuture<Long> catchUp(ReplicationNodeId peer) {
        return async(() -> { leader(); var value = started(); java.util.Objects.requireNonNull(peer, "peer"); return value.catchUp(peer); });
    }
    private CompletableFuture<Void> mutate(String operation, Function<ReplicaApplication<K, T>, byte[]> encoder) {
        return async(() -> { leader(); return started().mutate(operation, encoder); });
    }
    @Override public CompletableFuture<Void> add(T document) { return mutate("ADD", app -> app.documents("ADD", List.of(document))); }
    @Override public CompletableFuture<Void> update(T document) { return mutate("UPDATE", app -> app.documents("UPDATE", List.of(document))); }
    @Override public CompletableFuture<Void> remove(K id) { return mutate("REMOVE", app -> app.keys("REMOVE", List.of(id))); }
    @Override public CompletableFuture<Void> addAll(Collection<? extends T> documents) { return mutate("ADD_ALL", app -> app.documents("ADD_ALL", documents)); }
    @Override public CompletableFuture<Void> updateAll(Collection<? extends T> documents) { return mutate("UPDATE_ALL", app -> app.documents("UPDATE_ALL", documents)); }
    @Override public CompletableFuture<Void> removeAll(Collection<? extends K> ids) { return mutate("REMOVE_ALL", app -> app.keys("REMOVE_ALL", ids)); }
    @Override public CompletableFuture<Void> createIndex(IndexDefinition<T> definition) { return mutate("INDEX_CREATE", app -> app.index(definition)); }
    @Override public CompletableFuture<Void> dropIndex(String fieldName) { return mutate("INDEX_DROP", app -> app.dropIndex(fieldName)); }
    private <R> R read(Function<SearchEngine<K, T>, R> action) { leader(); return started().read(action); }
    @Override public T get(K id) { return read(engine -> engine.get(id)); }
    @Override public List<T> search(Query<T> query) { return read(engine -> engine.search(query)); }
    @Override public List<SearchHit<T>> searchTopK(RankedSearchRequest<T> request) { return read(engine -> engine.searchTopK(request)); }
    @Override public SearchResult<T> search(SearchRequest<T> request) { return read(engine -> engine.search(request)); }
    @Override public SearchPageResult<T> search(SearchPageRequest<T> request) { return read(engine -> engine.search(request)); }
    @Override public HighlightedSearchResult<T> search(HighlightedSearchRequest<T> request) { return read(engine -> engine.search(request)); }
    @Override public Optional<SearchExplanation<T>> explain(SearchRequest<T> request, K id) { return read(engine -> engine.explain(request, id)); }
    @Override public SearchEngineMetrics metrics() { return read(SearchEngine::metrics); }
    @Override public long currentSequence() { leader(); return started().currentSequence(); }
    @Override public SearchSchema<T, K> schema() { return application.schema(); }
    @Override public Field<T, ?> field(String name) { return schema().requireField(name); }
    @Override public <V> Field<T, V> field(String name, Class<V> valueType) { return schema().requireField(name, valueType); }
    @Override public TextField<T> textField(String name) { return schema().requireTextField(name); }
    @Override public CompletableFuture<Void> checkpoint() { return async(() -> started().checkpointLocal()); }
    @Override public CompletableFuture<DurableBackupResult> backup(DurableBackupRequest request) {
        return async(() -> { leader(); var value = started(); return value.backup(request); });
    }
    @Override public DurabilityMetrics durabilityMetrics() {
        var value = node;
        require(value != null, QUORUM_UNAVAILABLE, "local storage has not initialized");
        return value.durabilityMetrics();
    }
    @Override public ReplicationStatus replicationStatus() {
        var value = node;
        if (value != null) return value.status();
        return new ReplicationStatus(config.localNodeId(), config.localNodeId().equals(config.configuredLeaderId()) ? ReplicaRole.CONFIGURED_LEADER : ReplicaRole.FOLLOWER,
                state, false, 0, 0, 0, 0, 0, 0, 0, 0);
    }
    @Override public ReplicationDiagnostics replicationDiagnostics() {
        var value = node;
        if (value != null) return value.diagnostics();
        var peers = config.members().stream().filter(member -> !member.nodeId().equals(config.localNodeId()))
                .map(member -> new ReplicationPeerStatus(member.nodeId(), false, 0, 0, 0, Optional.empty())).toList();
        return new ReplicationDiagnostics(config.groupId(), config.configurationId(), Optional.empty(), NO_INCARNATION,
                replicationStatus(), 0, false, peers, Optional.empty(), Optional.ofNullable(lastFailure));
    }
    @Override public void close() {
        Thread opening; CompletableFuture<ReplicationStatus> attempt;
        synchronized (this) { closing = true; opening = starter; attempt = starting; }
        if (attempt != null && !attempt.isDone()) attempt.completeExceptionally(new ReplicationException(CLOSED, "closed during startup"));
        if (opening != null && opening != Thread.currentThread()) {
            try { opening.join(config.bounds().requestTimeoutMillis() + 100L); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); throw failure(CLOSED, "startup close interrupted", error); }
            require(!opening.isAlive(), CLOSED, "startup has not terminated; ownership retained for close retry");
        }
        var value = node;
        if (value != null) value.close();
        state = ReplicaState.CLOSED;
    }
}
