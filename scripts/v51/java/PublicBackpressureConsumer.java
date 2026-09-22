package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.replication.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** JAR-only client: holds caller callbacks, never runtime queues or authority. */
public final class PublicBackpressureConsumer {
    private final AutomaticReplicatedSearchEngine<Integer,Doc> engine;
    private final Path root;
    private PublicBackpressureConsumer(Path root,AutomaticReplicatedSearchEngine<Integer,Doc> engine){this.root=root;this.engine=engine;}
    private static synchronized void print(Object row){System.out.println(AdmissionJson.canonical(row));System.out.flush();}
    private static void failure(Map<String,Object> result,Throwable cause) {
        while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
        result.put("outcome",cause instanceof AutomaticReplicationException e?e.outcome().name():"VALIDATION_FAILURE");
        if(cause instanceof AutomaticReplicationException e)result.put("reasonCode",e.reason().name());
        result.put("reason",cause.toString());
    }
    private void returned(Map<String,Object> command,Throwable error,Object documents) {
        var result=new LinkedHashMap<String,Object>(command);
        if(error==null){result.put("outcome","SUCCESS");if(documents!=null)result.put("documents",documents);}
        else failure(result,error);
        observer.accept(error==null?"CLIENT_SUCCESS":"CLIENT_FAILURE",result);print(result);
    }
    private void hold(String event,String id,String release) {
        observer.accept(event,Map.of("opId",id,"thread",Thread.currentThread().getName()));long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(45);
        try {
            while(!Files.exists(root.resolve(release))&&System.nanoTime()<until)Thread.sleep(10);
            if(!Files.exists(root.resolve(release)))throw new IllegalStateException("caller callback was not released");
        } catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}
        observer.accept(event+"_RELEASED",Map.of("opId",id));
    }
    @SuppressWarnings("unchecked") private CompletableFuture<Void> write(Map<String,Object> command,Runnable after) {
        observer.accept("CLIENT_INVOKE",command);String id=(String)command.get("opId");
        var docs=((List<Map<String,Object>>)command.get("documents")).stream().map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList();
        Collection<Doc> input=docs;
        if(Boolean.TRUE.equals(command.get("poison")))input=new AbstractCollection<>() {
            private RuntimeException touched(){observer.accept("ARGUMENT_TOUCHED",Map.of("opId",id));return new IllegalStateException("queued poison argument evaluated");}
            public int size(){throw touched();}public Iterator<Doc> iterator(){throw touched();}
        };
        var future=engine.addAll(input);
        var observed=future.whenComplete((v,error)->{
            returned(command,error,null);
            if(error==null&&"hold".equals(command.get("completion")))hold("COMPLETION_HELD",id,"completion-release");
            if(error==null&&after!=null){
                observer.accept("COMPLETION_CHAIN_ENTER",Map.of("opId",id,"thread",Thread.currentThread().getName()));
                after.run();observer.accept("COMPLETION_CHAIN_EXIT",Map.of("opId",id));
            }
        });
        observer.accept("CLIENT_ENQUEUED",Map.of("opId",id));return observed;
    }
    private void reentry(String id,String method,Runnable action) {
        var result=new LinkedHashMap<String,Object>();result.put("opId",id);result.put("method",method);
        try{action.run();result.put("outcome","SUCCESS");}catch(Exception error){failure(result,error);}
        observer.accept("REENTRY",result);
    }
    private void read(Map<String,Object> command) {
        observer.accept("CLIENT_INVOKE",command);String id=(String)command.get("opId");var entered=new AtomicBoolean();
        try {
            var docs=engine.search(doc->{
                if(entered.compareAndSet(false,true)) {
                    observer.accept("READ_CALLBACK",Map.of("opId",id));
                    if(Boolean.TRUE.equals(command.get("hold")))hold("QUERY_HELD",id,"query-release");
                    if(Boolean.TRUE.equals(command.get("reenter"))) {
                        reentry(id,"add",()->engine.add(null).join());
                        reentry(id,"read",()->engine.search(d->true));
                        reentry(id,"start",()->engine.start().join());
                        reentry(id,"checkpoint",()->engine.checkpoint().join());
                        reentry(id,"backup",()->engine.backup(null).join());
                        reentry(id,"close",engine::close);
                        observer.accept("CALLBACK_DIAGNOSTICS",Map.of("opId",id,"state",engine.leadershipStatus().state().name(),
                                "schema",engine.schema()!=null,"durability",engine.durabilityMetrics().status().name()));
                    }
                }
                return true;
            }).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList();
            returned(command,null,docs);
        }catch(Exception error){returned(command,error,null);}
    }
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);var config=configs(root).get(Integer.parseInt(args[1])-1);
        try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),config).build()) {
            var started=engine.start().get(20,TimeUnit.SECONDS);
            if(started.state()!=AutomaticReplicationState.FOLLOWER)throw new AssertionError("local follower startup");
            observer.accept("STARTED",Map.of("node",started.localNodeId().value()));
            print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
            var client=new PublicBackpressureConsumer(root,engine);
            var readers=Executors.newFixedThreadPool(2);var callbacks=new ArrayList<CompletableFuture<Void>>();
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;while((line=input.readLine())!=null) {
                    var command=(Map<String,Object>)AdmissionJson.parse(line);String kind=(String)command.get("kind");
                    if(kind.equals("close"))break;
                    if(kind.equals("status")) {
                        var status=engine.leadershipStatus();var result=new LinkedHashMap<>(command);
                        result.put("state",status.state().name());result.put("provenIndex",status.provenIndex());result.put("pending",status.pendingOperations());
                        result.put("epoch",status.promisedEpoch());result.put("appliedIndex",status.appliedIndex());
                        var sample=diagnostics.apply(engine);if(!sample.isEmpty()){observer.accept("LIFECYCLE_SAMPLE",Map.of("opId",command.get("opId"),"sample",sample));result.put("sample",sample);}
                        result.put("outcome","SUCCESS");print(result);
                    }else if(kind.equals("addAll"))callbacks.add(client.write(command,null));
                    else if(kind.equals("read"))readers.execute(()->client.read(command));
                    else if(kind.equals("completionChain")) {
                        var calls=(List<Map<String,Object>>)command.get("calls");
                        callbacks.add(client.write(calls.get(0),()->{
                            try{client.write(calls.get(1),null).get(20,TimeUnit.SECONDS);client.read(calls.get(2));}
                            catch(Exception error){throw new CompletionException(error);}
                        }));
                    }else throw new IllegalArgumentException(kind);
                }
            }finally {
                readers.shutdown();if(!readers.awaitTermination(30,TimeUnit.SECONDS))throw new IllegalStateException("readers did not drain");
                for(var callback:callbacks)try{callback.get(30,TimeUnit.SECONDS);}catch(ExecutionException error){
                    // Expected operation failures have already been emitted. Callback failures are not hidden.
                    Throwable cause=error.getCause();if(!(cause instanceof AutomaticReplicationException))throw error;
                }
            }
            engine.close();observer.accept("CLOSED",Map.of());
        }
    }
}
