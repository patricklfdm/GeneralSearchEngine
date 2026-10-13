package fixture;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.Field;

/** A separately built application using only the core and replication JARs. */
public final class V51StyleConsumer {
    public static final Field<AutomaticDocument, Integer> ID =
            Field.of("id", Integer.class, AutomaticDocument::id);
    public static final Field<AutomaticDocument, String> BODY =
            Field.of("body", String.class, AutomaticDocument::body);

    private V51StyleConsumer() { }

    public static SearchEngineBuilder<Integer, AutomaticDocument> application() {
        return SearchEngine.builder(AutomaticDocument.class, ID).field(BODY).index(IndexDefinition.equality(BODY));
    }

    public static DurableStorageConfig<Integer, AutomaticDocument> storage(Path path) {
        return DurableStorageConfig.builder(path, new Codec())
                .storageIdentity("v51-consumer-store").schemaIdentity("v51-consumer-schema").build();
    }

    public static AutomaticReplicationBootstrapRequest<Integer, AutomaticDocument> request(Path root, Path backup) {
        var group = new ReplicationGroupId(UUID.randomUUID());
        var members = List.of(
                new ReplicationMember(new ReplicationNodeId("node-1"), new ReplicationEndpoint("127.0.0.1", 19601)),
                new ReplicationMember(new ReplicationNodeId("node-2"), new ReplicationEndpoint("127.0.0.1", 19602)),
                new ReplicationMember(new ReplicationNodeId("node-3"), new ReplicationEndpoint("127.0.0.1", 19603)));
        var bounds = ReplicationBounds.defaults();
        var policy = AutomaticLeadershipPolicy.forBounds(bounds);
        var replicas = members.stream().map(member -> new AutomaticReplicationGroupConfig<>(
                group, "v51-consumer-group", member.nodeId(), members,
                root.resolve(member.nodeId().value()), storage(root.resolve("app-" + member.nodeId().value())),
                bounds, policy)).toList();
        return new AutomaticReplicationBootstrapRequest<>(backup == null
                ? ReplicationBootstrapSource.EMPTY : ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                backup, replicas, root.resolve("bootstrap"), 1L << 26, 1L << 28);
    }

    public static AutomaticReplicatedSearchEngine<Integer, AutomaticDocument> stopped(
            AutomaticReplicationGroupConfig<Integer, AutomaticDocument> configuration) {
        return AutomaticReplicatedSearchEngines.builder(application(), configuration).build();
    }

    /** Explicit cleanup remains limited to an eligible uncommitted operation. */
    public static void cleanup(Path operation) {
        var plan = AutomaticReplicationStorageOperations.planCleanup(operation);
        AutomaticReplicationStorageOperations.applyCleanup(plan);
    }

    /** Binary/source coverage of the opt-in interface and failure classification. */
    public static java.util.concurrent.CompletableFuture<AutomaticReplicationStatus> start(
            AutomaticReplicatedSearchEngine<Integer, AutomaticDocument> engine) {
        return engine.start();
    }

    public static boolean definitelyNotSubmitted(AutomaticReplicationException error) {
        return error.outcome() == AutomaticReplicationException.Outcome.NOT_SUBMITTED;
    }

    private static final class Codec implements DurableCodec<Integer, AutomaticDocument> {
        public String codecId() { return "v51-consumer-codec"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer key) { return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != 4) throw new IllegalArgumentException("key length");
            return ByteBuffer.wrap(bytes).getInt();
        }
        public byte[] encodeDocument(AutomaticDocument document) {
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(8 + body.length).putInt(document.id()).putInt(body.length).put(body).array();
        }
        public AutomaticDocument decodeDocument(byte[] bytes) {
            if (bytes.length < 8) throw new IllegalArgumentException("document length");
            var input = ByteBuffer.wrap(bytes); int id = input.getInt(), size = input.getInt();
            if (size != input.remaining()) throw new IllegalArgumentException("body length");
            byte[] body = new byte[size]; input.get(body);
            return new AutomaticDocument(id, new String(body, StandardCharsets.UTF_8));
        }
    }
}
