package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.admission.AdmissionJson;
import java.io.*;
import java.net.ServerSocket;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.BiConsumer;

/** External JAR-only consumer. Hooks can observe calls; every operation uses public APIs. */
public final class PublicRuntimeConsumer {
    public record Doc(int id,String value) { }
    public static final Field<Doc,Integer> ID=Field.of("id",Integer.class,Doc::id);
    public static final Field<Doc,String> VALUE=Field.of("value",String.class,Doc::value);
    public static BiConsumer<String,Map<String,Object>> observer=(event,row)->{};
    public static SearchEngineBuilder<Integer,Doc> builder(){return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.equality(VALUE)).config(new SnapshotEngineConfig(64,16,java.time.Duration.ofMillis(1)));}
    public static final class Codec implements DurableCodec<Integer,Doc> {
        public String codecId(){return "public-runtime-codec";}public int codecVersion(){return 1;}
        public byte[] encodeKey(Integer id){return ByteBuffer.allocate(4).putInt(id).array();}
        public Integer decodeKey(byte[] bytes){return ByteBuffer.wrap(bytes).getInt();}
        public byte[] encodeDocument(Doc doc){byte[] value=doc.value().getBytes(StandardCharsets.UTF_8);return ByteBuffer.allocate(4+value.length).putInt(doc.id()).put(value).array();}
        public Doc decodeDocument(byte[] bytes){return new Doc(ByteBuffer.wrap(bytes).getInt(),new String(bytes,4,bytes.length-4,StandardCharsets.UTF_8));}
    }
    public static DurableStorageConfig<Integer,Doc> storage(Path directory) {
        return DurableStorageConfig.builder(directory,new Codec()).storageIdentity("public-runtime-store").schemaIdentity("public-runtime-schema").maxDocuments(1000).maxBulkElements(100).build();
    }
    public static ReplicationBounds bounds(){return new ReplicationBounds(1<<20,100,8,16,2,1200,25,65536,64L<<20,64L<<20);}
    public static List<AutomaticReplicationGroupConfig<Integer,Doc>> configs(Path root) throws IOException {
        var lines=Files.readAllLines(root.resolve("ports.txt"));var members=new ArrayList<ReplicationMember>();
        for(int i=0;i<3;i++)members.add(new ReplicationMember(new ReplicationNodeId("node-"+(i+1)),new ReplicationEndpoint("127.0.0.1",Integer.parseInt(lines.get(i)))));
        int operationTimeout=Files.exists(root.resolve("operation-timeout.txt"))?Integer.parseInt(Files.readString(root.resolve("operation-timeout.txt")).trim()):9600;
        return members.stream().map(m->new AutomaticReplicationGroupConfig<>(new ReplicationGroupId(UUID.fromString("11111111-1111-1111-1111-111111111111")),"public-runtime-fixture",m.nodeId(),members,
                root.resolve(m.nodeId().value()),storage(root.resolve("app-"+m.nodeId().value())),bounds(),new AutomaticLeadershipPolicy(1200,3600,6000,operationTimeout))).toList();
    }
    private static void print(Object row){System.out.println(AdmissionJson.canonical(row));System.out.flush();}
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath();String action=args[1];
        if(action.equals("setup")) {
            var sockets=new ArrayList<ServerSocket>();try {for(int i=0;i<3;i++)sockets.add(new ServerSocket(0));Files.write(root.resolve("ports.txt"),sockets.stream().map(s->Integer.toString(s.getLocalPort())).toList());}
            finally {for(var socket:sockets)socket.close();}
            var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,configs(root),root.resolve("operation"),1L<<30,1L<<30);
            AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,AutomaticReplicationStorageOperations.planBootstrap(builder(),request));
            print(Map.of("status","SETUP","admission","public-bootstrap"));return;
        }
        if(action.equals("control")) {
            System.err.println("controlSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
            var restored=storage(root.resolve("restored"));builder().restoreDurableBackup(root.resolve("backup"),restored);
            try(var engine=builder().buildDurable(restored)) {
                print(Map.of("sequence",engine.currentSequence(),"documents",engine.search(d->true).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList()));
            }
            return;
        }
        int ordinal=Integer.parseInt(action);
        try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),configs(root).get(ordinal-1)).build()) {
            if(engine.leadershipStatus().state()!=AutomaticReplicationState.STOPPED)throw new AssertionError("stopped handle");
            var cancelled=engine.start();cancelled.cancel(true);var started=engine.start().get(15,TimeUnit.SECONDS);
            if(started.state()!=AutomaticReplicationState.FOLLOWER)throw new AssertionError("local follower startup");
            observer.accept("STARTED",Map.of("node",started.localNodeId().value()));print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;while((line=input.readLine())!=null) {
                    var command=(Map<String,Object>)AdmissionJson.parse(line);String name=(String)command.get("command");
                    var result=new LinkedHashMap<String,Object>();result.put("command",name);result.put("accepted",true);
                    try {
                        if(name.equals("status")){var status=engine.leadershipStatus();result.put("state",status.state().name());result.put("epoch",status.promisedEpoch());result.put("provenIndex",status.provenIndex());result.put("sequence",status.applicationSequence());}
                        else if(name.equals("add")||name.equals("update")) {
                            var doc=new Doc(((Number)command.get("id")).intValue(),(String)command.get("value"));observer.accept("CALL",command);
                            (name.equals("add")?engine.add(doc):engine.update(doc)).get(15,TimeUnit.SECONDS);long index=engine.leadershipStatus().appliedIndex();
                            result.put("index",index);observer.accept("SUCCESS",Map.of("index",index,"id",doc.id(),"value",doc.value()));
                        } else if(name.equals("query")) {
                            var before=engine.leadershipStatus();var docs=engine.search(d->true).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList();var after=engine.leadershipStatus();
                            result.put("documents",docs);observer.accept("READ",Map.of("before",before.provenIndex(),"index",after.appliedIndex(),"epoch",after.activeEpoch(),"sequence",after.applicationSequence(),"documents",docs));
                        } else if(name.equals("checkpoint")){engine.checkpoint().get(15,TimeUnit.SECONDS);result.put("sequence",engine.durabilityMetrics().checkpointSequence());}
                        else if(name.equals("backup")){engine.backup(new DurableBackupRequest(root.resolve("backup"),1<<20)).get(15,TimeUnit.SECONDS);result.put("sequence",engine.durabilityMetrics().currentSequence());}
                        else if(name.equals("close")){engine.close();observer.accept("CLOSED",Map.of());print(result);break;}
                        else throw new IllegalArgumentException(name);
                    }catch(Exception error){
                        result.put("accepted",false);result.put("reason",error.toString());
                        Throwable cause=error;
                        while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
                        if(cause instanceof AutomaticReplicationException failure){result.put("reasonCode",failure.reason().name());result.put("outcome",failure.outcome().name());}
                    }
                    print(result);
                }
            }
        }
    }
}
