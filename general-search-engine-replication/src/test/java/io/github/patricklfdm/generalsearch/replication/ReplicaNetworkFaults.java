package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Test-only deterministic socket-boundary faults, with bounded raw transcripts. */
final class ReplicaNetworkFaults implements ReplicaTransport.Events {
    private final Path root;
    private final String node;
    private final Map<String, Integer> attempts = new HashMap<>();
    private Map<String, Object> plan = Map.of();
    private CountDownLatch release = new CountDownLatch(0);
    private long sequence, bytes;
    ReplicaNetworkFaults(Path root, String node) { this.root = root; this.node = node; }
    synchronized void configure(Map<String, Object> request) throws IOException {
        String mode = ReplicaWire.string(request, "mode"), type = ReplicaWire.string(request, "type"), barrier = ReplicaWire.string(request, "barrier");
        if (!Set.of("drop-first", "drop-all", "hold-first").contains(mode) || !ReplicaWire.TYPES.contains(type)
                || !Set.of("BEFORE_REQUEST_WRITE", "BEFORE_RESPONSE_WRITE", "AFTER_RESPONSE_READ").contains(barrier))
            throw new IllegalArgumentException("unsupported deterministic fault");
        heal(); plan = Map.of("mode", mode, "type", type, "barrier", barrier);
        release = new CountDownLatch(1);
        Files.writeString(root.resolve("network-plans.jsonl"), V50RecoveryWorker.json(plan) + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
    synchronized void heal() { plan = Map.of(); release.countDown(); }
    @Override public void at(String barrier, Map<String, Object> request, Map<String, Object> response) throws IOException {
        String action = "deliver"; CountDownLatch held;
        synchronized (this) {
            if (++sequence > 100_000) throw new IOException("network transcript count exceeded");
            String key = barrier + ":" + request.get("traceId");
            int attempt = attempts.merge(key, 1, Integer::sum);
            if (barrier.equals(plan.get("barrier")) && request.get("type").equals(plan.get("type"))) {
                if (plan.get("mode").equals("drop-all") || attempt == 1 && plan.get("mode").equals("drop-first")) action = "disconnect";
                if (attempt == 1 && plan.get("mode").equals("hold-first")) action = "hold";
            }
            held = release;
            var event = new java.util.TreeMap<String, Object>();
            event.put("node", node); event.put("pid", ProcessHandle.current().pid()); event.put("sequence", sequence);
            event.put("barrier", barrier); event.put("attempt", attempt); event.put("action", action);
            event.put("request", request); event.put("response", response);
            event.put("requestSha256", ReplicaFormat.sha256(ReplicaWire.encode(request, 1024 * 1024)));
            String line = V50RecoveryWorker.json(event) + "\n"; bytes += line.length();
            if (bytes > 64L * 1024 * 1024) throw new IOException("network transcript byte bound exceeded");
            Files.writeString(root.resolve("network.jsonl"), line, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        }
        if (action.equals("disconnect")) throw new IOException("deterministic response/connection loss");
        if (action.equals("hold")) {
            try { if (!held.await(20, TimeUnit.SECONDS)) throw new IOException("held response release expired"); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
        }
    }
}
