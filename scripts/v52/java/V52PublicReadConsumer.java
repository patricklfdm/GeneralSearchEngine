package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.V52ReadQueries.*;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.io.*;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** External public consumer. Its optional observer records calls, never supplies read results. */
public final class V52PublicReadConsumer {
    private static List<AutomaticReplicationGroupConfig<Integer,Doc>> configs(Path root) throws Exception {
        return PublicRuntimeConsumer.configs(root).stream().map(c->new AutomaticReplicationGroupConfig<Integer,Doc>(
                c.groupId(),"v52-public-read",c.localNodeId(),c.members(),c.replicaDirectory(),
                storage(root.resolve("app-"+c.localNodeId().value())),c.bounds(),c.leadershipPolicy())).toList();
    }
    private static View view(ReplicaReadView<Integer,Doc> view) {
        return new View() {
            public Doc get(Integer id){return view.get(id);}
            public List<Doc> search(Query<Doc> query){return view.search(query);}
            public List<SearchHit<Doc>> searchTopK(RankedSearchRequest<Doc> request){return view.searchTopK(request);}
            public SearchResult<Doc> search(SearchRequest<Doc> request){return view.search(request);}
            public HighlightedSearchResult<Doc> search(HighlightedSearchRequest<Doc> request){return view.search(request);}
            public Optional<SearchExplanation<Doc>> explain(SearchRequest<Doc> request,Integer id){return view.explain(request,id);}
            public long currentSequence(){return view.currentSequence();}
        };
    }
    private static synchronized void print(Object value){System.out.println(AdmissionJson.canonical(value));System.out.flush();}
    private static void event(String event,Map<String,Object> row){PublicRuntimeConsumer.observer.accept(event,row);}
    private static void respond(Map<String,Object> command,Map<String,Object> value,Throwable failure) {
        var row=new LinkedHashMap<String,Object>();row.put("opId",command.get("opId"));row.put("kind",command.get("kind"));
        if(failure==null){row.putAll(value);row.put("outcome","SUCCESS");}
        else {
            while((failure instanceof CompletionException||failure instanceof ExecutionException)&&failure.getCause()!=null)failure=failure.getCause();
            row.put("reason",failure.toString());
            if(failure instanceof AutomaticReplicationException auto){row.put("reasonCode",auto.reason().name());row.put("outcome",auto.outcome().name());}
            else if(failure instanceof ReplicaReadException read){row.put("reasonCode",read.reason().name());row.put("outcome","REJECTED");}
            else {row.put("reasonCode",failure.getClass().getSimpleName());row.put("outcome","VALIDATION_FAILURE");}
        }
        event(failure==null?"CLIENT_SUCCESS":"CLIENT_FAILURE",row);print(row);
    }
    @SuppressWarnings("unchecked") public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath();
        System.err.println("coreSource="+io.github.patricklfdm.generalsearch.engine.SearchEngine.class.getProtectionDomain().getCodeSource().getLocation());
        System.err.println("replicationSource="+AutomaticReplicatedSearchEngine.class.getProtectionDomain().getCodeSource().getLocation());
        if(args[1].equals("setup")) {
            var sockets=new ArrayList<ServerSocket>();
            try {for(int i=0;i<3;i++)sockets.add(new ServerSocket(0));Files.write(root.resolve("ports.txt"),sockets.stream().map(s->Integer.toString(s.getLocalPort())).toList());}
            finally {for(var socket:sockets)socket.close();}
            var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                    root.resolve("control/seed"),configs(root),root.resolve("operation"),1L<<30,1L<<30);
            AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,AutomaticReplicationStorageOperations.planBootstrap(builder(),request));
            print(Map.of("status","SETUP"));return;
        }
        int ordinal=Integer.parseInt(args[1]);var pending=new ArrayList<CompletableFuture<?>>();
        try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),configs(root).get(ordinal-1)).build()) {
            engine.start().get(20,TimeUnit.SECONDS);event("STARTED",Map.of());print(Map.of("status","STARTED","pid",ProcessHandle.current().pid()));
            try(var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
                String line;int calls=0;
                while((line=input.readLine())!=null) {
                    if(line.length()>1<<20||++calls>1000)throw new IOException("public read fixture command bound");
                    var command=(Map<String,Object>)AdmissionJson.parse(line);String kind=(String)command.get("kind");
                    if(kind.equals("close")){engine.close();CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).get(20,TimeUnit.SECONDS);event("CLOSED",Map.of());break;}
                    if(kind.equals("status")) {
                        var s=engine.leadershipStatus();var row=new LinkedHashMap<String,Object>();row.put("opId",command.get("opId"));row.put("kind",kind);row.put("outcome","SUCCESS");
                        row.put("state",s.state().name());row.put("epoch",s.promisedEpoch());row.put("provenIndex",s.provenIndex());
                        row.put("publishedIndex",s.appliedIndex());row.put("sequence",s.applicationSequence());row.put("pending",s.pendingOperations());print(row);continue;
                    }
                    event("CLIENT_INVOKE",command);
                    try {
                        if(kind.equals("addAll")) {
                            var docs=((List<Map<String,Object>>)command.get("documents")).stream().map(d->new Doc(((Number)d.get("id")).intValue(),(String)d.get("value"))).toList();
                            pending.add(engine.addAll(docs).handle((v,e)->{respond(command,Map.of("documents",docs.stream().map(V52ReadQueries::doc).toList()),e);return null;}));
                        } else if(kind.equals("read")) {
                            var policy=ReplicaReadPolicy.valueOf((String)command.get("policy"));String minimum=(String)command.getOrDefault("minimum","");
                            var options=new ReplicaReadOptions(policy,minimum.isEmpty()?Optional.empty():Optional.of(ReplicaReadToken.decode(Base64.getDecoder().decode(minimum))),
                                    ((Number)command.getOrDefault("waitTimeoutMillis",0L)).intValue());
                            pending.add(engine.read(options,v->{event("REPLICA_READ_CALLBACK",Map.of("opId",command.get("opId")));return report(view(v));})
                                    .handle((result,error)->{
                                        var row=new LinkedHashMap<String,Object>();
                                        if(result!=null){row.put("report",result.value());row.put("documents",result.value().get("documents"));row.put("policy",result.policy().name());
                                            row.put("token",Base64.getEncoder().encodeToString(result.progress().encode()));row.put("sequence",result.applicationSequence());}
                                        respond(command,row,error);return null;
                                    }));
                        } else throw new IllegalArgumentException("unknown public fixture command");
                    }catch(Throwable error){respond(command,Map.of(),error);}
                }
            }
        }
    }
}
