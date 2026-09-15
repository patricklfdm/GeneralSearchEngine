package io.github.patricklfdm.generalsearch.admission;

import static org.junit.jupiter.api.Assertions.*;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Public consumer package: cannot reach package-private replica initialization/codecs. */
class V50AdmissionDeclarationsTest {
    @TempDir Path directory;
    private static final UUID HISTORY = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String HASH = "ab".repeat(32);
    private static final Field<Doc, Integer> ID = Field.of("id", Integer.class, Doc::id);
    private static final Field<Doc, String> VALUE = Field.of("value", String.class, Doc::value);
    record Doc(int id, String value) { }

    @Test
    void immutableValuesCopyListsAndRetainCanonicalSchemaObjects() {
        var schema = SearchSchema.builder(Doc.class, ID).field(VALUE).build();
        var indexes = new ArrayList<IndexDefinition<Doc>>(List.of(IndexDefinition.equality(VALUE)));
        var config = new SearchEngineConfiguration<>(schema, indexes, SnapshotEngineConfig.DEFAULT, PlannerConfig.DEFAULT);
        var docs = new ArrayList<>(List.of(new Doc(1, "value")));
        var state = new DurableApplicationState<>(HISTORY, 41, docs, indexes);
        indexes.clear(); docs.clear();
        assertSame(schema, config.schema()); assertSame(VALUE, config.indexes().getFirst().field());
        assertEquals(1, state.documents().size()); assertEquals(1, state.indexes().size());
        assertThrows(UnsupportedOperationException.class, () -> config.indexes().clear());
        assertThrows(UnsupportedOperationException.class, () -> state.documents().clear());
        assertThrows(UnsupportedOperationException.class, config::newBuilder);
        assertThrows(IllegalArgumentException.class, () -> new DurableApplicationState<>(new UUID(0, 0), 0, List.of(), List.of()));
        assertThrows(IllegalArgumentException.class, () -> new DurableApplicationState<>(HISTORY, -1, List.of(), List.of()));
        assertThrows(NullPointerException.class, () -> new SearchEngineConfiguration<>(schema, null, SnapshotEngineConfig.DEFAULT, PlannerConfig.DEFAULT));
    }

    @Test
    void typedDeclarationsRemainReservedBeforeAnyCodecOrFilesystemWork() throws Exception {
        var calls = new AtomicInteger(); var codec = new Codec(calls);
        var configs = configurations(codec);
        var request = new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, null, configs,
                directory.resolve("operation"), 1 << 20, 1 << 20);
        var builder = SearchEngine.builder(Doc.class, ID).index(IndexDefinition.equality(VALUE));
        var plan = new ReplicationBootstrapPlan(configs.getFirst().groupId(), "config-v1", ReplicationBootstrapSource.EMPTY,
                null, configs.stream().map(ReplicationGroupConfig::replicaDirectory).toList(), HASH);
        var cleanup = new ReplicationCleanupPlan(request.operationDirectory(), HASH, List.of(), HASH, HASH);
        var replacement = new ReplicationReplacementPlan(request.operationDirectory(), directory.resolve("source"),
                configs.getFirst().localNodeId(), directory.resolve("replacement"), HASH, HASH, HASH);
        var verification = new DurableVerificationConfig<>("fixture-store", "fixture-schema", codec, 1, 1024, 1024, 10);
        calls.set(0);
        assertThrows(UnsupportedOperationException.class, builder::configuration);
        assertThrows(UnsupportedOperationException.class, () -> builder.readDurableBackup(directory.resolve("source"), verification, 1024));
        assertThrows(UnsupportedOperationException.class, () -> builder.writeDurableBackup(new DurableApplicationState<>(HISTORY, 41, List.of(), List.of()),
                configs.getFirst().materialization(), new DurableBackupRequest(directory.resolve("backup"), 1 << 20)));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.planBootstrap(builder, request));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.applyBootstrap(builder, request, plan));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.resumeBootstrap(builder, request, plan));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.readBootstrapResult(request.operationDirectory()));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.applyCleanup(cleanup));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.planReplacement(configs.getFirst(), directory.resolve("source"), request.operationDirectory()));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.applyReplacement(configs.getFirst(), replacement));
        assertThrows(UnsupportedOperationException.class, () -> ReplicationStorageOperations.resumeReplacement(configs.getFirst(), replacement));
        assertThrows(UnsupportedOperationException.class, () -> ReplicatedSearchEngines.builder(builder, configs.getFirst()).build());
        assertEquals(0, calls.get(), "reserved calls must not invoke application code");
        try (var files = Files.list(directory)) { assertEquals(0, files.count()); }
    }

    @Test
    void requestOrderSourceAndBoundsRejectBeforePlanning() {
        var configs = configurations(new Codec(new AtomicInteger()));
        var mutable = new ArrayList<>(configs);
        var request = new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, null, mutable, directory.resolve("operation"), 1, 1L << 40);
        mutable.clear(); assertEquals(3, request.replicas().size());
        assertThrows(UnsupportedOperationException.class, () -> request.replicas().clear());
        for (long invalid : new long[]{-1, 0, (1L << 40) + 1}) {
            assertThrows(IllegalArgumentException.class, () -> new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, null, configs, directory, invalid, 1));
            assertThrows(IllegalArgumentException.class, () -> new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, null, configs, directory, 1, invalid));
        }
        assertThrows(IllegalArgumentException.class, () -> new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, directory, configs, directory, 1, 1));
        assertThrows(IllegalArgumentException.class, () -> new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP, null, configs, directory, 1, 1));
        assertThrows(IllegalArgumentException.class, () -> new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, null, configs.reversed(), directory, 1, 1));
    }

    @Test
    void peerDiagnosticsRejectFabricatedProgressAndCopyPeers() {
        var node = new ReplicationNodeId("node-1");
        var peer = new ReplicationPeerStatus(new ReplicationNodeId("node-2"), false, 0, 0, 0, Optional.empty());
        var other = new ReplicationPeerStatus(new ReplicationNodeId("node-3"), true, 12, 10, 11, Optional.of(Instant.EPOCH));
        assertThrows(IllegalArgumentException.class, () -> new ReplicationPeerStatus(peer.nodeId(), true, 0, 0, 0, Optional.empty()));
        assertThrows(IllegalArgumentException.class, () -> new ReplicationPeerStatus(peer.nodeId(), false, 1, 2, 0, Optional.of(Instant.EPOCH)));
        assertThrows(IllegalArgumentException.class, () -> new ReplicationPeerStatus(peer.nodeId(), false, 1, 0, 2, Optional.of(Instant.EPOCH)));
        var status = new ReplicationStatus(node, ReplicaRole.CONFIGURED_LEADER, ReplicaState.STARTING, false, 0, 0, 0, 0, 0, 0, 0, 0);
        var peers = new ArrayList<>(List.of(peer, other));
        var diagnostics = new ReplicationDiagnostics(new ReplicationGroupId(HISTORY), "config-v1", Optional.empty(), new UUID(0, 0), status,
                0, false, peers, Optional.empty(), Optional.empty());
        peers.clear(); assertEquals(2, diagnostics.peers().size());
        assertThrows(IllegalArgumentException.class, () -> new ReplicationDiagnostics(diagnostics.groupId(), "config-v1", Optional.empty(), HISTORY,
                status, 0, false, diagnostics.peers(), Optional.empty(), Optional.empty()));
    }

    @Test
    void newInterfaceDefaultsPreserveThirdPartyImplementations() {
        var calls = new AtomicInteger();
        var engine = (ReplicatedSearchEngine<?, ?>) Proxy.newProxyInstance(getClass().getClassLoader(), new Class<?>[]{ReplicatedSearchEngine.class},
                (proxy, method, args) -> {
                    if (method.isDefault()) return InvocationHandler.invokeDefault(proxy, method, args);
                    calls.incrementAndGet(); throw new AssertionError("unexpected legacy dispatch");
                });
        assertThrows(UnsupportedOperationException.class, () -> engine.catchUp(new ReplicationNodeId("node-2")));
        assertThrows(UnsupportedOperationException.class, engine::reconstructConfiguredLeader);
        assertThrows(UnsupportedOperationException.class, engine::replicationDiagnostics);
        assertEquals(0, calls.get());
    }

    private List<ReplicationGroupConfig<Integer, Doc>> configurations(Codec codec) {
        var nodes = List.of(new ReplicationNodeId("node-1"), new ReplicationNodeId("node-2"), new ReplicationNodeId("node-3"));
        var members = new ArrayList<ReplicationMember>();
        for (int i = 0; i < 3; i++) members.add(new ReplicationMember(nodes.get(i), new ReplicationEndpoint("127.0.0.1", 19101 + i)));
        return nodes.stream().map(node -> new ReplicationGroupConfig<>(new ReplicationGroupId(HISTORY), "config-v1", node, nodes.getFirst(), members,
                directory.resolve(node.value()), DurableStorageConfig.builder(directory.resolve("materialized-" + node.value()), codec)
                .storageIdentity("fixture-store").schemaIdentity("fixture-schema").build(), ReplicationBounds.defaults())).toList();
    }
    record Codec(AtomicInteger calls) implements DurableCodec<Integer, Doc> {
        public String codecId() { calls.incrementAndGet(); return "fixture-codec"; }
        public int codecVersion() { calls.incrementAndGet(); return 1; }
        public byte[] encodeKey(Integer key) { calls.incrementAndGet(); return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) { calls.incrementAndGet(); return ByteBuffer.wrap(bytes).getInt(); }
        public byte[] encodeDocument(Doc doc) { calls.incrementAndGet(); return encodeKey(doc.id()); }
        public Doc decodeDocument(byte[] bytes) { calls.incrementAndGet(); return new Doc(decodeKey(bytes), "fixture"); }
    }
}
