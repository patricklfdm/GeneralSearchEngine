package fixture.v51;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.search.*;

/** Compiled only against external JARs; no package-private product/test access. */
public final class AutomaticConsumer {
    record Doc(int id) { }
    static final Field<Doc, Integer> ID = Field.of("id", Integer.class, Doc::id);
    public static void require(boolean value, String message) { if (!value) throw new AssertionError(message); }
    static void disabled(Runnable call) {
        try { call.run(); throw new AssertionError("automatic operation admitted in Phase 1"); }
        catch (AutomaticReplicationException expected) {
            require(expected.reason() == AutomaticReplicationException.Reason.NOT_READY, "reason");
            require(expected.outcome() == AutomaticReplicationException.Outcome.NOT_APPLICABLE, "outcome");
            require(expected.observedLeader().isEmpty(), "invented leader hint");
        }
    }
    public static List<AutomaticReplicationGroupConfig<Integer, Doc>> configs(Path root, AtomicInteger calls) {
        var members = new ArrayList<ReplicationMember>();
        for (int i=1;i<=3;i++) members.add(new ReplicationMember(new ReplicationNodeId("node-"+i),new ReplicationEndpoint("127.0.0.1",19600+i)));
        var result = new ArrayList<AutomaticReplicationGroupConfig<Integer, Doc>>();
        for (int i=1;i<=3;i++) {
            var store=DurableStorageConfig.builder(root.resolve("materialized-"+i),new Codec(calls))
                    .storageIdentity("fixture-store").schemaIdentity("fixture-schema").build();
            result.add(new AutomaticReplicationGroupConfig<>(new ReplicationGroupId(UUID.fromString("11111111-1111-1111-1111-111111111111")),
                    "automatic-fixture",members.get(i-1).nodeId(),members,root.resolve("node-"+i),store,
                    ReplicationBounds.defaults(),AutomaticLeadershipPolicy.forBounds(ReplicationBounds.defaults())));
        }
        return result;
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectory(root);
        var calls=new AtomicInteger();var configs=configs(root,calls);
        var mutable=new ArrayList<>(configs);var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,mutable,root.resolve("operation"),1L<<30,1L<<30);
        mutable.clear();require(request.replicas().size()==3,"request alias");
        var app=SearchEngine.builder(Doc.class,ID);var builder=AutomaticReplicatedSearchEngines.builder(app,configs.getFirst());
        require(builder.applicationBuilder()==app && builder.configuration()==configs.getFirst(),"builder arguments");
        calls.set(0);
        disabled(builder::build);
        require(calls.get()==0,"codec callback before disabled guard");
        try(var paths=Files.list(root)){require(paths.findAny().isEmpty(),"disabled operation created a file");}
        var plan=AutomaticReplicationStorageOperations.planBootstrap(app,request);
        try(var paths=Files.list(root)){require(paths.findAny().isEmpty(),"planning created a file");}
        var result=AutomaticReplicationStorageOperations.applyBootstrap(app,request,plan);
        require(result.equals(AutomaticReplicationStorageOperations.readBootstrapResult(request.operationDirectory())),"committed receipt");
        require(result.equals(AutomaticReplicationStorageOperations.resumeBootstrap(app,request,plan)),"idempotent resume");
        System.out.println("v51ExternalConsumer=PASS disabledEntries=1 offlineBootstrap=PASS runtime=not-enabled");
    }
    /** Compile-only full inherited surface. No fake runtime stands in for these operations. */
    static void compileLifecycle(AutomaticReplicatedSearchEngine<Integer, Doc> engine, Path backup) {
        engine.start();engine.leadershipStatus();engine.add(new Doc(1));engine.update(new Doc(1));engine.remove(1);
        engine.addAll(List.of(new Doc(1)));engine.updateAll(List.of(new Doc(1)));engine.removeAll(List.of(1));
        engine.createIndex(IndexDefinition.equality(ID));engine.dropIndex("id");engine.get(1);
        engine.search((Query<Doc>)null);engine.search((SearchRequest<Doc>)null);engine.search((SearchPageRequest<Doc>)null);
        engine.search((HighlightedSearchRequest<Doc>)null);engine.searchTopK((RankedSearchRequest<Doc>)null);
        engine.explain(null,1);engine.currentSequence();engine.metrics();engine.schema();
        engine.field("id");engine.field("id",Integer.class);engine.textField("text");
        engine.checkpoint();engine.backup((DurableBackupRequest)null);engine.durabilityMetrics();engine.lastReopenReport();engine.close();
    }
    record Codec(AtomicInteger calls) implements DurableCodec<Integer, Doc> {
        public String codecId(){calls.incrementAndGet();return "fixture-codec";}
        public int codecVersion(){calls.incrementAndGet();return 1;}
        public byte[] encodeKey(Integer key){calls.incrementAndGet();throw new AssertionError("encode key");}
        public Integer decodeKey(byte[] value){calls.incrementAndGet();throw new AssertionError("decode key");}
        public byte[] encodeDocument(Doc doc){calls.incrementAndGet();throw new AssertionError("encode document");}
        public Doc decodeDocument(byte[] value){calls.incrementAndGet();throw new AssertionError("decode document");}
    }
}
