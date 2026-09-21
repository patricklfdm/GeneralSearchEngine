package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Same query program compiled separately against candidate and published V4.4 core. */
public final class PublicSemanticConsumer {
    private static Object exercise(SearchEngine<Integer,Doc> engine) {
        var stages=new LinkedHashMap<String,Object>();
        populate(engine);stages.put("populated",report(engine));
        engine.updateAll(List.of(new Doc(3,"Java Revised","guide",31,"java search revised"),
                new Doc(7,"Prefix Query","reference",71,"query search search"))).join();
        engine.removeAll(List.of(1,5)).join();
        engine.addAll(List.of(new Doc(5,"Java Again","guide",55,"java query search"),
                new Doc(8,"New Java","guide",80,"java search memory"))).join();
        engine.dropIndex("category").join();stages.put("dropped",report(engine));
        engine.createIndex(IndexDefinition.equality(CATEGORY)).join();stages.put("recreated",report(engine));
        stages.put("get",engine.get(5).toString());return stages;
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String mode=args[1];
        System.err.println("coreSource="+Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        System.err.println("replicationSource="+Path.of(AutomaticReplicatedSearchEngines.class.getProtectionDomain().getCodeSource().getLocation().toURI()));
        if(mode.equals("control")) {
            Object stages;long sequence;
            try(var engine=builder().buildDurable(storage(root.resolve("control-store"),2))) {
                stages=exercise(engine);sequence=engine.currentSequence();
            }
            var restored=storage(root.resolve("restored"),2);builder().restoreDurableBackup(root.resolve("backup"),restored);
            try(var engine=builder().buildDurable(restored)) {
                System.out.println(AdmissionJson.canonical(Map.of("stages",stages,"sequence",sequence,
                        "restored",report(engine),"restoredSequence",engine.currentSequence())));
            }
            return;
        }
        // Ports are allocated by the external controller using the ordinary public fixture setup helper.
        var configs=PublicRuntimeConsumer.configs(root).stream().map(c->new AutomaticReplicationGroupConfig<>(
                c.groupId(),"public-rich-semantics",c.localNodeId(),c.members(),c.replicaDirectory(),
                storage(root.resolve("rich-app-"+c.localNodeId().value()),2),c.bounds(),c.leadershipPolicy())).toList();
        var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,configs,root.resolve("operation"),1L<<30,1L<<30);
        AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,AutomaticReplicationStorageOperations.planBootstrap(builder(),request));
        var engines=new ArrayList<AutomaticReplicatedSearchEngine<Integer,Doc>>();
        try {
            for(var config:configs)engines.add(AutomaticReplicatedSearchEngines.builder(builder(),config).build());
            CompletableFuture.allOf(engines.stream().map(AutomaticReplicatedSearchEngine::start).toArray(CompletableFuture[]::new)).get(20,TimeUnit.SECONDS);
            AutomaticReplicatedSearchEngine<Integer,Doc> leader=null;long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(40);
            while(leader==null&&System.nanoTime()<until) {
                leader=engines.stream().filter(e->e.leadershipStatus().state()==AutomaticReplicationState.LEADER_READY).findFirst().orElse(null);
                if(leader==null)Thread.sleep(20);
            }
            if(leader==null)throw new IllegalStateException("rich public election timeout");
            Object stages=exercise(leader);long sequence=leader.currentSequence();
            leader.checkpoint().get(20,TimeUnit.SECONDS);leader.backup(new DurableBackupRequest(root.resolve("backup"),1<<20)).get(20,TimeUnit.SECONDS);
            System.out.println(AdmissionJson.canonical(Map.of("stages",stages,"sequence",sequence)));
        } finally {for(var engine:engines)engine.close();}
    }
}
