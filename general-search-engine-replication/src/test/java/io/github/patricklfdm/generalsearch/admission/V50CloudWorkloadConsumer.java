package io.github.patricklfdm.generalsearch.admission;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.replication.*;
import static io.github.patricklfdm.generalsearch.admission.CloudWorkload.*;

/** Compiled against production JARs. All authority and application calls are public. */
public final class V50CloudWorkloadConsumer {
    private V50CloudWorkloadConsumer() { }
    public static List<ReplicationGroupConfig<Integer,AdmissionSemanticModel.Doc>> configs(Path root, String endpoints, Plan plan) {
        var addresses=endpoints.split(","); var b=plan.section("replicationBounds");
        var members=java.util.stream.IntStream.range(0,3).mapToObj(i -> new ReplicationMember(new ReplicationNodeId("node-"+(i+1)),
                new ReplicationEndpoint(addresses[i].split(":")[0],Integer.parseInt(addresses[i].split(":")[1])))).toList();
        var bounds=new ReplicationBounds(number(b,"maxFrameBytes"),number(b,"maxEntriesPerAppend"),number(b,"maxInFlightPerPeer"),
                number(b,"maxPendingClientOperations"),number(b,"maxRetryAttempts"),number(b,"requestTimeoutMillis"),number(b,"retryBackoffMillis"),
                number(b,"snapshotChunkBytes"),number(b,"maxRetainedLogBytes"),number(b,"maxSnapshotStagingBytes"));
        return members.stream().map(m -> new ReplicationGroupConfig<>(new ReplicationGroupId(UUID.fromString("50000000-0000-0000-0000-000000000016")),
                "phase6-cloud-workload-v1",m.nodeId(),members.getFirst().nodeId(),members,root.resolve(m.nodeId().value()),
                storage(root.resolve("materialization-"+m.nodeId().value()),plan),bounds)).toList();
    }
    public static Map<String,Object> status(ReplicatedSearchEngine<?,?> engine) {
        var s=engine.replicationStatus(); var d=engine.replicationDiagnostics(); var m=engine.durabilityMetrics();
        var result=new TreeMap<String,Object>();
        result.put("state",s.state().name()); result.put("sequence",s.applicationSequence()); result.put("commitIndex",s.commitIndex());
        result.put("appliedIndex",s.appliedIndex()); result.put("lastLogIndex",s.lastLogIndex()); result.put("pendingClients",s.pendingClientOperations());
        result.put("writeQuorum",s.writeQuorumAvailable()); result.put("epoch",s.activeEpoch()); result.put("incarnation",d.incarnation().toString());
        result.put("floor",d.recoveryFloor()); result.put("snapshotInstalling",d.snapshotInstalling()); result.put("retainedLogBytes",s.retainedLogBytes());
        result.put("checkpointSequence",m.checkpointSequence()); result.put("retainedBytes",m.retainedBytes());
        result.put("peers",d.peers().stream().map(p -> Map.of("node",p.nodeId().value(),"reachable",p.reachable(),"durableIndex",p.durableIndex(),"appliedIndex",p.appliedIndex())).toList());
        result.put("observer",CloudWorkloadTelemetry.observer.apply(engine)); return result;
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]); int ordinal=Integer.parseInt(args[1]); var plan=plan(Path.of(args[3]));
        var configs=configs(root,args[2],plan); var builder=PerformanceWorkload.builder();
        if (ordinal==0) {
            if (args[4].equals("bootstrap")) {
                var request=new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,root.resolve("source"),configs,
                        root.resolve("operation"),64L<<20,256L<<20);
                var r=ReplicationStorageOperations.applyBootstrap(builder,request,ReplicationStorageOperations.planBootstrap(builder,request));
                System.out.println(AdmissionJson.canonical(Map.of("manifest",r.manifestDigest(),"baseSequence",r.applicationSequence())));
            } else if(args[4].equals("replace")) {
                int target=Integer.parseInt(args[5]), source=Integer.parseInt(args[6]); var config=configs.get(target-1);
                var p=ReplicationStorageOperations.planReplacement(config,configs.get(source-1).replicaDirectory(),root.resolve("replacement-"+target));
                ReplicationStorageOperations.applyReplacement(config,p);
                System.out.println(AdmissionJson.canonical(Map.of("replacement",target,"source",source)));
            } else throw new IllegalArgumentException("offline command");
            return;
        }
        Path output=Path.of(args[4]); CloudWorkloadTelemetry.initialize(output);
        try(var engine=ReplicatedSearchEngines.builder(builder,configs.get(ordinal-1)).build(); var input=new BufferedReader(new InputStreamReader(System.in))) {
            engine.start().join(); CloudWorkloadTelemetry.startSampling(() -> status(engine));
            String source=Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
            System.out.println(AdmissionJson.canonical(Map.of("ready",true,"node","node-"+ordinal,"identity",PerformanceTelemetry.identity(source,plan.digest()))));
            String line;
            while((line=input.readLine())!=null) {
                AdmissionJson.require(line.length()<=65536,"command bound"); var q=map(AdmissionJson.parse(line)); String command=(String)q.get("command");
                var result=new TreeMap<String,Object>(); result.put("command",command); boolean close=false; long start=System.nanoTime();
                try {
                    switch(command) {
                        case "activate" -> engine.activateConfiguredLeader().join();
                        case "reconstruct" -> engine.reconstructConfiguredLeader().join();
                        case "configure" -> { CloudWorkloadTelemetry.window=(String)q.get("window"); CloudWorkloadTelemetry.instrumented=(Boolean)q.get("enabled"); }
                        case "fault" -> CloudWorkloadTelemetry.fault=(String)q.get("mode");
                        case "arm" -> CloudWorkloadTelemetry.cut=(String)q.get("barrier");
                        case "measure" -> result.put("measurement",execute(engine,plan,(String)q.get("window"),number(q,"firstCycle"),number(q,"calls"),
                                ((Number)q.get("intervalNanos")).longValue(),(Boolean)q.get("sustained"),() -> status(engine)));
                        case "state" -> result.put("semantic",state(engine,(String)q.get("label")));
                        case "status" -> { }
                        case "update" -> engine.update(PerformanceWorkload.document(number(q,"id"),number(q,"revision"),17)).join();
                        case "catchup" -> result.put("verifiedIndex",engine.catchUp(new ReplicationNodeId((String)q.get("peer"))).join());
                        case "checkpoint" -> engine.checkpoint().join();
                        case "backup" -> result.put("backupSequence",engine.backup(new DurableBackupRequest(root.resolve((String)q.get("target")),128L<<20)).join().sequence());
                        case "backup-cancel" -> {
                            var f=engine.backup(new DurableBackupRequest(root.resolve((String)q.get("target")),128L<<20));
                            result.put("cancelled",f.cancel(true)); CloudWorkloadTelemetry.stopSampling(); engine.close(); close=true;
                        }
                        case "close" -> { CloudWorkloadTelemetry.stopSampling(); engine.close(); close=true; }
                        default -> throw new IllegalArgumentException(command);
                    }
                    CloudWorkloadTelemetry.check(); result.put("accepted",true);
                } catch(RuntimeException error) {
                    Throwable cause=error; while(cause instanceof CompletionException && cause.getCause()!=null) cause=cause.getCause();
                    result.put("accepted",false); result.put("reason",cause instanceof ReplicationException r ? r.reason().name() : cause.toString());
                }
                result.put("startNanos",start); result.put("endNanos",System.nanoTime()); result.put("status",status(engine));
                System.out.println(AdmissionJson.canonical(result)); System.out.flush();
                if(close) return;
            }
        } finally { CloudWorkloadTelemetry.stopSampling(); CloudWorkloadTelemetry.close(); }
    }
}
