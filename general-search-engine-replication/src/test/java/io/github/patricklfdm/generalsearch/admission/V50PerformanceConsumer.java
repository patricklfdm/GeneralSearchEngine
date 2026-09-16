package io.github.patricklfdm.generalsearch.admission;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.replication.*;

/** Every application and lifecycle operation uses the published public interfaces. */
public final class V50PerformanceConsumer {
    private V50PerformanceConsumer() { }
    @SuppressWarnings("unchecked")
    public static List<ReplicationGroupConfig<Integer, AdmissionSemanticModel.Doc>> configs(Path root, String ports, PerformanceWorkload.Plan plan) {
        String[] numbers = ports.split(","); var b = (Map<String, Object>) plan.document().get("replicationBounds");
        var members = java.util.stream.IntStream.range(0, 3).mapToObj(i -> new ReplicationMember(new ReplicationNodeId("node-" + (i + 1)),
                new ReplicationEndpoint("127.0.0.1", Integer.parseInt(numbers[i])))).toList();
        var bounds = new ReplicationBounds(n(b, "maxFrameBytes"), n(b, "maxEntriesPerAppend"), n(b, "maxInFlightPerPeer"),
                n(b, "maxPendingClientOperations"), n(b, "maxRetryAttempts"), n(b, "requestTimeoutMillis"), n(b, "retryBackoffMillis"),
                n(b, "snapshotChunkBytes"), n(b, "maxRetainedLogBytes"), n(b, "maxSnapshotStagingBytes"));
        return members.stream().map(m -> new ReplicationGroupConfig<>(new ReplicationGroupId(UUID.fromString("50000000-0000-0000-0000-000000000006")), "phase6-local-v1",
                m.nodeId(), members.getFirst().nodeId(), members, root.resolve(m.nodeId().value()),
                PerformanceWorkload.storage(root.resolve("materialization-" + m.nodeId().value())), bounds)).toList();
    }
    private static int n(Map<String, Object> m, String key) { return Math.toIntExact(((Number) m.get(key)).longValue()); }
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]); int ordinal = Integer.parseInt(args[1]); var plan = PerformanceWorkload.plan(Path.of(args[3]));
        var configs = configs(root, args[2], plan); var builder = PerformanceWorkload.builder();
        if (ordinal == 0) {
            var request = new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                    root.resolve("source"), configs, root.resolve("operation"), 64L << 20, 256L << 20);
            var result = ReplicationStorageOperations.applyBootstrap(builder, request, ReplicationStorageOperations.planBootstrap(builder, request));
            System.out.println(AdmissionJson.canonical(Map.of("manifest", result.manifestDigest(), "baseSequence", result.applicationSequence(),
                    "history", result.applicationHistory().toString()))); return;
        }
        try (var engine = ReplicatedSearchEngines.builder(builder, configs.get(ordinal - 1)).build();
             var input = new BufferedReader(new InputStreamReader(System.in))) {
            engine.start().join();
            String source = Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
            System.out.println(AdmissionJson.canonical(Map.of("ready", true, "node", "node-" + ordinal,
                    "identity", PerformanceTelemetry.identity(source, plan.digest()))));
            String line;
            while ((line = input.readLine()) != null) {
                var request = (Map<String, Object>) AdmissionJson.parse(line); String command = (String) request.get("command");
                var result = new TreeMap<String, Object>(); result.put("command", command); boolean close = false;
                long start = System.nanoTime();
                try {
                    switch (command) {
                        case "activate" -> engine.activateConfiguredLeader().join();
                        case "configure" -> PerformanceTelemetry.configure((String) request.get("window"), (Boolean) request.get("enabled"));
                        case "measure" -> result.put("measurement", PerformanceWorkload.execute(engine, plan, (String) request.get("window"), n(request, "firstCycle"), n(request, "cycles")));
                        case "telemetry" -> result.put("telemetry", PerformanceTelemetry.snapshot());
                        case "status" -> { }
                        case "semantic" -> result.put("semantic", PerformanceWorkload.semantic(engine));
                        case "catchup" -> result.put("verifiedIndex", engine.catchUp(new ReplicationNodeId((String) request.get("peer"))).join());
                        case "checkpoint" -> engine.checkpoint().join();
                        case "backup" -> result.put("sequence", engine.backup(new DurableBackupRequest(root.resolve("export"), 16L << 20)).join().sequence());
                        case "no-quorum" -> engine.add(PerformanceWorkload.document(999999, 1, plan.number("seed"))).join();
                        case "close" -> { engine.close(); close = true; }
                        default -> throw new IllegalArgumentException(command);
                    }
                    result.put("accepted", true);
                } catch (RuntimeException error) {
                    Throwable cause = error;
                    while (cause instanceof java.util.concurrent.CompletionException && cause.getCause() != null) cause = cause.getCause();
                    result.put("accepted", false); result.put("reason", cause instanceof ReplicationException r ? r.reason().name() : cause.getClass().getSimpleName());
                }
                long end = System.nanoTime(); var s = engine.replicationStatus(); var d = engine.durabilityMetrics();
                result.put("startNanos", start); result.put("endNanos", end); result.put("elapsedNanos", end - start);
                result.put("status", Map.of("state", s.state().name(), "sequence", s.applicationSequence(), "appliedIndex", s.appliedIndex(),
                        "commitIndex", s.commitIndex(), "lastLogIndex", s.lastLogIndex(), "pendingClients", s.pendingClientOperations(),
                        "writeQuorum", s.writeQuorumAvailable(), "retainedBytes", d.retainedBytes(), "walBytes", d.walBytes()));
                result.put("resources", PerformanceTelemetry.resources());
                var diagnostics = engine.replicationDiagnostics();
                result.put("peers", diagnostics.peers().stream().map(p -> Map.of("node", p.nodeId().value(),
                        "reachable", p.reachable(), "durableIndex", p.durableIndex(), "matchIndex", p.matchIndex(),
                        "appliedIndex", p.appliedIndex(), "observed", p.observedAt().isPresent())).toList());
                System.out.println(AdmissionJson.canonical(result)); System.out.flush();
                if (close) return;
            }
        }
    }
}
