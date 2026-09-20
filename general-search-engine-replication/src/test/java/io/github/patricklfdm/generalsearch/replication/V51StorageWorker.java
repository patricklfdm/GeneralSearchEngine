package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;

import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Owned process storage probe, test classes only; never used by the public factory. */
public final class V51StorageWorker {
    private V51StorageWorker() { }
    private static void event(Path file, Map<String, Object> value) throws Exception {
        byte[] bytes = (new String(canonical(value), java.nio.charset.StandardCharsets.US_ASCII) + "\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        try (var channel = FileChannel.open(file, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND)) {
            var buffer = ByteBuffer.wrap(bytes); while (buffer.hasRemaining()) channel.write(buffer); channel.force(true);
        }
    }
    private static void print(Object value) { System.out.println(new String(canonical(value), java.nio.charset.StandardCharsets.US_ASCII)); }
    private static void cut(Path root, String stage, String wanted, String method) throws Exception {
        if (!stage.equals(wanted)) return;
        event(root.resolve("barrier.jsonl"), Map.of("pid", ProcessHandle.current().pid(), "cut", stage));
        if (method.equals("halt")) Runtime.getRuntime().halt(97);
        while (true) Thread.sleep(100);
    }
    private static AutomaticStore.Faults hooks(Path root, String node, String kind, byte[] record, String wanted, String method) {
        return new AutomaticStore.Faults() {
            @Override public int maximumWriteBytes() { return wanted.endsWith("_WRITE_CHUNK") ? 7 : Integer.MAX_VALUE; }
            @Override public void at(String stage) throws java.io.IOException {
                try {
                    event(root.resolve("events.jsonl"), Map.of("node", node, "pid", ProcessHandle.current().pid(), "stage", stage,
                            "recordSha256", sha(record), "timeNanos", System.nanoTime()));
                    cut(root, stage, wanted, method);
                } catch (java.io.IOException error) { throw error; }
                catch (Exception error) { throw new java.io.IOException(error); }
            }
        };
    }
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]); String command = args[1];
        if (command.equals("setup")) {
            byte[] manifest = setup(root); String kind = args[2]; byte[] first = entry(manifest, 1, null, 1, new byte[]{1, 2, 3});
            for (int i = 1; i <= 3; i++) {
                String node = "node-" + i;
                if (!kind.equals("PROMISE")) {
                    byte[] promise = promise(manifest, 2);
                    try (var store = AutomaticStore.open(root.resolve(node), manifest, node, ReplicationBounds.defaults(), hooks(root, node, "PROMISE", promise, "", ""))) {
                        store.promise(promise);
                    }
                }
                if (kind.equals("PROOF")) {
                    byte[] accepted = accept(manifest, first, 2);
                    try (var store = AutomaticStore.open(root.resolve(node), manifest, node, ReplicationBounds.defaults(), hooks(root, node, "ACCEPT", accepted, "", ""))) {
                        String receipt = store.accept(accepted);
                        event(root.resolve("events.jsonl"), Map.of("node", node, "pid", ProcessHandle.current().pid(), "stage", "ACCEPT_ACK",
                                "recordSha256", sha(accepted), "receipt", receipt, "timeNanos", System.nanoTime()));
                    }
                }
            }
            print(Map.of("status", "PREPARED", "execution", "test-only-storage-fixture")); return;
        }
        String node = args[2]; byte[] manifest = Files.readAllBytes(root.resolve(node).resolve("manifest.gsr"));
        if (command.equals("inspect")) {
            try (var store = AutomaticStore.open(root.resolve(node), manifest, node, ReplicationBounds.defaults(), AutomaticStore.Faults.NONE)) {
                var result = new java.util.LinkedHashMap<>(store.status()); result.put("status", "PASS");
                result.put("acceptedDigests", store.authorityDigests()); print(result);
            } catch (AutomaticReplicationException error) { print(Map.of("status", "REJECT", "reason", error.reason().name())); System.exit(3); }
            return;
        }
        if (command.equals("hold")) {
            try (var store = AutomaticStore.open(root.resolve(node), manifest, node, ReplicationBounds.defaults(), AutomaticStore.Faults.NONE)) {
                event(root.resolve(node + ".owner.jsonl"), Map.of("pid", ProcessHandle.current().pid(), "node", node));
                System.in.read();
            }
            return;
        }
        if (!command.equals("act")) throw new IllegalArgumentException("worker command");
        String kind = args[3], wanted = args[4], method = args[5];
        byte[] first = entry(manifest, 1, null, 1, new byte[]{1, 2, 3});
        byte[] record = switch (kind) {
            case "PROMISE" -> promise(manifest, 2);
            case "ACCEPT" -> accept(manifest, first, 2);
            case "PROOF" -> proof(manifest, first, 2);
            default -> throw new IllegalArgumentException("record kind");
        };
        try (var store = AutomaticStore.open(root.resolve(node), manifest, node, ReplicationBounds.defaults(), hooks(root, node, kind, record, wanted, method))) {
            String receipt = switch (kind) {
                case "PROMISE" -> { store.promise(record); yield ""; }
                case "ACCEPT" -> store.accept(record);
                case "PROOF" -> store.prove(record);
                default -> throw new IllegalArgumentException("record kind");
            };
            event(root.resolve("events.jsonl"), Map.of("node", node, "pid", ProcessHandle.current().pid(), "stage", kind + "_ACK",
                    "recordSha256", sha(record), "receipt", receipt, "timeNanos", System.nanoTime()));
            cut(root, kind + "_AFTER_ACK", wanted, method); print(store.status());
        }
    }
}
