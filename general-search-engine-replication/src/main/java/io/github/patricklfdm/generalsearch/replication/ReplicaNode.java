package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaWire.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Function;
import java.util.function.Supplier;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;

/** Internal Phase 3 coordinator. Bootstrap/reconciliation admission is reserved for Phase 4. */
final class ReplicaNode<K, T> implements AutoCloseable {
    interface Events {
        Events NONE = (barrier, index) -> { };
        void at(String barrier, long index) throws IOException;
    }
    private record Reply(ReplicationNodeId peer, Map<String, Object> message, Throwable error) { }
    private final ReplicaManifest manifest;
    private final ReplicationNodeId local;
    private final ReplicationBounds bounds;
    private final ReplicaStore store;
    private final ReplicaApplication<K, T> application;
    private final Events events;
    private final ThreadPoolExecutor writer;
    private final Semaphore admission;
    private final AtomicLong pendingBytes = new AtomicLong();
    private final AtomicLong sequence = new AtomicLong();
    private final java.util.Set<CompletableFuture<?>> pending = ConcurrentHashMap.newKeySet();
    private final ReplicaTransport transport;
    private volatile ReplicationStatus status;
    private volatile boolean closed, readable;
    private volatile Thread writerThread;
    private long activeEpoch, committed;
    private UUID incarnation = NO_INCARNATION;
    private volatile boolean writeReady;
    private volatile ReplicaState state = ReplicaState.CATCHING_UP;

    ReplicaNode(Path directory, ReplicaManifest manifest, ReplicationNodeId local, ReplicationBounds bounds,
                ReplicaApplication<K, T> application, ReplicaStore.Faults faults, Events events) {
        this.manifest = manifest; this.local = local; this.bounds = bounds; this.application = application; this.events = events;
        store = openStore(directory, manifest, local, bounds, application, faults);
        admission = new Semaphore(bounds.maxPendingClientOperations());
        writer = new ThreadPoolExecutor(1, 1, 0, TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(Math.min(bounds.maxPendingClientOperations() + bounds.maxInFlightPerPeer() * 3, 100_000)),
                task -> Thread.ofPlatform().daemon().name("gse-replica-writer-" + local.value()).unstarted(() -> {
                    writerThread = Thread.currentThread(); task.run();
                }), new ThreadPoolExecutor.AbortPolicy());
        try {
            // Phase 3 can reconstruct a complete local committed prefix; it never reconciles or truncates.
            for (long index = 1; index <= store.commitIndex(); index++) {
                application.prepare(store.entryAt(index)); application.publish(index);
            }
            committed = store.commitIndex();
            refresh();
            transport = new ReplicaTransport(manifest, local, bounds, this::handle);
        } catch (RuntimeException | Error error) {
            writer.shutdownNow(); store.close(); application.close(); throw error;
        }
    }

    private static ReplicaStore openStore(Path directory, ReplicaManifest manifest, ReplicationNodeId local,
                                          ReplicationBounds bounds, ReplicaApplication<?, ?> application, ReplicaStore.Faults faults) {
        try {
            application.validateManifest(manifest);
            require(application.appliedIndex() == 0, CONFLICTING_HISTORY, "node requires a fresh application materialization");
            return ReplicaStore.open(directory, manifest, local, bounds, faults);
        } catch (RuntimeException | Error error) { application.close(); throw error; }
    }

    ReplicationStatus status() {
        var value = status;
        return new ReplicationStatus(value.localNodeId(), value.role(), value.state(), value.writeQuorumAvailable(),
                value.promisedEpoch(), value.activeEpoch(), value.lastLogIndex(), value.commitIndex(), value.appliedIndex(),
                value.applicationSequence(), value.retainedLogBytes(), closed ? 0 : bounds.maxPendingClientOperations() - admission.availablePermits());
    }
    <R> R read(Function<SearchEngine<K, T>, R> reader) {
        requireLeader();
        require(!closed, CLOSED, "replica node closed");
        require(readable && state != ReplicaState.FAILED, QUORUM_UNAVAILABLE, "leader has no published activated view");
        return application.read(reader);
    }
    CompletableFuture<ReplicationStatus> activate() {
        if (!local.equals(manifest.leader())) return CompletableFuture.failedFuture(new ReplicationException(NOT_CONFIGURED_LEADER, "only configured leader can activate"));
        return enqueue(() -> {
            require(!writeReady, CONFLICTING_HISTORY, "leader is already activated");
            require(store.lastLogIndex() == store.commitIndex(), CONFLICTING_HISTORY, "uncommitted suffix requires Phase 4 reconciliation");
            require(application.appliedIndex() == store.commitIndex(), CONFLICTING_HISTORY, "unresolved publication requires reopen/recovery");
            state = ReplicaState.ACTIVATING; readable = false; refresh();
            try {
                Map<String, Object> probe = payload(Map.of());
                List<Reply> observed = quorum("AUTHORITY_STATUS_PROBE", probe, Math.max(1, store.promisedEpoch()), NO_INCARNATION,
                        reply -> {
                            var p = object(reply.message().get("payload"));
                            fields(p, "promisedEpoch", "lastLogIndex", "commitIndex", "lastDigest", "appliedIndex");
                            require(string(reply.message(), "type").equals("AUTHORITY_STATUS"), PROTOCOL_MISMATCH, "wrong authority response");
                            require(number(p, "lastLogIndex") == store.lastLogIndex() && number(p, "commitIndex") == store.commitIndex()
                                            && string(p, "lastDigest").equals(store.lastEntryDigest()), CONFLICTING_HISTORY, "history differs; reconciliation required");
                            require(number(p, "promisedEpoch") >= 1, PROTOCOL_MISMATCH, "invalid promised epoch");
                        });
                long maximum = store.promisedEpoch();
                for (var reply : observed) maximum = Math.max(maximum, number(object(reply.message().get("payload")), "promisedEpoch"));
                require(maximum < Long.MAX_VALUE, STALE_EPOCH, "epoch arithmetic exhausted");
                long proposedEpoch = maximum + 1;
                UUID proposedIncarnation = UUID.randomUUID();
                store.promise(manifest.leader(), proposedEpoch, proposedIncarnation);
                activeEpoch = proposedEpoch; incarnation = proposedIncarnation;
                quorum("ACTIVATE_EPOCH", payload(Map.of("commitIndex", store.commitIndex(), "lastDigest", store.lastEntryDigest())),
                        activeEpoch, incarnation, reply -> {
                            require(string(reply.message(), "type").equals("ACTIVATION_PROMISE"), PROTOCOL_MISMATCH, "wrong promise response");
                            var p = object(reply.message().get("payload")); fields(p, "promisedEpoch");
                            require(number(p, "promisedEpoch") == activeEpoch, STALE_EPOCH, "promise epoch mismatch");
                        });
                event("AFTER_PROMISE_QUORUM", store.lastLogIndex());
                commit("NO_OP", new byte[0]);
                readable = true; writeReady = true; state = ReplicaState.READY; refresh();
                return status;
            } catch (RuntimeException error) { stopWrites(error); throw error; }
        }, false, 0);
    }

    CompletableFuture<Void> submit(String operation, byte[] payload) {
        if (!local.equals(manifest.leader())) return CompletableFuture.failedFuture(new ReplicationException(NOT_CONFIGURED_LEADER, "follower rejects application mutation"));
        if (!writeReady || closed) return CompletableFuture.failedFuture(new ReplicationException(closed ? CLOSED : QUORUM_UNAVAILABLE, "leader has no write quorum"));
        require(payload != null && payload.length <= bounds.maxFrameBytes() - 197, CAPACITY_EXCEEDED, "entry exceeds frame limit");
        // One bounded owned copy; cancelled futures retain admission until execution finishes.
        if (!admission.tryAcquire()) return CompletableFuture.failedFuture(new ReplicationException(CAPACITY_EXCEEDED, "pending operation limit reached"));
        long memory = pendingBytes.addAndGet(payload.length);
        if (memory > (long) bounds.maxFrameBytes() * 4) {
            pendingBytes.addAndGet(-payload.length); admission.release();
            return CompletableFuture.failedFuture(new ReplicationException(CAPACITY_EXCEEDED, "pending payload byte limit reached"));
        }
        byte[] owned = payload.clone();
        return enqueue(() -> {
            require(writeReady && !closed, QUORUM_UNAVAILABLE, "leader writes are suspended");
            require(!operation.equals("NO_OP") && !operation.equals("SNAPSHOT_MARKER"), PROTOCOL_MISMATCH, "control entry is not an application mutation");
            commit(operation, owned); refresh(); return null;
        }, true, owned.length);
    }

    private void commit(String operation, byte[] bytes) {
        require(store.lastLogIndex() == application.appliedIndex(), CONFLICTING_HISTORY, "an earlier entry is unresolved");
        var entry = new ReplicaEntry(manifest.digest(), activeEpoch, incarnation, store.lastLogIndex() + 1,
                operation, store.lastEntryEpoch(), store.lastLogIndex(), store.lastEntryDigest(), bytes);
        byte[] encoded = entry.encode(bounds.maxFrameBytes());
        String digest = frameDigest(encoded);
        Map<String, Object> append = payload(Map.of("entry", Base64.getEncoder().encodeToString(encoded)));
        for (var member : manifest.members()) if (!member.nodeId().equals(local))
            ReplicaWire.encode(request(member.nodeId(), "APPEND", append, activeEpoch, incarnation), bounds.maxFrameBytes());
        // Application business/codec failures occur before the first authority write.
        application.prepare(entry);
        try {
            var own = store.append(manifest.leader(), entry);
            event("AFTER_LOCAL_ENTRY_FORCE", entry.index());
            List<Reply> acknowledgements = quorum("APPEND", append, activeEpoch, incarnation, reply -> {
                var p = object(reply.message().get("payload")); fields(p, "index", "entryDigest", "receiptDigest");
                require(string(reply.message(), "type").equals("DURABLE_ACK") && number(p, "index") == entry.index()
                        && string(p, "entryDigest").equals(digest)
                        && string(p, "receiptDigest").equals(ReplicaProof.acknowledgement(reply.peer(), entry, digest).digest()),
                        INTEGRITY_FAILURE, "invalid durable-entry acknowledgement");
            });
            event("AFTER_ENTRY_QUORUM", entry.index());
            var receipts = new ArrayList<ReplicaProof.Receipt>(); receipts.add(own);
            for (var ack : acknowledgements) receipts.add(ReplicaProof.acknowledgement(ack.peer(), entry, digest));
            receipts.sort(java.util.Comparator.comparing(ReplicaProof.Receipt::voter));
            var proof = new ReplicaProof(manifest.digest(), activeEpoch, incarnation, entry.index(), digest, entry.previousDigest(), receipts);
            String proofDigest = store.storeProof(manifest.leader(), proof);
            event("AFTER_LOCAL_PROOF_FORCE", entry.index());
            quorum("COMMIT_PROOF", payload(Map.of("proof", Base64.getEncoder().encodeToString(proof.encode()))),
                    activeEpoch, incarnation, reply -> {
                        var p = object(reply.message().get("payload")); fields(p, "index", "proofDigest");
                        require(string(reply.message(), "type").equals("COMMIT_PROOF_ACK") && number(p, "index") == entry.index()
                                && string(p, "proofDigest").equals(proofDigest), INTEGRITY_FAILURE, "invalid proof acknowledgement");
                    });
            committed = entry.index();
            event("AFTER_PROOF_QUORUM", entry.index());
            event("BEFORE_APPLICATION_PUBLICATION", entry.index());
            application.publish(entry.index());
            refresh();
            event("AFTER_APPLICATION_PUBLICATION", entry.index());
            event("BEFORE_CLIENT_SUCCESS", entry.index());
        } catch (RuntimeException error) { stopWrites(error); throw error; }
    }

    private Map<String, Object> handle(Map<String, Object> request) {
        try {
            return enqueue(() -> receive(request), false, 0).get(bounds.requestTimeoutMillis(), TimeUnit.MILLISECONDS);
        } catch (Exception error) {
            Throwable cause = unwrap(error);
            String reason = cause instanceof ReplicationException replication ? replication.reason().name() : INTEGRITY_FAILURE.name();
            return response(request, "REJECT", payload(Map.of("reason", reason)));
        }
    }

    private Map<String, Object> receive(Map<String, Object> request) {
        ReplicaWire.identity(request, manifest, local);
        String type = string(request, "type");
        var p = object(request.get("payload"));
        if (type.equals("HANDSHAKE")) {
            fields(p);
            return response(request, "HANDSHAKE", payload(Map.of()));
        }
        if (type.equals("AUTHORITY_STATUS_PROBE")) {
            fields(p);
            return response(request, "AUTHORITY_STATUS", payload(Map.of("promisedEpoch", store.promisedEpoch(),
                    "lastLogIndex", store.lastLogIndex(), "commitIndex", store.commitIndex(),
                    "lastDigest", store.lastEntryDigest(), "appliedIndex", application.appliedIndex())));
        }
        require(string(request, "sender").equals(manifest.leader().value()) && !local.equals(manifest.leader()),
                NOT_CONFIGURED_LEADER, "only configured leader may write followers");
        long epoch = number(request, "epoch"); UUID requested = UUID.fromString(string(request, "incarnationId"));
        if (type.equals("ACTIVATE_EPOCH")) {
            fields(p, "commitIndex", "lastDigest");
            require(store.lastLogIndex() == store.commitIndex() && number(p, "commitIndex") == store.commitIndex()
                    && string(p, "lastDigest").equals(store.lastEntryDigest()), CONFLICTING_HISTORY, "activation requires matching committed history");
            store.promise(manifest.leader(), epoch, requested);
            activeEpoch = epoch; incarnation = requested; state = ReplicaState.READY; refresh();
            return response(request, "ACTIVATION_PROMISE", payload(Map.of("promisedEpoch", store.promisedEpoch())));
        }
        require(state == ReplicaState.READY && epoch == activeEpoch && incarnation.equals(requested), STALE_EPOCH, "follower has not activated this incarnation");
        try {
            if (type.equals("APPEND")) {
                fields(p, "entry");
                var entry = ReplicaEntry.decode(decodeRecord(binary(p, "entry", bounds.maxFrameBytes()), ENTRY, bounds.maxFrameBytes()));
                require(entry.manifestDigest().equals(manifest.digest()), PROTOCOL_MISMATCH, "entry manifest mismatch");
                require(entry.epoch() == epoch && entry.incarnation().equals(requested), STALE_EPOCH, "entry envelope epoch mismatch");
                if (entry.index() > store.lastLogIndex()) {
                    require(entry.index() == store.lastLogIndex() + 1 && entry.previousEpoch() == store.lastEntryEpoch()
                            && entry.previousDigest().equals(store.lastEntryDigest()), CONFLICTING_HISTORY, "append predecessor mismatch");
                    require(application.appliedIndex() == store.lastLogIndex(), QUORUM_UNAVAILABLE, "previous append awaits commit proof");
                    application.prepare(entry);
                }
                var receipt = store.append(manifest.leader(), entry);
                refresh(); event("FOLLOWER_BEFORE_ENTRY_ACK", entry.index());
                return response(request, "DURABLE_ACK", payload(Map.of("index", entry.index(),
                        "entryDigest", frameDigest(entry.encode(bounds.maxFrameBytes())), "receiptDigest", receipt.digest())));
            }
            if (type.equals("COMMIT_PROOF")) {
                fields(p, "proof");
                var proof = ReplicaProof.decode(decodeRecord(binary(p, "proof", MAX_METADATA_BYTES), PROOF, MAX_METADATA_BYTES));
                require(proof.epoch() == epoch && proof.incarnation().equals(requested), STALE_EPOCH, "proof envelope epoch mismatch");
                String digest = store.storeProof(manifest.leader(), proof);
                committed = store.commitIndex();
                if (proof.index() > application.appliedIndex()) application.publish(proof.index());
                refresh(); event("FOLLOWER_BEFORE_PROOF_ACK", proof.index());
                return response(request, "COMMIT_PROOF_ACK", payload(Map.of("index", proof.index(), "proofDigest", digest)));
            }
            throw new ReplicationException(PROTOCOL_MISMATCH, "message is not enabled in Phase 3");
        } catch (IOException error) { throw failure(INTEGRITY_FAILURE, "malformed replicated record", error); }
        catch (ReplicationException error) {
            if (error.reason() == STORAGE_FAILURE) { state = ReplicaState.FAILED; refresh(); }
            throw error;
        }
    }

    private byte[] binary(Map<String, Object> payload, String key, int maximum) {
        String encoded = string(payload, key);
        require(encoded.length() <= ((long) maximum + 2) / 3 * 4, CAPACITY_EXCEEDED, "binary payload exceeds bound");
        try {
            byte[] bytes = Base64.getDecoder().decode(encoded);
            require(bytes.length <= maximum && Base64.getEncoder().encodeToString(bytes).equals(encoded), INTEGRITY_FAILURE, "noncanonical base64");
            return bytes;
        } catch (IllegalArgumentException error) { throw failure(INTEGRITY_FAILURE, "invalid base64", error); }
    }

    private List<Reply> quorum(String type, Map<String, Object> payload, long epoch, UUID incarnation,
                               java.util.function.Consumer<Reply> validate) {
        var replies = new ArrayBlockingQueue<Reply>(2);
        for (var member : manifest.members()) if (!member.nodeId().equals(local)) {
            var peer = member.nodeId();
            transport.exchange(peer, request(peer, type, payload, epoch, incarnation))
                    .whenComplete((value, error) -> replies.offer(new Reply(peer, value, error)));
        }
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis() + 100L);
        Throwable last = null;
        for (int received = 0; received < 2; received++) {
            try {
                Reply reply = replies.poll(Math.max(0, deadline - System.nanoTime()), TimeUnit.NANOSECONDS);
                if (reply == null) break;
                if (reply.error() != null) { last = reply.error(); continue; }
                if (string(reply.message(), "type").equals("REJECT")) {
                    var body = object(reply.message().get("payload")); fields(body, "reason");
                    last = new ReplicationException(ReplicationException.Reason.valueOf(string(body, "reason")), "peer rejected " + type);
                    continue;
                }
                try { validate.accept(reply); return List.of(reply); }
                catch (RuntimeException error) { last = error; }
            } catch (InterruptedException error) { Thread.currentThread().interrupt(); throw failure(CLOSED, "quorum wait interrupted", error); }
        }
        throw failure(QUORUM_UNAVAILABLE, "no valid remote voter for " + type, last);
    }

    private Map<String, Object> request(ReplicationNodeId peer, String type, Map<String, Object> payload, long epoch, UUID incarnation) {
        long next = sequence.incrementAndGet(); require(next > 0, PROTOCOL_MISMATCH, "event sequence exhausted");
        return message(manifest, local, peer, epoch, incarnation, type, payload, UUID.randomUUID(), next);
    }
    private Map<String, Object> response(Map<String, Object> request, String type, Map<String, Object> payload) {
        return message(manifest, local, new ReplicationNodeId(string(request, "sender")), number(request, "epoch"),
                UUID.fromString(string(request, "incarnationId")), type, payload,
                UUID.fromString(string(request, "traceId")), number(request, "eventSequence"));
    }
    private Map<String, Object> payload(Map<String, Object> values) {
        var result = new java.util.TreeMap<>(values); result.put("manifestDigest", manifest.digest()); return result;
    }
    private void event(String barrier, long index) {
        try { events.at(barrier, index); }
        catch (IOException error) { throw failure(STORAGE_FAILURE, "runtime barrier I/O failure", error); }
    }
    private void requireLeader() { require(local.equals(manifest.leader()), NOT_CONFIGURED_LEADER, "follower rejects application reads"); }
    private void stopWrites(Throwable error) {
        writeReady = false;
        state = error instanceof ReplicationException replication && replication.reason() == QUORUM_UNAVAILABLE
                ? ReplicaState.UNAVAILABLE : ReplicaState.FAILED;
        refresh();
    }
    private void refresh() {
        status = new ReplicationStatus(local, local.equals(manifest.leader()) ? ReplicaRole.CONFIGURED_LEADER : ReplicaRole.FOLLOWER,
                state, writeReady, store.promisedEpoch(), activeEpoch, store.lastLogIndex(), committed,
                application.appliedIndex(), application.sequence(), store.retainedLogBytes(),
                bounds.maxPendingClientOperations() - admission.availablePermits());
    }
    private <R> CompletableFuture<R> enqueue(Supplier<R> action, boolean admitted, int bytes) {
        var result = new CompletableFuture<R>(); pending.add(result);
        Runnable cleanup = () -> {
            pending.remove(result);
            if (admitted) { pendingBytes.addAndGet(-bytes); admission.release(); }
        };
        try {
            require(!closed, CLOSED, "replica node closed");
            writer.execute(() -> {
                try { require(!closed, CLOSED, "replica node closed"); result.complete(action.get()); }
                catch (Throwable error) { result.completeExceptionally(unwrap(error)); }
                finally { cleanup.run(); }
            });
        } catch (RuntimeException error) { cleanup.run(); result.completeExceptionally(error); }
        return result;
    }
    private static Throwable unwrap(Throwable error) {
        while ((error instanceof java.util.concurrent.ExecutionException || error instanceof java.util.concurrent.CompletionException)
                && error.getCause() != null) error = error.getCause();
        return error;
    }
    @Override public void close() {
        if (closed) return;
        closed = true; writeReady = false; readable = false;
        var failure = new ReplicationException(CLOSED, "replica node closed");
        for (var future : pending) future.completeExceptionally(failure);
        transport.close();
        writer.shutdownNow();
        if (Thread.currentThread() != writerThread) {
            try { require(writer.awaitTermination(bounds.requestTimeoutMillis() + 100L, TimeUnit.MILLISECONDS), CLOSED, "writer did not terminate"); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); throw ReplicaFormat.failure(CLOSED, "node close interrupted", error); }
        }
        pending.clear();
        application.close(); store.close();
        state = ReplicaState.CLOSED; refresh();
    }
}
