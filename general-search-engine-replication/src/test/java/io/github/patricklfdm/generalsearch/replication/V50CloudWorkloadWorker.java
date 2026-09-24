package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import io.github.patricklfdm.generalsearch.admission.*;

/** Test-only force/network observations and fault barriers; no private application operation. */
public final class V50CloudWorkloadWorker {
    private V50CloudWorkloadWorker() { }
    private static Object field(Object object, String name) throws ReflectiveOperationException {
        var f=object.getClass().getDeclaredField(name); f.setAccessible(true); return f.get(object);
    }
    @SuppressWarnings("unchecked") private static Map<String,Object> observe(Object engine) {
        try {
            Object node=field(engine,"node"), transport=field(node,"transport");
            var senders=(Map<ReplicationNodeId,ThreadPoolExecutor>)field(transport,"senders");
            var permits=(Map<ReplicationNodeId,Semaphore>)field(transport,"outbound");
            var peers=new TreeMap<String,Object>();
            for(var entry:senders.entrySet()) peers.put(entry.getKey().value(),Map.of("queued",entry.getValue().getQueue().size(),
                    "inFlight",4-permits.get(entry.getKey()).availablePermits()));
            return Map.of("peers",peers,"queuedBytes",((AtomicLong)field(transport,"queuedBytes")).get(),
                    "writerQueue",((ThreadPoolExecutor)field(node,"writer")).getQueue().size());
        } catch(ReflectiveOperationException error) { throw new IllegalStateException(error); }
    }
    public static void main(String[] args) throws Exception {
        CloudWorkloadTelemetry.observer=V50CloudWorkloadWorker::observe;
        var starts=ThreadLocal.withInitial(HashMap<String,Long>::new);
        var delayedCatchup=new AtomicBoolean();
        long catchupDelayMillis=2L*CloudWorkload.number(CloudWorkload.plan(Path.of(args[3])).section("replicationBounds"),"requestTimeoutMillis");
        ReplicaNode.Events events=(name,index) -> {
            if(index>32768) throw new IOException("cloud log index bound");
            if(CloudWorkloadTelemetry.instrumented)
                CloudWorkloadTelemetry.record("events",Map.of("event",name,"index",index,"nanos",System.nanoTime()));
            // Local remote-adapter regression: a durable batch may outlive its caller's RPC wait.
            if(name.equals("AFTER_CATCHUP_BATCH") && CloudWorkloadTelemetry.fault.equals("delay-catchup-once") && delayedCatchup.compareAndSet(false,true)) {
                long start=System.nanoTime();
                try { Thread.sleep(catchupDelayMillis); }
                catch(InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
                CloudWorkloadTelemetry.record("faults",Map.of("action","delayed-catchup","index",index,"startNanos",start,"endNanos",System.nanoTime()));
            }
            if(name.equals(CloudWorkloadTelemetry.cut)) {
                CloudWorkloadTelemetry.record("barriers",Map.of("barrier",name,"index",index,"pid",ProcessHandle.current().pid()));
                Files.writeString(CloudWorkloadTelemetry.root().resolve("barrier"),ProcessHandle.current().pid()+"\n"+name+"\n");
                try { new CountDownLatch(1).await(); }
                catch(InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
            }
        };
        var storage=new ReplicaStore.Faults() {
            @Override public void at(String name) throws IOException {
                for(String kind:List.of("ENTRY","PROOF")) {
                    if(name.equals("BEFORE_"+kind+"_FORCE") && CloudWorkloadTelemetry.instrumented) starts.get().put(kind,System.nanoTime());
                    if(name.equals("AFTER_"+kind+"_FORCE")) {
                        Long start=starts.get().remove(kind);
                        if(start!=null) CloudWorkloadTelemetry.record("forces",Map.of("kind",kind,"startNanos",start,"endNanos",System.nanoTime()));
                    }
                }
                events.at(name,0);
            }
        };
        var ledger=ConcurrentHashMap.<String>newKeySet(); var lost=new AtomicBoolean();
        ReplicaTransport.Events network=(name,request,response) -> {
            boolean outgoing=name.equals("BEFORE_REQUEST_WRITE"), replying=name.equals("BEFORE_RESPONSE_WRITE");
            if(outgoing||replying) CloudWorkloadTelemetry.network(ReplicaWire.encode(outgoing?request:response,1<<20).length);
            String type=request.get("type").toString(), mode=CloudWorkloadTelemetry.fault;
            if(outgoing && (type.equals("APPEND")||type.equals("COMMIT_PROOF"))) {
                var payload=CloudWorkload.map(request.get("payload")); String key=(String)payload.get(type.equals("APPEND")?"entry":"proof");
                if(ledger.add(type+key)) {
                    if(ledger.size()>65536) throw new IOException("ledger count bound");
                    CloudWorkloadTelemetry.record("ledger",Map.of("type",type,"frame",key,"request",request));
                }
            }
            // The local timeout fixture must recover through an explicit batch:
            // ordinary queued replication cannot overtake it when the network heals.
            boolean blockedPeer=request.get("recipient").equals("node-3") &&
                    (mode.equals("block-node-3") || mode.equals("block-live-node-3") &&
                            (type.equals("APPEND") || type.equals("COMMIT_PROOF")));
            if(outgoing && (mode.equals("block-all")||blockedPeer)) {
                CloudWorkloadTelemetry.record("faults",Map.of("action","disconnect","type",type,"recipient",request.get("recipient")));
                throw new IOException("owned test network isolation");
            }
            if(replying && mode.equals("slow") && type.equals("APPEND")) {
                long start=System.nanoTime();
                try { Thread.sleep(250); } catch(InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
                CloudWorkloadTelemetry.record("faults",Map.of("action","delay","type",type,"startNanos",start,"endNanos",System.nanoTime()));
            }
            if(replying && mode.equals("lose-snapshot-ack") && type.equals("SNAPSHOT_CHUNK") && lost.compareAndSet(false,true)) {
                CloudWorkloadTelemetry.record("faults",Map.of("action","lost-ack","type",type,"request",request));
                throw new IOException("owned first snapshot ACK loss");
            }
            if(type.startsWith("SNAPSHOT") && replying)
                CloudWorkloadTelemetry.record("transfer",Map.of("type",type,"responseType",response.get("type"),"traceId",request.get("traceId")));
        };
        ReplicaRuntimeHooks.CURRENT.set(new ReplicaRuntimeHooks.Hooks(storage,events,network));
        try { V50CloudWorkloadConsumer.main(args); } finally { ReplicaRuntimeHooks.CURRENT.remove(); }
    }
}
