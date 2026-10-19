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
public final class V52StyleConsumer {
    public static final Field<ReadDocument, Integer> ID =
            Field.of("id", Integer.class, ReadDocument::id);
    public static final Field<ReadDocument, String> BODY =
            Field.of("body", String.class, ReadDocument::body);

    public static final java.util.concurrent.atomic.AtomicInteger CODEC_CALLS = new java.util.concurrent.atomic.AtomicInteger();

    private V52StyleConsumer() { }

    public static SearchEngineBuilder<Integer, ReadDocument> application() {
        return SearchEngine.builder(ReadDocument.class, ID).field(BODY).index(IndexDefinition.equality(BODY));
    }

    public static DurableStorageConfig<Integer, ReadDocument> storage(Path path) {
        return DurableStorageConfig.builder(path, new Codec())
                .storageIdentity("v52-consumer-store").schemaIdentity("v52-consumer-schema").build();
    }

    public static AutomaticReplicationBootstrapRequest<Integer, ReadDocument> request(Path root, Path backup) {
        var group = new ReplicationGroupId(UUID.randomUUID());
        var members = List.of(
                new ReplicationMember(new ReplicationNodeId("node-1"), new ReplicationEndpoint("127.0.0.1", 19701)),
                new ReplicationMember(new ReplicationNodeId("node-2"), new ReplicationEndpoint("127.0.0.1", 19702)),
                new ReplicationMember(new ReplicationNodeId("node-3"), new ReplicationEndpoint("127.0.0.1", 19703)));
        var bounds = ReplicationBounds.defaults();
        var policy = AutomaticLeadershipPolicy.forBounds(bounds);
        var replicas = members.stream().map(member -> new AutomaticReplicationGroupConfig<>(
                group, "v52-consumer-group", member.nodeId(), members,
                root.resolve(member.nodeId().value()), storage(root.resolve("app-" + member.nodeId().value())),
                bounds, policy)).toList();
        return new AutomaticReplicationBootstrapRequest<>(backup == null
                ? ReplicationBootstrapSource.EMPTY : ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                backup, replicas, root.resolve("bootstrap"), 1L << 26, 1L << 28);
    }

    public static AutomaticReplicatedSearchEngine<Integer, ReadDocument> stopped(
            AutomaticReplicationGroupConfig<Integer, ReadDocument> configuration) {
        return AutomaticReplicatedSearchEngines.builder(application(), configuration).build();
    }

    /** Complete new read surface compiles against packaged public types only. */
    public static java.util.List<Object> surface(ReplicaReadView<Integer, ReadDocument> view,
            io.github.patricklfdm.generalsearch.query.Query<ReadDocument> query,
            io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest<ReadDocument> ranked,
            io.github.patricklfdm.generalsearch.search.SearchRequest<ReadDocument> request,
            io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest<ReadDocument> highlighted) {
        return java.util.Arrays.asList(view.get(1), view.search(query), view.searchTopK(ranked),
                view.search(request), view.search(highlighted), view.explain(request, 1), view.currentSequence());
    }

    /** Explicit cleanup remains limited to an eligible uncommitted operation. */
    public static void cleanup(Path operation) {
        var plan = AutomaticReplicationStorageOperations.planCleanup(operation);
        AutomaticReplicationStorageOperations.applyCleanup(plan);
    }

    /** Binary/source coverage of the opt-in interface and failure classification. */
    public static java.util.concurrent.CompletableFuture<AutomaticReplicationStatus> start(
            AutomaticReplicatedSearchEngine<Integer, ReadDocument> engine) {
        return engine.start();
    }

    public static boolean definitelyNotSubmitted(AutomaticReplicationException error) {
        return error.outcome() == AutomaticReplicationException.Outcome.NOT_SUBMITTED;
    }

    private static final class Codec implements DurableCodec<Integer, ReadDocument> {
        public String codecId() { CODEC_CALLS.incrementAndGet(); return "v52-consumer-codec"; }
        public int codecVersion() { CODEC_CALLS.incrementAndGet(); return 1; }
        public byte[] encodeKey(Integer key) { CODEC_CALLS.incrementAndGet(); return ByteBuffer.allocate(4).putInt(key).array(); }
        public Integer decodeKey(byte[] bytes) {
            CODEC_CALLS.incrementAndGet();
            if (bytes.length != 4) throw new IllegalArgumentException("key length");
            return ByteBuffer.wrap(bytes).getInt();
        }
        public byte[] encodeDocument(ReadDocument document) {
            CODEC_CALLS.incrementAndGet();
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            return ByteBuffer.allocate(8 + body.length).putInt(document.id()).putInt(body.length).put(body).array();
        }
        public ReadDocument decodeDocument(byte[] bytes) {
            CODEC_CALLS.incrementAndGet();
            if (bytes.length < 8) throw new IllegalArgumentException("document length");
            var input = ByteBuffer.wrap(bytes); int id = input.getInt(), size = input.getInt();
            if (size != input.remaining()) throw new IllegalArgumentException("body length");
            byte[] body = new byte[size]; input.get(body);
            return new ReadDocument(id, new String(body, StandardCharsets.UTF_8));
        }
    }
}
