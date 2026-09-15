package io.github.patricklfdm.generalsearch.admission;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;

/** The process gate compiles this class against production JARs, outside the implementation package. */
public final class PublicRuntimeConsumer {
    private PublicRuntimeConsumer() { }
    public static List<ReplicationGroupConfig<Integer, AdmissionSemanticModel.Doc>> configs(Path root, String ports, int minor) {
        var numbers = ports.split(",");
        var members = java.util.stream.IntStream.range(0, 3).mapToObj(i -> new ReplicationMember(new ReplicationNodeId("node-" + (i + 1)),
                new ReplicationEndpoint("127.0.0.1", Integer.parseInt(numbers[i])))).toList();
        var bounds = new ReplicationBounds(1 << 20, 10, 4, 16, 3, 1500, 10, 4096, 16 << 20, 16 << 20);
        return members.stream().map(member -> new ReplicationGroupConfig<>(new ReplicationGroupId(OfflineApplication.GROUP), "runtime-v1",
                member.nodeId(), members.getFirst().nodeId(), members, root.resolve(member.nodeId().value()),
                AdmissionSemanticModel.storage(root.resolve("materialization-" + member.nodeId().value()), minor), bounds)).toList();
    }
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]); int ordinal = Integer.parseInt(args[1]), minor = Integer.parseInt(args[3]);
        var configs = configs(root, args[2], minor); var application = AdmissionSemanticModel.builder();
        if (ordinal == 0) {
            String command = args[4];
            if (command.equals("bootstrap")) {
                var source = root.resolve("source");
                var request = new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP, source, configs,
                        root.resolve("operation"), 1 << 28, 1 << 28);
                var result = ReplicationStorageOperations.applyBootstrap(application, request, ReplicationStorageOperations.planBootstrap(application, request));
                System.out.println(AdmissionJson.canonical(Map.of("manifest", result.manifestDigest(), "history", result.applicationHistory().toString(), "base", result.applicationSequence())));
            } else if (command.equals("replace")) {
                int target = Integer.parseInt(args[5]); int source = Integer.parseInt(args[6]);
                var config = configs.get(target - 1);
                var plan = ReplicationStorageOperations.planReplacement(config, configs.get(source - 1).replicaDirectory(), root.resolve("replace-operation-" + target));
                ReplicationStorageOperations.applyReplacement(config, plan);
                System.out.println(AdmissionJson.canonical(Map.of("replacement", target)));
            }
            return;
        }
        try (var engine = ReplicatedSearchEngines.builder(application, configs.get(ordinal - 1)).build();
             var input = new BufferedReader(new InputStreamReader(System.in))) {
            engine.start().join();
            System.out.println(AdmissionJson.canonical(Map.of("ready", true, "pid", ProcessHandle.current().pid(), "node", "node-" + ordinal)));
            String line;
            while ((line = input.readLine()) != null) {
                var request = (Map<String, Object>) AdmissionJson.parse(line); String command = (String) request.get("command");
                var result = new java.util.TreeMap<String, Object>(); result.put("command", command);
                boolean exit = false;
                try {
                    switch (command) {
                        case "status" -> { }
                        case "activate" -> engine.activateConfiguredLeader().join();
                        case "reconstruct" -> engine.reconstructConfiguredLeader().join();
                        case "catchup" -> result.put("verifiedIndex", engine.catchUp(new ReplicationNodeId((String) request.get("peer"))).join());
                        case "report" -> result.put("semantics", AdmissionSemanticModel.report(engine));
                        case "workload" -> PublicRuntimeWorkload.apply(engine);
                        case "add" -> engine.add(new AdmissionSemanticModel.Doc(((Number) request.get("id")).intValue(), "Java Added", "guide", 24, "java search")).join();
                        case "checkpoint" -> engine.checkpoint().join();
                        case "backup" -> { var backup = engine.backup(new DurableBackupRequest(root.resolve((String) request.get("target")), 1 << 20)).join();
                            result.put("backupSequence", backup.sequence()); result.put("backupHistory", backup.sourceHistory().toString()); }
                        case "close" -> { engine.close(); exit = true; }
                        default -> throw new IllegalArgumentException("unknown public command");
                    }
                    result.put("accepted", true);
                } catch (RuntimeException error) {
                    Throwable cause = error;
                    while (cause instanceof java.util.concurrent.CompletionException && cause.getCause() != null) cause = cause.getCause();
                    result.put("accepted", false); result.put("reason", cause instanceof ReplicationException r ? r.reason().name() : cause.getClass().getSimpleName());
                }
                var status = engine.replicationStatus(); var diagnostic = engine.replicationDiagnostics(); var durability = engine.durabilityMetrics();
                result.put("state", status.state().name()); result.put("applicationSequence", status.applicationSequence());
                result.put("epoch", status.activeEpoch()); result.put("commitIndex", status.commitIndex()); result.put("appliedIndex", status.appliedIndex());
                result.put("lastLogIndex", status.lastLogIndex()); result.put("writeQuorum", status.writeQuorumAvailable());
                result.put("floor", diagnostic.recoveryFloor()); result.put("incarnation", diagnostic.incarnation().toString());
                result.put("checkpointSequence", durability.checkpointSequence()); result.put("recoverySource", durability.recoverySource().name());
                result.put("replayed", durability.replayedRecords()); result.put("storageState", durability.status().name());
                System.out.println(AdmissionJson.canonical(result)); System.out.flush();
                if (exit) return;
            }
        }
    }
}
