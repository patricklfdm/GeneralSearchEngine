package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Test-only process control. All replication, recovery, transfer and compaction use production code. */
public final class V50RecoveryWorker {
    private V50RecoveryWorker() { }
    public static void main(String[] args) throws Exception {
        if (args.length == 2 && args[0].equals("inspect")) {
            try { emit(Map.of("accepted", ReplicationStorageOperations.inspect(Path.of(args[1])).structurallyValid())); }
            catch (ReplicationException error) { emit(Map.of("accepted", false, "reason", error.reason().name())); System.exit(3); }
            return;
        }
        Path root = Path.of(args[0]); int ordinal = Integer.parseInt(args[1]);
        var manifest = manifest(Arrays.stream(args[2].split(",")).map(Integer::parseInt).toList());
        String barrier = args.length > 3 ? args[3] : ""; var id = manifest.members().get(ordinal - 1).nodeId();
        var defaults = bounds(2000, 8);
        var bounds = new ReplicationBounds(defaults.maxFrameBytes(), 2, 8, 8, 1, 2000, 20, 256, 64 * 1024 * 1024, 64 * 1024 * 1024);
        Files.createDirectories(root); Path directory = root.resolve("replica");
        if (!Files.exists(directory)) {
            if (Files.exists(root.resolve("replacement.request"))) ReplicaStore.initializeReplacement(directory, manifest, id, bounds, ReplicaStore.Faults.NONE);
            else ReplicaStore.initialize(directory, manifest, id, bounds, ReplicaStore.Faults.NONE);
        }
        var app = application(root.resolve("application-reserved"), bounds);
        var reference = new AtomicReference<ReplicaNode<Integer, Document>>();
        var events = (ReplicaNode.Events) (point, index) -> {
            var event = Map.<String, Object>of("node", id.value(), "pid", ProcessHandle.current().pid(), "index", index,
                    "barrier", point, "appliedIndex", app.appliedIndex(), "applicationSequence", app.sequence(), "monotonicNanos", System.nanoTime());
            Files.writeString(root.resolve("events.jsonl"), json(event) + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            if (point.equals(barrier) && Files.exists(root.resolve("armed"))) {
                Files.writeString(root.resolve("barrier.json"), json(event), StandardOpenOption.CREATE_NEW);
                try { new CountDownLatch(1).await(); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
            }
        };
        var faults = new ReplicaStore.Faults() {
            public void at(String point) throws java.io.IOException {
                var node = reference.get(); events.at(point, node == null ? 0 : node.status().commitIndex());
            }
        };
        try (var node = new ReplicaNode<>(directory, manifest, id, bounds, app, faults, events);
             var input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.US_ASCII))) {
            reference.set(node); emit(Map.of("ready", true, "pid", ProcessHandle.current().pid(), "node", id.value()));
            String line;
            while ((line = input.readLine()) != null) {
                var request = ReplicaWire.object(ReplicaJson.decode(line.getBytes(StandardCharsets.US_ASCII), bounds.maxFrameBytes()));
                String command = ReplicaWire.string(request, "command");
                try {
                    switch (command) {
                        case "activate" -> node.activate().get(30, TimeUnit.SECONDS);
                        case "reconstruct" -> node.reconstructLeader().get(30, TimeUnit.SECONDS);
                        case "catchup" -> node.catchUp(new ReplicationNodeId(ReplicaWire.string(request, "peer"))).get(30, TimeUnit.SECONDS);
                        case "checkpoint" -> node.checkpoint().get(30, TimeUnit.SECONDS);
                        case "arm" -> Files.writeString(root.resolve("armed"), barrier, StandardOpenOption.CREATE_NEW);
                        case "add", "update" -> node.submit(command.toUpperCase(java.util.Locale.ROOT), app.documents(command.toUpperCase(java.util.Locale.ROOT),
                                List.of(document(request)))).get(30, TimeUnit.SECONDS);
                        case "remove" -> node.submit("REMOVE", app.keys("REMOVE", List.of(Math.toIntExact(ReplicaWire.number(request, "id"))))).get(30, TimeUnit.SECONDS);
                        case "drop" -> node.submit("INDEX_DROP", app.dropIndex("value")).get(30, TimeUnit.SECONDS);
                        case "index" -> node.submit("INDEX_CREATE", app.index(INDEXES.getFirst())).get(30, TimeUnit.SECONDS);
                        case "read" -> node.read(engine -> engine.get(Math.toIntExact(ReplicaWire.number(request, "id"))));
                        case "status" -> { }
                        case "close" -> node.close();
                        default -> throw new IllegalArgumentException("unknown recovery control");
                    }
                    emit(report(node, app, command, true, "")); if (command.equals("close")) return;
                } catch (Exception error) {
                    Throwable cause = error;
                    while (cause.getCause() != null && (cause instanceof java.util.concurrent.ExecutionException || cause instanceof java.util.concurrent.CompletionException)) cause = cause.getCause();
                    emit(report(node, app, command, false, cause instanceof ReplicationException replication ? replication.reason().name() : cause.getClass().getSimpleName()));
                }
            }
        }
    }
    static Document document(Map<String, Object> request) { return new Document(Math.toIntExact(ReplicaWire.number(request, "id")), ReplicaWire.string(request, "value")); }
    static Map<String, Object> state(io.github.patricklfdm.generalsearch.engine.SearchEngine<Integer, Document> engine) {
        var documents = engine.search(document -> true).stream().map(document -> Map.<String, Object>of("id", document.id(), "value", document.value())).toList();
        var query = engine.search(io.github.patricklfdm.generalsearch.query.Query.eq(VALUE, "shared")).stream().map(Document::id).toList();
        return Map.of("documents", documents, "queryIds", query, "indexCount", (long) engine.metrics().registeredIndexCount());
    }
    private static Map<String, Object> report(ReplicaNode<Integer, Document> node, ReplicaApplication<Integer, Document> app, String command, boolean accepted, String reason) {
        var status = node.status(); var result = new java.util.TreeMap<String, Object>();
        result.put("command", command); result.put("accepted", accepted); result.put("reason", reason); result.put("epoch", status.activeEpoch());
        result.put("lastLogIndex", status.lastLogIndex()); result.put("commitIndex", status.commitIndex()); result.put("appliedIndex", status.appliedIndex());
        result.put("applicationSequence", status.applicationSequence()); result.put("state", status.state().name()); result.put("writeQuorum", status.writeQuorumAvailable());
        if (status.state() != ReplicaState.CLOSED) result.putAll(app.read(V50RecoveryWorker::state));
        return result;
    }
    static String json(Object value) { return new String(ReplicaJson.encode(value, 1024 * 1024), StandardCharsets.US_ASCII); }
    private static void emit(Map<String, Object> value) { System.out.println(json(value)); System.out.flush(); }
}
