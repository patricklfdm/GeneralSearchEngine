package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Test-only separate-JVM driver; all replication/codec/publication work uses production classes. */
public final class V50LeaderWorker {
    private V50LeaderWorker() { }
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        int ordinal = Integer.parseInt(args[1]);
        var ports = Arrays.stream(args[2].split(",")).map(Integer::parseInt).toList();
        String barrier = args.length > 3 ? args[3] : "";
        var manifest = manifest(ports);
        var id = manifest.members().get(ordinal - 1).nodeId();
        Files.createDirectories(root);
        Path directory = root.resolve("replica");
        var bounds = bounds(2000, 8);
        if (!Files.exists(directory)) ReplicaStore.initialize(directory, manifest, id, bounds, ReplicaStore.Faults.NONE);
        var app = application(root.resolve("materialization-reserved"), bounds);
        var events = (ReplicaNode.Events) (point, index) -> {
            var event = Map.<String, Object>of("node", id.value(), "pid", ProcessHandle.current().pid(), "index", index,
                    "barrier", point, "monotonicNanos", System.nanoTime());
            Files.writeString(root.resolve("events.jsonl"), new String(ReplicaJson.encode(event, 4096), StandardCharsets.US_ASCII) + "\n",
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            if (ordinal == 1 && index == 2 && point.equals(barrier)) {
                Files.write(root.resolve("barrier.json"), ReplicaJson.encode(event, 4096), StandardOpenOption.CREATE_NEW);
                try { new CountDownLatch(1).await(); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
            }
        };
        try (var node = new ReplicaNode<>(directory, manifest, id, bounds, app, ReplicaStore.Faults.NONE, events);
             var input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.US_ASCII))) {
            emit(Map.of("ready", true, "pid", ProcessHandle.current().pid(), "node", id.value()));
            String line;
            while ((line = input.readLine()) != null) {
                var request = ReplicaWire.object(ReplicaJson.decode(line.getBytes(StandardCharsets.US_ASCII), 8192));
                String command = ReplicaWire.string(request, "command");
                try {
                    switch (command) {
                        case "activate" -> node.activate().get(20, TimeUnit.SECONDS);
                        case "add" -> node.submit("ADD", app.documents("ADD", List.of(new Document(
                                Math.toIntExact(ReplicaWire.number(request, "id")), ReplicaWire.string(request, "value"))))).get(20, TimeUnit.SECONDS);
                        case "read" -> node.read(engine -> engine.get(Math.toIntExact(ReplicaWire.number(request, "id"))));
                        case "status" -> { }
                        case "close" -> node.close();
                        default -> throw new IllegalArgumentException("unknown worker command");
                    }
                    emit(report(node, app, command, true, ""));
                    if (command.equals("close")) return;
                } catch (Exception error) {
                    Throwable cause = error;
                    while (cause.getCause() != null && (cause instanceof java.util.concurrent.ExecutionException
                            || cause instanceof java.util.concurrent.CompletionException)) cause = cause.getCause();
                    String reason = cause instanceof ReplicationException replication ? replication.reason().name() : cause.getClass().getSimpleName();
                    emit(report(node, app, command, false, reason));
                }
            }
        }
    }
    private static Map<String, Object> report(ReplicaNode<Integer, Document> node,
                                               ReplicaApplication<Integer, Document> app, String command,
                                               boolean accepted, String reason) {
        var status = node.status();
        var result = new java.util.TreeMap<String, Object>();
        result.put("command", command); result.put("accepted", accepted); result.put("reason", reason);
        result.put("epoch", status.activeEpoch()); result.put("lastLogIndex", status.lastLogIndex());
        result.put("commitIndex", status.commitIndex()); result.put("appliedIndex", status.appliedIndex());
        result.put("applicationSequence", status.applicationSequence()); result.put("state", status.state().name());
        result.put("writeQuorum", status.writeQuorumAvailable());
        // Test-only local diagnostic: public follower reads are tested separately and reject.
        var documents = new ArrayList<Map<String, Object>>();
        if (status.state() != ReplicaState.CLOSED) {
            app.read(engine -> {
                for (int i = 1; i <= 10; i++) {
                    Document document = engine.get(i);
                    if (document != null) documents.add(Map.of("id", document.id(), "value", document.value()));
                }
                return null;
            });
        }
        result.put("documents", documents);
        return result;
    }
    private static void emit(Map<String, Object> value) {
        System.out.println(new String(ReplicaJson.encode(value, 8192), StandardCharsets.US_ASCII));
        System.out.flush();
    }
}
