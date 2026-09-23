package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.replication.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** External public client. Cancellation/close use only the original public handle and futures. */
public final class PublicLifecycleConsumer {
    private final AutomaticReplicationGroupConfig<Integer,Doc> config;
    private volatile AutomaticReplicatedSearchEngine<Integer,Doc> engine;
    private final Map<String,CompletableFuture<Void>> pending=new ConcurrentHashMap<>();
    private PublicLifecycleConsumer(AutomaticReplicationGroupConfig<Integer,Doc> config){this.config=config;}
    private static synchronized void print(Object row){System.out.println(AdmissionJson.canonical(row));System.out.flush();}
    private void open() throws Exception {
        engine=AutomaticReplicatedSearchEngines.builder(builder(),config).build();
        var status=engine.start().get(20,TimeUnit.SECONDS);
        if(status.state()!=AutomaticReplicationState.FOLLOWER)throw new AssertionError("local follower startup");
        observer.accept("STARTED",Map.of("node",config.localNodeId().value()));
    }
    private static void failure(Map<String,Object> response,Throwable cause) {
        while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
        response.put("outcome",cause instanceof CancellationException?"CANCELLED":
                cause instanceof AutomaticReplicationException automatic?automatic.outcome().name():"VALIDATION_FAILURE");
        if(cause instanceof AutomaticReplicationException automatic)response.put("reasonCode",automatic.reason().name());
        response.put("errorType",cause.getClass().getName());response.put("reason",cause.toString());
    }
    @SuppressWarnings("unchecked") private void execute(Map<String,Object> command) {
        String kind=(String)command.get("kind"),id=(String)command.get("opId");
        var result=new LinkedHashMap<String,Object>(command);observer.accept("CLIENT_INVOKE",command);
        try {
            switch(kind) {
                case "status" -> {
                    var status=engine.leadershipStatus();result.put("state",status.state().name());result.put("epoch",status.promisedEpoch());
                    result.put("appliedIndex",status.appliedIndex());result.put("provenIndex",status.provenIndex());
                    result.put("sequence",status.applicationSequence());result.put("pending",status.pendingOperations());
                }
                case "addAll" -> {
                    var docs=((List<Map<String,Object>>)command.get("documents")).stream().map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList();
                    var future=engine.addAll(docs);pending.put(id,future);observer.accept("CLIENT_ENQUEUED",command);
                    try{future.get(20,TimeUnit.SECONDS);}finally{pending.remove(id);}
                }
                case "read" -> {
                    var entered=new AtomicBoolean();
                    result.put("documents",engine.search(doc->{
                        if(entered.compareAndSet(false,true))observer.accept("READ_CALLBACK",Map.of("opId",id));return true;
                    }).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList());
                }
                case "backup" -> {
                    var backup=engine.backup(new io.github.patricklfdm.generalsearch.durability.DurableBackupRequest(Path.of((String)command.get("target")),1<<20)).get(20,TimeUnit.SECONDS);
                    result.put("sequence",backup.sequence());result.put("contentIdentity",backup.contentIdentity());
                    result.put("sourceHistory",backup.sourceHistory().toString());
                }
                case "cancel" -> {
                    var future=pending.get((String)command.get("target"));
                    if(future==null)throw new IllegalStateException("target future is not pending");
                    result.put("cancelled",future.cancel(true));observer.accept("CLIENT_CANCEL",result);
                }
                case "closeHandle" -> {engine.close();observer.accept("HANDLE_CLOSED",Map.of());}
                case "duplicateStart" -> {
                    try(var duplicate=AutomaticReplicatedSearchEngines.builder(builder(),config).build()){
                        result.put("state",duplicate.start().get(20,TimeUnit.SECONDS).state().name());
                    }
                }
                case "reopen" -> {
                    if(engine.leadershipStatus().state()!=AutomaticReplicationState.CLOSED)throw new IllegalStateException("close first");
                    open();
                }
                default -> throw new IllegalArgumentException(kind);
            }
            result.put("outcome","SUCCESS");observer.accept("CLIENT_SUCCESS",result);
        } catch(Exception error){failure(result,error);observer.accept("CLIENT_FAILURE",result);}
        print(result);
    }
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);var config=configs(root).get(Integer.parseInt(args[1])-1);
        if(args.length>2&&args[2].equals("probe")) {
            if(args.length>3)config=new AutomaticReplicationGroupConfig<>(config.groupId(),config.configurationId(),config.localNodeId(),config.members(),
                    root.resolve(args[3]),config.materialization(),config.bounds(),config.leadershipPolicy());
            var result=new LinkedHashMap<String,Object>();result.put("pid",ProcessHandle.current().pid());
            try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),config).build()) {
                try{engine.start().get(20,TimeUnit.SECONDS);result.put("outcome","SUCCESS");}
                catch(Exception error){failure(result,error);}
                result.put("state",engine.leadershipStatus().state().name());
            }
            print(result);return;
        }
        var client=new PublicLifecycleConsumer(config);client.open();
        print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
        var callers=new ThreadPoolExecutor(4,4,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(16));
        try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
            String line;while((line=input.readLine())!=null) {
                var command=(Map<String,Object>)AdmissionJson.parse(line);
                if(command.get("kind").equals("close"))break;
                callers.execute(()->client.execute(command));
            }
        } finally {
            callers.shutdown();
            if(!callers.awaitTermination(25,TimeUnit.SECONDS))throw new IllegalStateException("lifecycle callers did not drain");
            client.engine.close();observer.accept("CLOSED",Map.of());
        }
    }
}
