package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.replication.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Public JAR-only client. Four callers overlap; the observer never supplies authority. */
public final class PublicQualificationConsumer {
    private static synchronized void print(Object row){System.out.println(AdmissionJson.canonical(row));System.out.flush();}
    @SuppressWarnings("unchecked")
    private static void execute(AutomaticReplicatedSearchEngine<Integer,Doc> engine,Map<String,Object> command) {
        String kind=(String)command.get("kind");
        var response=new LinkedHashMap<String,Object>(command);
        observer.accept("CLIENT_INVOKE",command);
        try {
            if(kind.equals("status")) {
                var status=engine.leadershipStatus();response.put("state",status.state().name());
                response.put("epoch",status.promisedEpoch());response.put("appliedIndex",status.appliedIndex());
                response.put("provenIndex",status.provenIndex());
            }
            else if(kind.equals("addAll")) {
                var docs=((List<Map<String,Object>>)command.get("documents")).stream()
                        .map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList();
                engine.addAll(docs).get(20,TimeUnit.SECONDS);
            } else if(kind.equals("read")) {
                var entered=new AtomicBoolean();
                var docs=engine.search(doc->{
                    if(entered.compareAndSet(false,true))observer.accept("READ_CALLBACK",Map.of("opId",command.get("opId")));
                    return true;
                }).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList();
                response.put("documents",docs);
            } else throw new IllegalArgumentException(kind);
            response.put("outcome","SUCCESS");observer.accept("CLIENT_SUCCESS",response);
        } catch(Exception failure) {
            Throwable cause=failure;
            while((cause instanceof ExecutionException||cause instanceof CompletionException)&&cause.getCause()!=null)cause=cause.getCause();
            response.put("outcome",cause instanceof AutomaticReplicationException automatic?automatic.outcome().name():"VALIDATION_FAILURE");
            if(cause instanceof AutomaticReplicationException automatic)response.put("reasonCode",automatic.reason().name());
            response.put("reason",cause.toString());observer.accept("CLIENT_FAILURE",response);
        }
        if(!kind.equals("status"))observer.accept("BEFORE_CLIENT_RESPONSE",response);
        print(response);
    }
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);int ordinal=Integer.parseInt(args[1]);
        try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),configs(root).get(ordinal-1)).build()) {
            var started=engine.start().get(20,TimeUnit.SECONDS);
            if(started.state()!=AutomaticReplicationState.FOLLOWER)throw new AssertionError("public local startup");
            observer.accept("STARTED",Map.of("node",started.localNodeId().value()));
            print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
            var calls=new ThreadPoolExecutor(4,4,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(16));
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;
                while((line=input.readLine())!=null) {
                    var command=(Map<String,Object>)AdmissionJson.parse(line);
                    if(command.get("kind").equals("close"))break;
                    calls.execute(()->execute(engine,command));
                }
            } finally {
                calls.shutdown();if(!calls.awaitTermination(25,TimeUnit.SECONDS))throw new IllegalStateException("public callers did not drain");
            }
            engine.close();observer.accept("CLOSED",Map.of());
        }
    }
}
