package io.github.patricklfdm.generalsearch.replication;

import io.github.patricklfdm.generalsearch.admission.PerformanceTelemetry;
import io.github.patricklfdm.generalsearch.admission.V50PerformanceConsumer;

/** Observations only; the external consumer owns all public application operations. */
public final class V50PerformanceWorker {
    private V50PerformanceWorker() { }
    public static void main(String[] args) throws Exception {
        var forceStarts = ThreadLocal.withInitial(java.util.HashMap<String, Long>::new);
        var storage = new ReplicaStore.Faults() {
            @Override public void at(String barrier) {
                for (String kind : new String[]{"ENTRY", "PROOF"}) {
                    if (barrier.equals("BEFORE_" + kind + "_FORCE") && PerformanceTelemetry.enabled())
                        forceStarts.get().put(kind, System.nanoTime());
                    else if (barrier.equals("AFTER_" + kind + "_FORCE")) {
                        Long start = forceStarts.get().remove(kind);
                        if (start != null) PerformanceTelemetry.force(kind, start, System.nanoTime());
                    }
                }
            }
        };
        ReplicaNode.Events events = (name, index) -> PerformanceTelemetry.event(name, index, System.nanoTime());
        ReplicaTransport.Events network = (name, request, response) -> {
            if (PerformanceTelemetry.enabled() && (name.equals("BEFORE_REQUEST_WRITE") || name.equals("BEFORE_RESPONSE_WRITE")))
                PerformanceTelemetry.wire(ReplicaWire.encode(name.equals("BEFORE_REQUEST_WRITE") ? request : response, 1 << 20).length);
        };
        ReplicaRuntimeHooks.CURRENT.set(new ReplicaRuntimeHooks.Hooks(storage, events, network));
        try { V50PerformanceConsumer.main(args); } finally { ReplicaRuntimeHooks.CURRENT.remove(); }
    }
}
