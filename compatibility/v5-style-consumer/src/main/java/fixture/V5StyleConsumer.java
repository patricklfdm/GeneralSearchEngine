package fixture;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.replication.ReplicatedSearchEngineBuilder;
import io.github.patricklfdm.generalsearch.replication.ReplicatedSearchEngines;
import io.github.patricklfdm.generalsearch.replication.ReplicationBounds;
import io.github.patricklfdm.generalsearch.replication.ReplicationEndpoint;
import io.github.patricklfdm.generalsearch.replication.ReplicationGroupConfig;
import io.github.patricklfdm.generalsearch.replication.ReplicationGroupId;
import io.github.patricklfdm.generalsearch.replication.ReplicationMember;
import io.github.patricklfdm.generalsearch.replication.ReplicationNodeId;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Framework-independent consumer of the declaration-only V5 API. */
public final class V5StyleConsumer {
    private static final Field<V5Document, Integer> ID =
            Field.of("id", Integer.class, V5Document::id);

    private V5StyleConsumer() {
    }

    public static ReplicatedSearchEngineBuilder<Integer, V5Document> declaration(
            Path root
    ) {
        ReplicationNodeId one = new ReplicationNodeId("node-1");
        ReplicationNodeId two = new ReplicationNodeId("node-2");
        ReplicationNodeId three = new ReplicationNodeId("node-3");
        DurableStorageConfig<Integer, V5Document> materialization =
                DurableStorageConfig.builder(root.resolve("materialized"), new Codec())
                        .storageIdentity("v50-consumer-store")
                        .schemaIdentity("v50-consumer-schema")
                        .build();
        ReplicationGroupConfig<Integer, V5Document> group =
                new ReplicationGroupConfig<>(
                        new ReplicationGroupId(UUID.fromString(
                                "22222222-2222-2222-2222-222222222222")),
                        "v50-consumer-config", one, one,
                        List.of(
                                new ReplicationMember(one,
                                        new ReplicationEndpoint("10.0.0.1", 19501)),
                                new ReplicationMember(two,
                                        new ReplicationEndpoint("10.0.0.2", 19501)),
                                new ReplicationMember(three,
                                        new ReplicationEndpoint("10.0.0.3", 19501))),
                        root.resolve("replica"), materialization,
                        ReplicationBounds.defaults());
        return ReplicatedSearchEngines.builder(
                SearchEngine.builder(V5Document.class, ID), group);
    }

    private static final class Codec implements DurableCodec<Integer, V5Document> {
        public String codecId() { return "v50-consumer-codec"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(4).putInt(key).array();
        }
        public Integer decodeKey(byte[] bytes) { return ByteBuffer.wrap(bytes).getInt(); }
        public byte[] encodeDocument(V5Document document) {
            return encodeKey(document.id());
        }
        public V5Document decodeDocument(byte[] bytes) {
            return new V5Document(decodeKey(bytes), "fixture");
        }
    }
}
