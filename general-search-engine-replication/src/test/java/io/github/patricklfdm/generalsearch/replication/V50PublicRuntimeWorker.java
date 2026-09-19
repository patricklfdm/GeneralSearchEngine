package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.concurrent.atomic.AtomicLong;
import io.github.patricklfdm.generalsearch.admission.PublicRuntimeConsumer;

/** Fault injection only. Every lifecycle, data and administrative operation uses the external public consumer. */
public final class V50PublicRuntimeWorker {
    private V50PublicRuntimeWorker() { }
    public static void main(String[] args) throws Exception {
        Path evidence = Path.of(System.getProperty("gse.runtime.evidence")); Files.createDirectories(evidence);
        String cut = System.getProperty("gse.runtime.cut", "");
        ReplicaNode.Events events = (barrier, index) -> {
            if (barrier.equals(cut) && Files.exists(evidence.resolve("armed"))) {
                // The harness treats existence as publication. Publish the complete
                // identity atomically so it cannot observe an empty/partial file.
                Path pending = evidence.resolve("barrier.tmp");
                Files.writeString(pending, ProcessHandle.current().pid() + "\n" + barrier + "\n");
                Files.move(pending, evidence.resolve("barrier"), StandardCopyOption.ATOMIC_MOVE);
                try { new java.util.concurrent.CountDownLatch(1).await(); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
            }
        };
        var sequence = new AtomicLong();
        var attempts = new java.util.concurrent.ConcurrentHashMap<String, AtomicLong>();
        ReplicaTransport.Events network = (barrier, request, response) -> {
            long next = sequence.incrementAndGet();
            if (next > 10000) throw new IOException("bounded wire evidence exhausted");
            if (barrier.equals("BEFORE_REQUEST_WRITE")) Files.write(evidence.resolve("wire-" + next + ".bin"), ReplicaWire.encode(request, 1 << 20));
            if (barrier.equals("BEFORE_RESPONSE_WRITE")) {
                Files.write(evidence.resolve("wire-" + next + ".bin"), ReplicaWire.encode(response, 1 << 20));
                Path fault = evidence.resolve("lose-response");
                if (Files.exists(fault) && request.get("type").equals(Files.readString(fault).strip())) {
                    long attempt = attempts.computeIfAbsent(request.get("traceId").toString(), ignored -> new AtomicLong()).incrementAndGet();
                    Files.writeString(evidence.resolve("lost-" + next + ".txt"), request.get("type") + " " + request.get("traceId") + " " + attempt + "\n");
                    if (attempt == 1) throw new IOException("deterministic lost public response");
                }
            }
        };
        ReplicaRuntimeHooks.CURRENT.set(new ReplicaRuntimeHooks.Hooks(new ReplicaStore.Faults() {
            @Override public void at(String barrier) throws IOException { events.at(barrier, 0); }
        }, events, network));
        try { PublicRuntimeConsumer.main(args); } finally { ReplicaRuntimeHooks.CURRENT.remove(); }
    }
}
