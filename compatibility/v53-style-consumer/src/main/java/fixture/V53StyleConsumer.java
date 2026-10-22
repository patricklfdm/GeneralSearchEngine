package fixture;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.Field;

/** External consumer compiled against packaged public APIs only. */
public final class V53StyleConsumer {
    public static final Field<ReadDocument, Integer> ID = Field.of("id", Integer.class, ReadDocument::id);
    public static final Field<ReadDocument, String> BODY = Field.of("body", String.class, ReadDocument::body);
    public static final java.util.concurrent.atomic.AtomicInteger CODEC_CALLS = new java.util.concurrent.atomic.AtomicInteger();
    private V53StyleConsumer() {}
    public static SearchEngineBuilder<Integer, ReadDocument> application() {
        return SearchEngine.builder(ReadDocument.class, ID).field(BODY).index(IndexDefinition.equality(BODY));
    }
    public static DurableStorageConfig<Integer, ReadDocument> storage(Path path) {
        return DurableStorageConfig.builder(path, new Codec()).storageIdentity("v53-consumer-store").schemaIdentity("v53-consumer-schema").build();
    }
    public static List<MembershipIdentity> members(int count) {
        return java.util.stream.IntStream.rangeClosed(1, count).mapToObj(n -> new MembershipIdentity(
                new ReplicationNodeId("node-"+n), new UUID(10, n), new ReplicationEndpoint("127.0.0.1", 19300+n))).toList();
    }
    public static MembershipRoot root() { return new MembershipRoot(new ReplicationGroupId(new UUID(1, 2)), new UUID(3, 4), "ab".repeat(32)); }
    public static MembershipReplicaConfig<Integer, ReadDocument> configuration(Path path, int count) {
        var peers = members(count); var bounds = ReplicationBounds.defaults();
        return new MembershipReplicaConfig<>(root(), peers.getFirst(), peers.subList(1, count), path.resolve("authority"),
                storage(path.resolve("application")), bounds, AutomaticLeadershipPolicy.forBounds(bounds));
    }
    public static MembershipBootstrapRequest<Integer, ReadDocument> bootstrap(Path path, int count) {
        return new MembershipBootstrapRequest<>(root().groupId(), "v53-consumer", MembershipBootstrapSource.EMPTY, Optional.empty(),
                members(count).stream().map(m -> new MembershipBootstrapTarget<>(m, path.resolve(m.nodeId().value()),
                        storage(path.resolve("app-"+m.nodeId().value())))).toList(), path.resolve("operation"), 1L << 26, 1L << 28);
    }
    /** Declaration coverage for all membership operations, without private implementation access. */
    public static List<CompletableFuture<?>> surface(MembershipSearchEngine<Integer, ReadDocument> engine) {
        var id = new MembershipOperationId(root(), 1);
        var request = new MembershipChangeRequest(id, "cd".repeat(32), MembershipChangeKind.ADD, members(4));
        var token = new ReplicaReadToken(1, root().groupId(), root().historyId(), root().manifestDigest(), 0);
        var maintenance = new MembershipMaintenancePlan(root(), "cd".repeat(32), members(3).getFirst().nodeId(),
                new UUID(6, 7), token, List.of(members(3).get(1).nodeId(), members(3).get(2).nodeId()));
        return List.of(engine.start(), engine.membership(), engine.submitMembershipChange(request), engine.membershipOperation(id),
                engine.cancelMembershipChange(id), engine.retireMembershipResults(0), engine.planMaintenance(maintenance.target()),
                engine.drainForMaintenance(maintenance), engine.read(new ReplicaReadOptions(ReplicaReadPolicy.LEADER_STRONG, Optional.empty(), 0), v -> v.get(1)));
    }
    /** A fresh process can verify disabled public admission without pretending to run a membership group. */
    public static void main(String[] args) {
        var config = configuration(Path.of(args[0]), Integer.parseInt(args[1]));
        System.err.println("coreSource=" + SearchEngine.class.getProtectionDomain().getCodeSource().getLocation());
        System.err.println("replicationSource=" + MembershipSearchEngines.class.getProtectionDomain().getCodeSource().getLocation());
        CODEC_CALLS.set(0);
        try (var engine = MembershipSearchEngines.builder(application(), config).build()) {
            for (var future : surface(engine)) {
                try { future.join(); throw new IllegalStateException("membership unexpectedly enabled"); }
                catch (CompletionException error) { if (!(error.getCause() instanceof UnsupportedOperationException)) throw error; }
            }
            if (CODEC_CALLS.get() != 0 || engine.leadershipStatus().state() != AutomaticReplicationState.STOPPED
                    || engine.leadershipStatus().membership().isPresent()) throw new IllegalStateException("disabled handle observation");
            System.out.println("{\"status\":\"PASS\",\"execution\":\"disabled-public-declarations\",\"protocol\":\""+MembershipSearchEngines.PROTOCOL+"\",\"members\":"+args[1]+",\"runtimeEnabled\":false}");
        }
    }
    private static final class Codec implements DurableCodec<Integer, ReadDocument> {
        public String codecId() { CODEC_CALLS.incrementAndGet(); return "v53-consumer-codec"; }
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
