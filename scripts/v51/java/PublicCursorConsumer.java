package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.replication.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.*;
import java.net.ServerSocket;
import java.util.*;
import java.util.concurrent.*;

/** Same cursor program on published V4.4 and three real public TCP voters in one JVM. */
public final class PublicCursorConsumer {
    private static final TextField<Doc> TEXT=TextField.of(VALUE,SimpleAnalyzer.INSTANCE);
    private static SearchEngineBuilder<Integer,Doc> cursorBuilder(){
        return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.text(TEXT)).config(new SnapshotEngineConfig(64,16,java.time.Duration.ofMillis(1)));
    }
    private static List<Integer> ids(SearchPageResult<Doc> page){return page.hits().stream().map(h->h.document().id()).toList();}
    private static String rejected(Runnable action){try{action.run();return "ACCEPTED";}catch(RuntimeException e){return e.getClass().getName();}}
    private static List<AutomaticReplicatedSearchEngine<Integer,Doc>> open(Path root) throws Exception {
        var result=new ArrayList<AutomaticReplicatedSearchEngine<Integer,Doc>>();
        try {
            for(var config:configs(root))result.add(AutomaticReplicatedSearchEngines.builder(cursorBuilder(),config).build());
            CompletableFuture.allOf(result.stream().map(AutomaticReplicatedSearchEngine::start).toArray(CompletableFuture[]::new)).get(20,TimeUnit.SECONDS);
            return result;
        } catch(Exception error){for(var engine:result)engine.close();throw error;}
    }
    private static AutomaticReplicatedSearchEngine<Integer,Doc> leader(List<AutomaticReplicatedSearchEngine<Integer,Doc>> group) throws Exception {
        long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(40);
        while(System.nanoTime()<until) {
            for(var engine:group)if(engine.leadershipStatus().state()==AutomaticReplicationState.LEADER_READY)return engine;
            Thread.sleep(20);
        }
        throw new IllegalStateException("cursor group election timeout");
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);boolean candidate=args[1].equals("candidate");
        if(args[1].equals("setup")) {
            var sockets=new ArrayList<ServerSocket>();
            try{for(int i=0;i<3;i++)sockets.add(new ServerSocket(0));Files.write(root.resolve("ports.txt"),sockets.stream().map(s->Integer.toString(s.getLocalPort())).toList());}
            finally{for(var socket:sockets)socket.close();}
            var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,configs(root),root.resolve("operation"),1L<<30,1L<<30);
            AutomaticReplicationStorageOperations.applyBootstrap(cursorBuilder(),request,AutomaticReplicationStorageOperations.planBootstrap(cursorBuilder(),request));return;
        }
        System.err.println("coreSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        var group=new ArrayList<AutomaticReplicatedSearchEngine<Integer,Doc>>();
        DurableSearchEngine<Integer,Doc> engine=null;
        try {
            if(candidate){group.addAll(open(root));engine=leader(group);}else engine=cursorBuilder().buildDurable(storage(root.resolve("cursor-control")));
            var report=new LinkedHashMap<String,Object>();
            engine.addAll(List.of(new Doc(3,"shared third"),new Doc(1,"shared first"),new Doc(2,"shared second"))).get(20,TimeUnit.SECONDS);
            var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(1).build();
            var first=engine.search(SearchPageRequest.builder(request).build());report.put("first",ids(first));
            var continuation=SearchPageRequest.builder(request).after(first.nextCursor().orElseThrow()).build();
            long before=engine.currentSequence();engine.get(1);engine.metrics();
            report.put("continuedAfterReads",ids(engine.search(continuation)));report.put("sequenceAfterReads",engine.currentSequence());
            if(before!=engine.currentSequence())throw new AssertionError("reads changed application sequence");
            engine.add(new Doc(4,"shared later")).get(20,TimeUnit.SECONDS);
            var active=engine;report.put("mutationFailure",rejected(()->active.search(continuation)));
            var rebuildRequest=SearchPageRequest.builder(request).after(engine.search(SearchPageRequest.builder(request).build()).nextCursor().orElseThrow()).build();
            if(candidate) {
                for(var member:group)member.close();group.clear();group.addAll(open(root));engine=leader(group);
            }else{engine.close();engine=cursorBuilder().buildDurable(storage(root.resolve("cursor-control")));}
            var rebuilt=engine;report.put("rebuildFailure",rejected(()->rebuilt.search(rebuildRequest)));
            report.put("freshAfterRebuild",ids(engine.search(SearchPageRequest.builder(request).build())));
            report.put("documents",engine.search(Query.matchAll()).stream().map(d->Map.of("id",d.id(),"value",d.value())).toList());
            report.put("sequenceAfterRebuild",engine.currentSequence());
            System.out.println(AdmissionJson.canonical(report));
        } finally {if(candidate){for(var member:group)member.close();}else if(engine!=null)engine.close();}
    }
}
