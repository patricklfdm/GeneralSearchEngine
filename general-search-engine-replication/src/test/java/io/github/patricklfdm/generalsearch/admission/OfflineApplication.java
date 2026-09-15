package io.github.patricklfdm.generalsearch.admission;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.query.RangePlanningMode;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.Field;

/** External-package consumer shared by the public API tests and owned JVM harness. */
public final class OfflineApplication {
    public record Doc(int id, String value) { }
    public static final Field<Doc, Integer> ID = Field.of("id", Integer.class, Doc::id);
    public static final Field<Doc, String> VALUE = Field.of("value", String.class, Doc::value);
    public static final UUID GROUP = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private OfflineApplication() { }
    public static SearchEngineBuilder<Integer, Doc> builder() {
        return SearchEngine.builder(Doc.class, ID).index(IndexDefinition.equality(VALUE))
                .config(new SnapshotEngineConfig(31, 7, Duration.ofNanos(1_234_567)))
                .plannerConfig(new PlannerConfig(RangePlanningMode.FORCE_SCAN));
    }
    public static DurableStorageConfig<Integer, Doc> storage(Path path, int minor) {
        var builder = DurableStorageConfig.builder(path, new Codec()).format(new DurableStorageFormat("gse-durable", 1, minor))
                .storageIdentity("fixture-store").schemaIdentity("fixture-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(65536).maxBulkElements(1000).maxDocuments(10000)
                .checkpointWalBytes(1024).maxRetainedBytes(1 << 30);
        if (minor == 2) builder.maxDerivedStateBytes(1 << 20);
        return builder.build();
    }
    public static List<ReplicationGroupConfig<Integer, Doc>> configurations(Path root) {
        var members = java.util.stream.IntStream.range(1, 4).mapToObj(i -> new ReplicationMember(
                new ReplicationNodeId("node-" + i), new ReplicationEndpoint("127.0.0.1", 19100 + i))).toList();
        return members.stream().map(member -> new ReplicationGroupConfig<>(new ReplicationGroupId(GROUP), "config-v1",
                member.nodeId(), members.getFirst().nodeId(), members, root.resolve(member.nodeId().value()),
                storage(root.resolve("materialization-" + member.nodeId().value()), 2), ReplicationBounds.defaults())).toList();
    }
    public static ReplicationBootstrapRequest<Integer, Doc> request(Path root, Path source) {
        return new ReplicationBootstrapRequest<>(source == null ? ReplicationBootstrapSource.EMPTY : ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                source, configurations(root), root.resolve("operation"), 1 << 30, 1 << 30);
    }
    public static final class Codec implements DurableCodec<Integer, Doc> {
        public String codecId() { return "fixture-codec"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer key) { return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) { return ByteBuffer.wrap(bytes).getInt(); }
        public byte[] encodeDocument(Doc doc) { return (doc.id() + ":" + doc.value()).getBytes(StandardCharsets.UTF_8); }
        public Doc decodeDocument(byte[] bytes) { String[] parts = new String(bytes, StandardCharsets.UTF_8).split(":", 2); return new Doc(Integer.parseInt(parts[0]), parts[1]); }
    }
}
