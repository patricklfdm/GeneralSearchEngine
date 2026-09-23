package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import java.util.function.Supplier;

/** Same query program compiled separately against candidate and published V4.4 core. */
public final class PublicSemanticConsumer {
    @FunctionalInterface interface Pause { void sleep(long nanos) throws InterruptedException; }

    /** A local maintenance rejection may wait for durable generation retirement.
     * Never replay a mutation, backup, missing response or unclassified failure. */
    static void checkpointWhenAvailable(Path evidence, Supplier<CompletableFuture<Void>> checkpoint,
            LongSupplier clock, Pause pause, long budgetNanos) throws Exception {
        long started=clock.getAsLong();
        var attempts=new ArrayList<Map<String,Object>>();var receipt=new LinkedHashMap<String,Object>();
        receipt.put("status","FAIL");receipt.put("timeoutNanos",budgetNanos);receipt.put("attempts",attempts);
        try {
            while(true) {
                long elapsed=clock.getAsLong()-started,remaining=budgetNanos-elapsed;
                if(remaining<=0)throw new TimeoutException("rich checkpoint capacity timeout");
                var attempt=new LinkedHashMap<String,Object>();attempt.put("startNanos",elapsed);attempt.put("status","PENDING");attempts.add(attempt);
                try {
                    checkpoint.get().get(remaining,TimeUnit.NANOSECONDS);
                    attempt.put("endNanos",clock.getAsLong()-started);attempt.put("status","PASS");
                    receipt.put("status","PASS");return;
                } catch(ExecutionException error) {
                    attempt.put("endNanos",clock.getAsLong()-started);attempt.put("status","FAIL");attempt.put("failure",error.toString());
                    if(!(error.getCause() instanceof AutomaticReplicationException failure))throw error;
                    attempt.put("reasonCode",failure.reason().name());attempt.put("outcome",failure.outcome().name());
                    if(failure.reason()!=AutomaticReplicationException.Reason.CAPACITY_EXCEEDED
                            ||failure.outcome()!=AutomaticReplicationException.Outcome.NOT_APPLICABLE)throw error;
                }
                remaining=budgetNanos-(clock.getAsLong()-started);
                if(remaining<=0)throw new TimeoutException("rich checkpoint capacity timeout");
                pause.sleep(Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(250)));
            }
        } catch(Exception error) {
            if(error instanceof InterruptedException)Thread.currentThread().interrupt();
            receipt.put("failure",error.toString());throw error;
        } finally {Files.writeString(evidence,AdmissionJson.canonical(receipt)+"\n");}
    }

    private static Object exercise(SearchEngine<Integer,Doc> engine) {
        var stages=new LinkedHashMap<String,Object>();
        if(engine.schema().requireField("id")!=engine.field("id")||engine.field("id",Integer.class)!=ID
                ||engine.field("category",String.class)!=CATEGORY||engine.textField("body")!=TEXT)
            throw new AssertionError("canonical public metadata");
        stages.put("metadata",Map.of("id",engine.field("id").name(),"text",engine.textField("body").field().name()));
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
            if(leader.lastReopenReport().isPresent())throw new AssertionError("automatic authority does not expose a core reopen report");
            if(leader.durabilityMetrics().status()!=DurabilityStatus.OPEN)throw new AssertionError("public durability readiness");
            Object stages=exercise(leader);long sequence=leader.currentSequence();
            checkpointWhenAvailable(root.resolve("checkpoint-maintenance.json"),leader::checkpoint,
                    System::nanoTime,nanos->TimeUnit.NANOSECONDS.sleep(nanos),TimeUnit.SECONDS.toNanos(30));
            leader.backup(new DurableBackupRequest(root.resolve("backup"),1<<20)).get(20,TimeUnit.SECONDS);
            System.out.println(AdmissionJson.canonical(Map.of("stages",stages,"sequence",sequence)));
        } finally {for(var engine:engines)engine.close();}
    }
}
