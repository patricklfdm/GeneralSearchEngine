package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.net.ServerSocket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

final class ReplicaLeaderTestSupport {
    record Document(int id, String value) { }
    static final Field<Document, Integer> ID = Field.of("id", Integer.class, Document::id);
    static final Field<Document, String> VALUE = Field.of("value", String.class, Document::value);
    static final SearchSchema<Document, Integer> SCHEMA = SearchSchema.builder(Document.class, ID).field(VALUE).build();
    static final List<IndexDefinition<Document>> INDEXES = List.of(IndexDefinition.equality(VALUE));
    static final ReplicationNodeId LEADER = new ReplicationNodeId("node-1");
    static final ReplicationBounds BOUNDS = bounds(1200, 8);
    static ReplicationBounds bounds(int timeout, int pending) {
        return new ReplicationBounds(1024 * 1024, 100, 8, pending, 1, timeout, 20, 4096, 64 * 1024 * 1024, 64 * 1024 * 1024);
    }
    static final class Codec implements DurableCodec<Integer, Document> {
        public String codecId() { return "leader-fixture"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer key) { return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != 4) throw new IllegalArgumentException("bad key");
            return ByteBuffer.wrap(bytes).getInt();
        }
        public byte[] encodeDocument(Document document) {
            byte[] text = document.value().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(4 + text.length).putInt(document.id()).put(text).array();
        }
        public Document decodeDocument(byte[] bytes) {
            return new Document(ByteBuffer.wrap(bytes).getInt(), new String(bytes, 4, bytes.length - 4, StandardCharsets.UTF_8));
        }
    }
    static ReplicaApplication<Integer, Document> application(Path directory, ReplicationBounds bounds) {
        var config = DurableStorageConfig.builder(directory, new Codec()).storageIdentity("fixture-storage")
                .schemaIdentity("fixture-schema").maxDocuments(1000).maxBulkElements(100).build();
        return new ReplicaApplication<>(SCHEMA, INDEXES, config, bounds);
    }
    static ReplicaManifest manifest(List<Integer> ports) {
        var members = new ArrayList<ReplicationMember>();
        for (int i = 0; i < 3; i++) members.add(new ReplicationMember(new ReplicationNodeId("node-" + (i + 1)),
                new ReplicationEndpoint("127.0.0.1", ports.get(i))));
        String indexDigest = ReplicaFormat.sha256(ReplicaJson.encode(INDEXES.stream().map(ReplicaApplication::descriptor).sorted().toList(), 65536));
        return new ReplicaManifest(new ReplicationGroupId(UUID.fromString("33333333-3333-3333-3333-333333333333")),
                "leader-v1", LEADER, members, "leader-fixture", 1, "fixture-schema", 1, indexDigest);
    }
    static List<Integer> ports() throws IOException {
        var sockets = new ArrayList<ServerSocket>();
        try {
            for (int i = 0; i < 3; i++) sockets.add(new ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress()));
            return sockets.stream().map(ServerSocket::getLocalPort).toList();
        } finally { for (var socket : sockets) socket.close(); }
    }
    static final class Group implements AutoCloseable {
        final Path root;
        final ReplicaManifest manifest;
        final ReplicationBounds bounds;
        final List<ReplicaApplication<Integer, Document>> applications = new ArrayList<>();
        final List<ReplicaNode<Integer, Document>> nodes = new ArrayList<>();
        Group(Path root, ReplicationBounds bounds, ReplicaNode.Events events) throws IOException {
            this(root, bounds, events, ignored -> ReplicaTransport.Events.NONE);
        }
        Group(Path root, ReplicationBounds bounds, ReplicaNode.Events events,
              java.util.function.IntFunction<ReplicaTransport.Events> network) throws IOException {
            this.root = root; this.bounds = bounds; manifest = manifest(ports());
            try {
                for (int i = 0; i < 3; i++) {
                    var id = manifest.members().get(i).nodeId();
                    Path path = root.resolve(id.value());
                    ReplicaStore.initialize(path, manifest, id, bounds, ReplicaStore.Faults.NONE);
                    var app = application(root.resolve("app-" + i), bounds); applications.add(app);
                    nodes.add(new ReplicaNode<>(path, manifest, id, bounds, app, ReplicaStore.Faults.NONE,
                            i == 0 ? events : ReplicaNode.Events.NONE, network.apply(i)));
                }
            } catch (RuntimeException | Error error) { close(); throw error; }
        }
        ReplicaNode<Integer, Document> leader() { return nodes.getFirst(); }
        java.util.concurrent.CompletableFuture<Void> add(Document document) {
            return leader().submit("ADD", applications.getFirst().documents("ADD", List.of(document)));
        }
        @Override public void close() {
            for (var node : nodes) node.close();
            for (var app : applications) app.close();
        }
    }
}
