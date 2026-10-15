package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import static io.github.patricklfdm.generalsearch.admission.V52MeasurementQueries.*;
import io.github.patricklfdm.generalsearch.replication.*;
import java.io.*;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/** Common external consumer compiled independently against published V5.1 and candidate. */
public final class V52MeasurementConsumer {
    public interface Reads {CompletableFuture<Map<String,Object>> read(Map<String,Object> request);}
    public static final ThreadLocal<String> callId=new ThreadLocal<>();
    public static BiConsumer<String,Map<String,Object>> observer=(name,row)->{};
    public static Function<Object,Map<String,Object>> diagnostics=engine->Map.of();
    public static final Set<String> MODES=Set.of("published-v51-legacy-strong","candidate-legacy-strong","candidate-explicit-strong","candidate-stale","candidate-minimum");
    public static ReplicationBounds bounds(){return new ReplicationBounds(1<<20,100,8,64,2,1200,25,65536,64L<<20,64L<<20);}
    public static List<AutomaticReplicationGroupConfig<Integer,Doc>> configs(Path root) throws IOException {
        var lines=Files.readAllLines(root.resolve("ports.txt"));var members=new ArrayList<ReplicationMember>();
        if(lines.size()!=3)throw new IllegalArgumentException("measurement member count");
        for(int i=0;i<3;i++)members.add(new ReplicationMember(new ReplicationNodeId("node-"+(i+1)),new ReplicationEndpoint("127.0.0.1",Integer.parseInt(lines.get(i)))));
        var group=new ReplicationGroupId(UUID.fromString(Files.readString(root.resolve("group-id.txt")).trim()));
        return members.stream().map(m->new AutomaticReplicationGroupConfig<>(group,"v52-measurement",m.nodeId(),members,
                root.resolve(m.nodeId().value()),V52MeasurementQueries.storage(root.resolve("app-"+m.nodeId().value())),bounds(),
                new AutomaticLeadershipPolicy(1200,3600,6000,9600))).toList();
    }
    private static synchronized void print(Object row){System.out.println(AdmissionJson.canonical(row));System.out.flush();}
    public static void event(String name,Map<String,Object> row){observer.accept(name,row);}
    private static Map<String,Object> status(AutomaticReplicatedSearchEngine<Integer,Doc> engine) {
        var s=engine.leadershipStatus();return Map.of("state",s.state().name(),"epoch",s.promisedEpoch(),"provenIndex",s.provenIndex(),
                "publishedIndex",s.appliedIndex(),"sequence",s.applicationSequence());
    }
    private static void finish(Map<String,Object> request,long received,long invoked,Map<String,Object> value,Throwable failure) {
        var row=new LinkedHashMap<String,Object>();row.put("opId",request.get("opId"));row.put("kind",request.get("kind"));
        row.put("receivedNanos",received);row.put("apiStartNanos",invoked);row.put("apiEndNanos",System.nanoTime());
        if(request.containsKey("document"))row.put("document",request.get("document"));
        if(failure==null){row.putAll(value);row.put("outcome","SUCCESS");}
        else {
            while((failure instanceof CompletionException||failure instanceof ExecutionException)&&failure.getCause()!=null)failure=failure.getCause();
            row.put("reason",failure.toString());row.put("outcome","VALIDATION_FAILURE");row.put("reasonCode",failure.getClass().getSimpleName());
            if(failure instanceof AutomaticReplicationException auto){row.put("reasonCode",auto.reason().name());row.put("outcome",auto.outcome().name());}
            else if(failure instanceof CancellationException)row.put("outcome","CANCELLED");
            else try {row.put("reasonCode",failure.getClass().getMethod("reason").invoke(failure).toString());row.put("outcome","REJECTED");}
                catch(ReflectiveOperationException absent){/* Published V5.1 has no explicit-read error type. */}
        }
        event(failure==null?"CLIENT_SUCCESS":"CLIENT_FAILURE",row);print(row);
    }
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath();String action=args[1];
        if(action.equals("setup")) {
            var sockets=new ArrayList<ServerSocket>();
            try {for(int i=0;i<3;i++)sockets.add(new ServerSocket(0));Files.write(root.resolve("ports.txt"),sockets.stream().map(s->Integer.toString(s.getLocalPort())).toList());}
            finally {for(var socket:sockets)socket.close();}
            var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,root.resolve("control/seed"),configs(root),root.resolve("operation"),1L<<30,1L<<30);
            AutomaticReplicationStorageOperations.applyBootstrap(measurementBuilder(),request,AutomaticReplicationStorageOperations.planBootstrap(measurementBuilder(),request));
            print(Map.of("status","SETUP"));return;
        }
        int ordinal=Integer.parseInt(action);String mode=args[2];if(!MODES.contains(mode))throw new IllegalArgumentException("measurement mode");
        var executor=new ThreadPoolExecutor(8,8,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(64),new ThreadPoolExecutor.AbortPolicy());
        var pending=new ArrayList<CompletableFuture<?>>();var ids=new HashSet<String>();
        try(var engine=AutomaticReplicatedSearchEngines.builder(measurementBuilder(),configs(root).get(ordinal-1)).build()) {
            Reads reads=mode.endsWith("legacy-strong")?request->CompletableFuture.completedFuture(Map.of("answer",answer(core(engine),(Map<String,Object>)request.get("query")))):
                    (Reads)Class.forName("io.github.patricklfdm.generalsearch.admission.V52MeasuredExplicitReads").getConstructor(AutomaticReplicatedSearchEngine.class,String.class).newInstance(engine,mode);
            engine.start().get(15,TimeUnit.SECONDS);
            var identity=new LinkedHashMap<String,Object>();identity.put("status","STARTED");identity.put("pid",ProcessHandle.current().pid());
            identity.put("node","node-"+ordinal);identity.put("mode",mode);identity.put("javaRuntime",System.getProperty("java.runtime.version"));identity.put("javaVendor",System.getProperty("java.vendor"));
            identity.put("coreSource",Path.of(io.github.patricklfdm.generalsearch.engine.SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString());
            identity.put("replicationSource",Path.of(AutomaticReplicatedSearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString());
            event("STARTED",identity);print(identity);
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;while((line=input.readLine())!=null) {
                    if(line.length()>16384)throw new IllegalArgumentException("measurement command bound");
                    var request=(Map<String,Object>)AdmissionJson.parse(line);String kind=(String)request.get("kind");
                    if(kind.equals("close"))break;
                    long received=System.nanoTime();String id=(String)request.get("opId");
                    if(id==null||id.length()>128||ids.size()>=4096||!ids.add(id))throw new IllegalArgumentException("measurement command identity/count");
                    if(!Set.of("status","probe","update","read").contains(kind))throw new IllegalArgumentException("measurement command kind");
                    event("CLIENT_RECEIVED",request);var completion=new CompletableFuture<Void>();pending.add(completion);
                    Runnable invoke=()->{
                        long invoked=System.nanoTime();callId.set(id);
                        try {
                            event("CLIENT_INVOKE",request);
                            CompletableFuture<Map<String,Object>> result;
                            if(kind.equals("status"))result=CompletableFuture.completedFuture(status(engine));
                            else if(kind.equals("probe"))result=CompletableFuture.completedFuture(Map.of("queues",diagnostics.apply(engine),"retainedBytes",engine.durabilityMetrics().retainedBytes()));
                            else if(kind.equals("update")) {
                                var doc=(Map<String,Object>)request.get("document");
                                result=engine.update(new Doc(((Number)doc.get("id")).intValue(),(String)doc.get("value"))).thenApply(ignored->Map.of());
                            } else result=reads.read(request);
                            result.whenComplete((value,failure)->{
                                try {finish(request,received,invoked,value,failure);completion.complete(null);}
                                catch(Throwable observerFailure){completion.completeExceptionally(observerFailure);}
                            });
                        } catch(Throwable failure) {
                            try {finish(request,received,invoked,Map.of(),failure);completion.complete(null);}
                            catch(Throwable observerFailure){completion.completeExceptionally(observerFailure);}
                        } finally {callId.remove();}
                    };
                    if(!kind.equals("read"))invoke.run(); // Preserve offered mutation invocation order.
                    else try {executor.execute(invoke);}
                    catch(RejectedExecutionException rejected){finish(request,received,received,Map.of(),rejected);completion.complete(null);}
                }
            }
            executor.shutdown();if(!executor.awaitTermination(30,TimeUnit.SECONDS))throw new IOException("measurement client executor did not stop");
            CompletableFuture.allOf(pending.toArray(CompletableFuture<?>[]::new)).get(30,TimeUnit.SECONDS);
            event("CLIENT_IDLE",Map.of("queues",diagnostics.apply(engine),"retainedBytes",engine.durabilityMetrics().retainedBytes()));
            engine.close();event("CLOSED",Map.of());
        } finally {executor.shutdownNow();}
    }
}
