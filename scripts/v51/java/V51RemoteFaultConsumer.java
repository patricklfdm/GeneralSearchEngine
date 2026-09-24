package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Frozen remote two-field fault schedule; all authority, reads and writes use public APIs. */
public final class V51RemoteFaultConsumer {
    private static java.util.function.Consumer<String> sampleBoundary;
    private static Path rootForBackup;
    private static synchronized void print(Object value){System.out.println(AdmissionJson.canonical(value));System.out.flush();}
    private static java.util.List<AutomaticReplicationGroupConfig<Integer,Doc>> groups(Path root) throws Exception {
        String cell=Files.readString(root.resolve("cell.txt")).trim();
        int documentBytes=cell.equals("interrupted-transfer")?4100:cell.equals("minority-capacity")?20004:4096;
        var group=new ReplicationGroupId(UUID.fromString(Files.readString(root.resolve("group-id.txt")).trim()));
        return configs(root).stream().map(c->new AutomaticReplicationGroupConfig<>(group,"phase6-fault-v1",c.localNodeId(),c.members(),
                c.replicaDirectory(),io.github.patricklfdm.generalsearch.durability.DurableStorageConfig.builder(c.materialization().directory(),new Codec())
                    .format(new io.github.patricklfdm.generalsearch.durability.DurableStorageFormat("gse-durable",1,2))
                    .storageIdentity("public-runtime-store").schemaIdentity("public-runtime-schema")
                    .maxDocuments(1024).maxBulkElements(16).maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(documentBytes)
                    .checkpointWalBytes(32L<<20).maxRetainedBytes(128L<<20).maxDerivedStateBytes(4L<<20).build(),
                new ReplicationBounds(1<<20,16,4,4,2,1200,25,4096,
                    cell.equals("minority-capacity")&&c.localNodeId().value().equals("node-3")?128L<<10:64L<<20,64L<<20),
                new AutomaticLeadershipPolicy(1200,3600,6000,9600))).toList();
    }
    private static Map<String,Object> configuration(AutomaticReplicationGroupConfig<Integer,Doc> c) throws Exception {
        var row=new LinkedHashMap<String,Object>();
        for(Object part:List.of(c.bounds(),c.leadershipPolicy()))
            for(var field:part.getClass().getRecordComponents())row.put(field.getName(),field.getAccessor().invoke(part));
        var app=c.materialization();
        for(String name:List.of("maxDocuments","maxBulkElements","maxEncodedKeyBytes","maxEncodedDocumentBytes","checkpointWalBytes","maxRetainedBytes","maxDerivedStateBytes"))
            row.put(name,app.getClass().getMethod(name).invoke(app));
        return row;
    }
    @SuppressWarnings("unchecked") private static void execute(AutomaticReplicatedSearchEngine<Integer,Doc> engine,Map<String,Object> request) {
        var result=new LinkedHashMap<String,Object>(request);String kind=(String)request.get("kind");
        observer.accept("CLIENT_INVOKE",request);long start=System.nanoTime();
        var completed=new java.util.concurrent.atomic.AtomicLong();
        try {
            switch(kind) {
                case "status" -> {if(request.containsKey("boundary"))sampleBoundary.accept((String)request.get("boundary"));var s=engine.leadershipStatus();result.put("state",s.state().name());result.put("epoch",s.promisedEpoch());result.put("provenIndex",s.provenIndex());result.put("appliedIndex",s.appliedIndex());}
                case "addAll" -> engine.addAll(((List<Map<String,Object>>)request.get("documents")).stream().map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList()).whenComplete((v,e)->completed.set(System.nanoTime())).get(15,TimeUnit.SECONDS);
                case "read" -> {
                    var seen=new AtomicBoolean();
                    result.put("documents",engine.search(doc->{if(seen.compareAndSet(false,true))observer.accept("READ_CALLBACK",Map.of("opId",request.get("opId")));return true;})
                            .stream().map(d->Map.of("id",d.id(),"value",d.value())).toList());
                }
                case "checkpoint" -> engine.checkpoint().get(15,TimeUnit.SECONDS);
                case "backup" -> {var backup=engine.backup(new io.github.patricklfdm.generalsearch.durability.DurableBackupRequest(rootForBackup,1<<20)).get(15,TimeUnit.SECONDS);result.put("sequence",backup.sequence());result.put("contentIdentity",backup.contentIdentity());}
                default -> throw new IllegalArgumentException(kind);
            }
            result.put("apiStartNanos",start);result.put("apiEndNanos",completed.get()==0?System.nanoTime():completed.get());result.put("outcome","SUCCESS");observer.accept("CLIENT_SUCCESS",result);
        }catch(Exception error) {
            Throwable cause=error;while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
            result.put("apiStartNanos",start);result.put("apiEndNanos",completed.get()==0?System.nanoTime():completed.get());result.put("reason",cause.toString());
            result.put("outcome",cause instanceof AutomaticReplicationException a?a.outcome().name():"VALIDATION_FAILURE");
            if(cause instanceof AutomaticReplicationException a)result.put("reasonCode",a.reason().name());
            observer.accept("CLIENT_FAILURE",result);
        }
        print(result);
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);rootForBackup=root.resolve("backup");V51Measurement.cloudMode=true;var app=builder().plannerConfig(new io.github.patricklfdm.generalsearch.query.PlannerConfig(io.github.patricklfdm.generalsearch.query.RangePlanningMode.FORCE_SCAN)).config(new SnapshotEngineConfig(31,16,Duration.ofNanos(1234567)));
        var configs=groups(root);
        if(args[1].equals("setup")) {
            var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,configs,root.resolve("operation"),64L<<20,256L<<20);
            AutomaticReplicationStorageOperations.applyBootstrap(app,request,AutomaticReplicationStorageOperations.planBootstrap(app,request));return;
        }
        int ordinal=Integer.parseInt(args[1]),generation=Integer.parseInt(args[3]);
        try(var engine=AutomaticReplicatedSearchEngines.builder(app,configs.get(ordinal-1)).build()) {
            if(engine.start().get(15,TimeUnit.SECONDS).state()!=AutomaticReplicationState.FOLLOWER)throw new AssertionError("remote fault startup");
            observer.accept("FAULT_CONFIGURATION",configuration(configs.get(ordinal-1)));
            var plan=V51RichWorkload.plan(root.resolve("plan.json"));var identity=new LinkedHashMap<>(V51Measurement.identity("candidate-v5.1-remote-fault","node-"+ordinal,plan,AutomaticReplicatedSearchEngines.class));
            identity.put("generation",generation);identity.put("cloudPlanSha256",V51RichWorkload.digest(AdmissionJson.parse(Files.readString(root.resolve("cloud-plan.json")))));observer.accept("PERFORMANCE_IDENTITY",identity);observer.accept("STARTED",Map.of("node","node-"+ordinal));
            var failure=new java.util.concurrent.atomic.AtomicReference<Throwable>();
            sampleBoundary=boundary->{try{
                long samplingStart=System.nanoTime();var row=new LinkedHashMap<>(PerformanceTelemetry.resources());row.put("samplingStartNanos",samplingStart);row.put("boundary",boundary);row.put("threads",java.lang.management.ManagementFactory.getThreadMXBean().getThreadCount());
                row.put("networkIo","unsupported: namespace-wide Linux counters");var s=engine.leadershipStatus();
                row.put("state",s.state().name());row.put("pending",s.pendingOperations());row.put("retainedBytes",engine.durabilityMetrics().retainedBytes());
                var queues=new LinkedHashMap<>(diagnostics.apply(engine));
                var outbound=(Map<?,?>)queues.get("outboundAvailable");
                queues.put("outboundAvailable",outbound.entrySet().stream().map(e->Map.of("node",e.getKey(),"available",e.getValue())).toList());
                row.put("queues",queues);
                observer.accept("PERFORMANCE_SAMPLE",row);
            }catch(Throwable e){failure.set(e);}};
            sampleBoundary.accept("start");
            var sampler=Executors.newSingleThreadScheduledExecutor(r->Thread.ofPlatform().daemon().name("fault-sampler").unstarted(r));
            sampler.scheduleAtFixedRate(()->sampleBoundary.accept("periodic"),1,1,TimeUnit.SECONDS);
            var callers=new ThreadPoolExecutor(4,4,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(16));
            print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;
                while((line=input.readLine())!=null) {
                    if(failure.get()!=null)throw new IllegalStateException("fault sampler failed",failure.get());
                    @SuppressWarnings("unchecked") var request=(Map<String,Object>)AdmissionJson.parse(line);
                    if(request.get("kind").equals("close"))break;
                    callers.execute(()->execute(engine,request));
                }
            }finally{
                callers.shutdown();if(!callers.awaitTermination(15,TimeUnit.SECONDS))throw new IllegalStateException("fault clients not drained");
                sampler.shutdown();if(!sampler.awaitTermination(5,TimeUnit.SECONDS))throw new IllegalStateException("fault sampler not stopped");
            }
            sampleBoundary.accept("pre-close");engine.close();sampleBoundary.accept("closed");observer.accept("CLOSED",Map.of());
            if(failure.get()!=null)throw new IllegalStateException("fault sampler failed",failure.get());
        }
    }
}
