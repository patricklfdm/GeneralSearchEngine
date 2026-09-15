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
    private final ReplicaTransfer incoming;
    private final byte[] emptyApplication;
    private byte[] exportedImage;
    private UUID exportedId, installedTransfer;
    private String installedImageDigest;
    private Map<String, Object> installedReceipt;

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
        emptyApplication = initialSnapshot(application);
        store = openStore(directory, manifest, local, bounds, application, faults);
        incoming = new ReplicaTransfer(directory, manifest, local, bounds);
        admission = new Semaphore(bounds.maxPendingClientOperations());
        writer = new ThreadPoolExecutor(1, 1, 0, TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(Math.min(bounds.maxPendingClientOperations() + bounds.maxInFlightPerPeer() * 3, 100_000)),
                task -> Thread.ofPlatform().daemon().name("gse-replica-writer-" + local.value()).unstarted(() -> {
                    writerThread = Thread.currentThread(); task.run();
                }), new ThreadPoolExecutor.AbortPolicy());
        try {
            if (store.commitIndex() > 0 || store.snapshotIndex() > 0) {
                try (var rebuilt = application.rebuild(store.image(emptyApplication))) { application.replaceWith(rebuilt); }
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
            return ReplicaStore.openForRecovery(directory, manifest, local, bounds, faults);
        } catch (RuntimeException | Error error) { application.close(); throw error; }
    }

    private static byte[] initialSnapshot(ReplicaApplication<?, ?> application) {
        try { return application.emptySnapshot(); }
        catch (RuntimeException | Error error) { application.close(); throw error; }
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
    CompletableFuture<ReplicationStatus> activate() { return recover(false); }

    /** Explicit replacement-leader reconstruction requires both surviving voter identities. */
    CompletableFuture<ReplicationStatus> reconstructLeader() { return recover(true); }

    private CompletableFuture<ReplicationStatus> recover(boolean replacement) {
        if (!local.equals(manifest.leader())) return CompletableFuture.failedFuture(new ReplicationException(NOT_CONFIGURED_LEADER, "only configured leader can activate"));
        return enqueue(() -> {
            require(!writeReady, CONFLICTING_HISTORY, "leader is already activated");
            require(store.voter() || replacement, CONFLICTING_HISTORY, "replacement leader requires explicit two-survivor reconstruction");
            state = ReplicaState.ACTIVATING; readable = false; refresh();
            try {
                var observed = contact("AUTHORITY_STATUS_PROBE", payload(Map.of()), Math.max(1, store.promisedEpoch()), NO_INCARNATION, "AUTHORITY_STATUS");
                var voters = observed.stream().filter(reply -> Boolean.TRUE.equals(object(reply.message().get("payload")).get("voter"))).toList();
                require(voters.size() >= (store.voter() ? 1 : 2), QUORUM_UNAVAILABLE, "recovery requires an intact voter quorum");
                long maximum = store.promisedEpoch();
                for (var reply : voters) maximum = Math.max(maximum, number(object(reply.message().get("payload")), "promisedEpoch"));
                require(maximum < Long.MAX_VALUE, STALE_EPOCH, "epoch arithmetic exhausted");
                long proposed = maximum + 1; UUID proposedIncarnation = UUID.randomUUID();
                store.promise(manifest.leader(), proposed, proposedIncarnation);
                activeEpoch = proposed; incarnation = proposedIncarnation;
                var promised = contact("ACTIVATE_EPOCH", payload(Map.of("recovery", true)), activeEpoch, incarnation, "ACTIVATION_PROMISE")
                        .stream().filter(reply -> Boolean.TRUE.equals(object(reply.message().get("payload")).get("voter"))).toList();
                require(promised.size() >= (store.voter() ? 1 : 2), QUORUM_UNAVAILABLE, "new epoch was not promised by a voter quorum");
                event("AFTER_PROMISE_QUORUM", store.lastLogIndex());
                Reply source = null; long highest = store.commitIndex();
                for (var reply : promised) {
                    long index = number(object(reply.message().get("payload")), "commitIndex");
                    if (index > highest) { highest = index; source = reply; }
                }
                ReplicaRecoveryImage image = source == null ? store.image(emptyApplication) : download(source.peer());
                require(image.index() == highest, CONFLICTING_HISTORY, "recovery source changed its protected boundary");
                for (var reply : promised) {
                    var status = object(reply.message().get("payload")); long index = number(status, "commitIndex");
                    require(image.digestAt(index).equals(string(status, "commitDigest")), CONFLICTING_HISTORY, "valid voter proofs conflict");
                }
                image = store.preserveSnapshot(image);
                event("AFTER_RECOVERY_SELECTION", image.index());
                establishLocalFloor(promised, image);
                installLocal(image, replacement);
                int ready = 0;
                for (var reply : promised) {
                    try {
                        var status = object(reply.message().get("payload"));
                        establishPeerFloor(reply.peer(), status, image);
                        if (number(status, "lastLogIndex") != image.index() || number(status, "commitIndex") != image.index()
                                || Boolean.TRUE.equals(status.get("damagedTail"))) upload(reply.peer(), image, false);
                        ready(reply.peer(), image); ready++;
                    } catch (ReplicationException error) { if (error.reason() != QUORUM_UNAVAILABLE && error.reason() != CAPACITY_EXCEEDED) throw error; }
                }
                require(ready >= 1, QUORUM_UNAVAILABLE, "no recovered READY follower");
                event("AFTER_RECOVERY_READY_QUORUM", image.index());
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
        if (type.equals("AUTHORITY_STATUS_PROBE")) return probe(request, p);
        require(string(request, "sender").equals(manifest.leader().value()) && !local.equals(manifest.leader()),
                NOT_CONFIGURED_LEADER, "only configured leader may write followers");
        long epoch = number(request, "epoch"); UUID requested = UUID.fromString(string(request, "incarnationId"));
        if (type.equals("ACTIVATE_EPOCH")) {
            fields(p, "recovery"); require(Boolean.TRUE.equals(p.get("recovery")), PROTOCOL_MISMATCH, "activation requires recovery fencing");
            if (epoch > store.promisedEpoch()) {
                try { incoming.abort(); }
                catch (IOException error) { throw failure(STORAGE_FAILURE, "cannot discard superseded transfer staging", error); }
            }
            store.promise(manifest.leader(), epoch, requested);
            activeEpoch = epoch; incarnation = requested; state = ReplicaState.CATCHING_UP; refresh();
            return response(request, "ACTIVATION_PROMISE", authorityStatus());
        }
        require(epoch == activeEpoch && incarnation.equals(requested), STALE_EPOCH, "follower has not promised this incarnation");
        if (type.equals("SNAPSHOT_OFFER") || type.equals("SNAPSHOT_CHUNK") || type.equals("SNAPSHOT_INSTALL")
                || type.equals("SNAPSHOT_ABORT") || type.equals("COMMIT_ADVANCE")) return recoveryMessage(request, p, type);
        require(store.voter() && state == ReplicaState.READY && epoch == activeEpoch && incarnation.equals(requested), STALE_EPOCH, "follower has not activated this incarnation");
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

    private Map<String, Object> authorityStatus() {
        return payload(Map.of("promisedEpoch", store.promisedEpoch(), "lastLogIndex", store.lastLogIndex(),
                "commitIndex", store.commitIndex(), "lastDigest", store.lastEntryDigest(), "commitDigest", store.digestAt(store.commitIndex()),
                "appliedIndex", application.appliedIndex(), "snapshotIndex", store.snapshotIndex(), "recoveryFloor", store.recoveryFloor(),
                "voter", store.voter(), "damagedTail", store.damagedTail()));
    }

    private Map<String, Object> probe(Map<String, Object> request, Map<String, Object> p) {
        if (!p.containsKey("action")) { fields(p); return response(request, "AUTHORITY_STATUS", authorityStatus()); }
        require(string(request, "sender").equals(manifest.leader().value()) && number(request, "epoch") == activeEpoch
                && string(request, "incarnationId").equals(incarnation.toString()), STALE_EPOCH, "recovery export requires the fenced leader");
        String action = string(p, "action");
        if (action.equals("export")) {
            fields(p, "action"); exportedImage = store.image(emptyApplication).encode(bounds); exportedId = UUID.randomUUID();
            return response(request, "AUTHORITY_STATUS", payload(Map.of("transferId", exportedId.toString(), "length", (long) exportedImage.length, "digest", sha256(exportedImage))));
        }
        if (action.equals("chunk")) {
            fields(p, "action", "transferId", "offset", "length");
            require(exportedId != null && string(p, "transferId").equals(exportedId.toString()), CONFLICTING_HISTORY, "recovery export expired");
            long offset = number(p, "offset"), length = number(p, "length");
            require(offset >= 0 && length > 0 && length <= ReplicaTransfer.chunkSize(bounds) && offset <= exportedImage.length - length,
                    CAPACITY_EXCEEDED, "recovery export chunk exceeds bounds");
            return response(request, "AUTHORITY_STATUS", payload(Map.of("transferId", exportedId.toString(), "offset", offset,
                    "data", Base64.getEncoder().encodeToString(java.util.Arrays.copyOfRange(exportedImage, (int) offset, (int) (offset + length))))));
        }
        throw new ReplicationException(PROTOCOL_MISMATCH, "unknown recovery probe action");
    }

    private Map<String, Object> recoveryMessage(Map<String, Object> request, Map<String, Object> p, String type) {
        try {
            if (type.equals("SNAPSHOT_OFFER")) {
                fields(p, "transferId", "length", "digest");
                incoming.begin(UUID.fromString(string(p, "transferId")), number(p, "length"), string(p, "digest"));
                state = ReplicaState.CATCHING_UP; refresh(); event("AFTER_SNAPSHOT_OFFER_FORCE", store.commitIndex());
                return response(request, type, payload(Map.of("transferId", string(p, "transferId"))));
            }
            if (type.equals("SNAPSHOT_CHUNK")) {
                fields(p, "transferId", "offset", "data");
                long next = incoming.chunk(UUID.fromString(string(p, "transferId")), number(p, "offset"), binary(p, "data", ReplicaTransfer.chunkSize(bounds)));
                event("AFTER_SNAPSHOT_CHUNK_FORCE", store.commitIndex());
                return response(request, type, payload(Map.of("transferId", string(p, "transferId"), "offset", next)));
            }
            if (type.equals("SNAPSHOT_ABORT")) {
                fields(p); incoming.abort(); return response(request, type, payload(Map.of()));
            }
            if (type.equals("SNAPSHOT_INSTALL")) {
                fields(p, "transferId", "admit"); require(p.get("admit") instanceof Boolean, PROTOCOL_MISMATCH, "invalid snapshot admission flag"); UUID id = UUID.fromString(string(p, "transferId"));
                if (id.equals(installedTransfer)) return response(request, type, installedReceipt);
                byte[] bytes = incoming.complete(id); var image = ReplicaRecoveryImage.decode(bytes, manifest, bounds);
                boolean admit = Boolean.TRUE.equals(p.get("admit"));
                if (!store.voter()) require(admit && image.index() > 0
                                && image.anchors().getLast().epoch() == activeEpoch && image.anchors().getLast().incarnation().equals(incarnation),
                        CONFLICTING_HISTORY, "replacement follower needs current activated committed authority");
                installLocal(image, admit);
                installedTransfer = id; installedImageDigest = sha256(bytes);
                installedReceipt = payload(Map.of("transferId", id.toString(), "imageDigest", installedImageDigest,
                        "index", image.index(), "digest", image.digestAt(image.index()), "snapshotIndex", store.snapshotIndex()));
                incoming.abort(); event("BEFORE_SNAPSHOT_INSTALL_ACK", image.index());
                return response(request, type, installedReceipt);
            }
            String action = string(p, "action");
            if (action.equals("ready")) {
                fields(p, "action", "index", "digest");
                require(store.voter() && !store.damagedTail() && store.lastLogIndex() == store.commitIndex()
                        && store.commitIndex() == number(p, "index") && store.digestAt(store.commitIndex()).equals(string(p, "digest")),
                        CONFLICTING_HISTORY, "follower has not reconstructed the required committed boundary");
                try (var rebuilt = application.rebuild(store.image(emptyApplication))) { application.replaceWith(rebuilt); }
                committed = store.commitIndex(); state = ReplicaState.READY; refresh();
                return response(request, "COMMIT_ADVANCE", authorityStatus());
            }
            if (action.equals("floor")) {
                fields(p, "action", "index", "digest", "voters");
                var voters = strings(p, "voters").stream().map(ReplicationNodeId::new).toList();
                store.advanceFloor(number(p, "index"), string(p, "digest"), voters); store.compact(); refresh();
                return response(request, "COMMIT_ADVANCE", authorityStatus());
            }
            if (action.equals("batch")) {
                fields(p, "action", "entries", "proofs");
                require(state == ReplicaState.CATCHING_UP && store.voter(), CONFLICTING_HISTORY, "incremental recovery requires an intact catching-up voter");
                var encoded = strings(p, "entries"); var proofBytes = strings(p, "proofs");
                require(!encoded.isEmpty() && encoded.size() <= bounds.maxEntriesPerAppend() && proofBytes.size() <= encoded.size(), CAPACITY_EXCEEDED, "catch-up batch exceeds bound");
                var old = store.image(emptyApplication); var tail = new ArrayList<>(old.entries()); var proofs = new ArrayList<>(old.proofs());
                for (String value : encoded) {
                    var entry = ReplicaEntry.decode(decodeRecord(binary(Map.of("entry", value), "entry", bounds.maxFrameBytes()), ENTRY, bounds.maxFrameBytes()));
                    if (entry.index() <= store.commitIndex()) require(store.digestAt(entry.index()).equals(frameDigest(entry.encode(bounds.maxFrameBytes()))), CONFLICTING_HISTORY, "conflicting catch-up retry");
                    else tail.add(entry);
                }
                for (String value : proofBytes) {
                    var proof = ReplicaProof.decode(decodeRecord(binary(Map.of("proof", value), "proof", MAX_METADATA_BYTES), PROOF, MAX_METADATA_BYTES));
                    if (proof.index() > store.commitIndex()) proofs.add(proof);
                    else ReplicaSnapshot.validateProof(manifest, proof, proof.index(), old.anchors().get(Math.toIntExact(proof.index() - 1)), old.digestAt(proof.index() - 1));
                }
                if (tail.size() != old.entries().size()) installLocal(new ReplicaRecoveryImage(old.snapshot(), tail, proofs), false);
                event("AFTER_CATCHUP_BATCH", store.commitIndex());
                return response(request, "COMMIT_ADVANCE", authorityStatus());
            }
            throw new ReplicationException(PROTOCOL_MISMATCH, "unknown recovery action");
        } catch (IOException error) { state = ReplicaState.FAILED; refresh(); throw failure(STORAGE_FAILURE, "recovery transfer I/O failure", error); }
        catch (ReplicationException error) { if (error.reason() == STORAGE_FAILURE) { state = ReplicaState.FAILED; refresh(); } throw error; }
    }

    private static List<String> strings(Map<String, Object> p, String key) {
        require(p.get(key) instanceof List<?> list && list.size() <= 100_000 && list.stream().allMatch(String.class::isInstance), PROTOCOL_MISMATCH, "expected bounded string array");
        return ((List<?>) p.get(key)).stream().map(String.class::cast).toList();
    }

    private List<Reply> contact(String type, Map<String, Object> payload, long epoch, UUID incarnation, String expected) {
        var calls = new java.util.LinkedHashMap<ReplicationNodeId, CompletableFuture<Map<String, Object>>>();
        for (var member : manifest.members()) if (!member.nodeId().equals(local))
            calls.put(member.nodeId(), transport.exchange(member.nodeId(), request(member.nodeId(), type, payload, epoch, incarnation)));
        var replies = new ArrayList<Reply>();
        for (var call : calls.entrySet()) {
            try { var response = await(call.getValue()); if (string(response, "type").equals(expected)) replies.add(new Reply(call.getKey(), response, null)); }
            catch (ReplicationException ignored) { }
        }
        return replies;
    }
    private Map<String, Object> rpc(ReplicationNodeId peer, String type, Map<String, Object> values) {
        var reply = await(transport.exchange(peer, request(peer, type, payload(values), activeEpoch, incarnation)));
        if (string(reply, "type").equals("REJECT")) {
            var p = object(reply.get("payload")); fields(p, "reason");
            try { throw new ReplicationException(ReplicationException.Reason.valueOf(string(p, "reason")), "peer rejected recovery " + type); }
            catch (IllegalArgumentException error) { throw failure(PROTOCOL_MISMATCH, "unknown peer rejection", error); }
        }
        require(string(reply, "type").equals(type.equals("AUTHORITY_STATUS_PROBE") ? "AUTHORITY_STATUS" : type.equals("ACTIVATE_EPOCH") ? "ACTIVATION_PROMISE" : type), PROTOCOL_MISMATCH, "unexpected recovery response");
        return object(reply.get("payload"));
    }
    private Map<String, Object> await(CompletableFuture<Map<String, Object>> future) {
        try { return future.get(bounds.requestTimeoutMillis() + 100L, TimeUnit.MILLISECONDS); }
        catch (InterruptedException error) { Thread.currentThread().interrupt(); throw failure(CLOSED, "recovery interrupted", error); }
        catch (Exception error) { Throwable cause = unwrap(error); if (cause instanceof ReplicationException replication) throw replication; throw failure(QUORUM_UNAVAILABLE, "recovery peer unavailable", cause); }
    }
    private ReplicaRecoveryImage download(ReplicationNodeId peer) {
        var offer = rpc(peer, "AUTHORITY_STATUS_PROBE", Map.of("action", "export"));
        fields(offer, "transferId", "length", "digest");
        long length = number(offer, "length"); String id = string(offer, "transferId"), digest = string(offer, "digest");
        require(length > 0 && length <= ReplicaSnapshot.maximum(bounds)
                && (length + ReplicaTransfer.chunkSize(bounds) - 1) / ReplicaTransfer.chunkSize(bounds) <= 100_000, CAPACITY_EXCEEDED, "recovery export exceeds bound");
        byte[] bytes = new byte[(int) length];
        for (int offset = 0; offset < bytes.length;) {
            int count = Math.min(ReplicaTransfer.chunkSize(bounds), bytes.length - offset);
            var chunk = rpc(peer, "AUTHORITY_STATUS_PROBE", Map.of("action", "chunk", "transferId", id, "offset", (long) offset, "length", (long) count));
            fields(chunk, "transferId", "offset", "data");
            require(string(chunk, "transferId").equals(id) && number(chunk, "offset") == offset, PROTOCOL_MISMATCH, "uncorrelated recovery chunk");
            byte[] part = binary(chunk, "data", count); require(part.length == count, INTEGRITY_FAILURE, "short recovery chunk");
            System.arraycopy(part, 0, bytes, offset, count); offset += count;
        }
        require(sha256(bytes).equals(digest), INTEGRITY_FAILURE, "recovery export checksum mismatch");
        return ReplicaRecoveryImage.decode(bytes, manifest, bounds);
    }
    private void upload(ReplicationNodeId peer, ReplicaRecoveryImage image, boolean admit) {
        byte[] bytes = image.encode(bounds); String id = UUID.randomUUID().toString(), digest = sha256(bytes);
        var offer = rpc(peer, "SNAPSHOT_OFFER", Map.of("transferId", id, "length", (long) bytes.length, "digest", digest));
        fields(offer, "transferId"); require(string(offer, "transferId").equals(id), PROTOCOL_MISMATCH, "uncorrelated snapshot offer");
        for (int offset = 0; offset < bytes.length;) {
            int count = Math.min(ReplicaTransfer.chunkSize(bounds), bytes.length - offset);
            var reply = rpc(peer, "SNAPSHOT_CHUNK", Map.of("transferId", id, "offset", (long) offset,
                    "data", Base64.getEncoder().encodeToString(java.util.Arrays.copyOfRange(bytes, offset, offset + count))));
            fields(reply, "transferId", "offset");
            require(string(reply, "transferId").equals(id) && number(reply, "offset") == offset + count, PROTOCOL_MISMATCH, "uncorrelated snapshot chunk ACK"); offset += count;
        }
        var installed = rpc(peer, "SNAPSHOT_INSTALL", Map.of("transferId", id, "admit", admit));
        fields(installed, "transferId", "imageDigest", "index", "digest", "snapshotIndex");
        require(string(installed, "transferId").equals(id) && string(installed, "imageDigest").equals(digest)
                && number(installed, "index") == image.index() && string(installed, "digest").equals(image.digestAt(image.index())), INTEGRITY_FAILURE, "invalid snapshot installation ACK");
    }
    private void installLocal(ReplicaRecoveryImage requested, boolean admit) {
        var image = store.preserveSnapshot(requested);
        try (var rebuilt = application.rebuild(image)) {
            boolean same = store.voter() && !store.damagedTail() && store.lastLogIndex() == image.index()
                    && store.commitIndex() == image.index() && store.snapshotIndex() == image.snapshot().index();
            event("BEFORE_RECOVERY_INSTALL", image.index());
            if (!same) {
                store.install(image, activeEpoch, incarnation, admit);
                if (store.snapshotIndex() <= store.recoveryFloor()) store.compact();
            }
            event("AFTER_RECOVERY_INSTALL", image.index());
            application.replaceWith(rebuilt); committed = store.commitIndex(); refresh();
            event("AFTER_RECOVERY_APPLICATION_PUBLICATION", image.index());
        }
    }
    private void ready(ReplicationNodeId peer, ReplicaRecoveryImage image) {
        var status = rpc(peer, "COMMIT_ADVANCE", Map.of("action", "ready", "index", image.index(), "digest", image.digestAt(image.index())));
        require(number(status, "commitIndex") == image.index() && number(status, "appliedIndex") == image.index()
                && Boolean.TRUE.equals(status.get("voter")), INTEGRITY_FAILURE, "follower READY acknowledgement is invalid");
    }
    private void establishLocalFloor(List<Reply> peers, ReplicaRecoveryImage image) {
        if (store.snapshotIndex() == 0 || store.recoveryFloor() >= store.snapshotIndex() || !store.voter()) return;
        for (var peer : peers) if (number(object(peer.message().get("payload")), "commitIndex") >= store.snapshotIndex()) {
            store.advanceFloor(store.snapshotIndex(), image.digestAt(store.snapshotIndex()), List.of(local, peer.peer())); store.compact(); return;
        }
    }
    private void establishPeerFloor(ReplicationNodeId peer, Map<String, Object> status, ReplicaRecoveryImage image) {
        long index = number(status, "snapshotIndex");
        if (index > 0 && number(status, "recoveryFloor") < index && Boolean.TRUE.equals(status.get("voter")))
            rpc(peer, "COMMIT_ADVANCE", Map.of("action", "floor", "index", index, "digest", image.digestAt(index), "voters", List.of(local.value(), peer.value())));
    }

    CompletableFuture<Long> catchUp(ReplicationNodeId peer) {
        return enqueue(() -> {
            try { return catchUpOrdered(peer); }
            catch (ReplicationException error) { if (error.reason() == CONFLICTING_HISTORY) stopWrites(error); throw error; }
        }, false, 0);
    }
    private long catchUpOrdered(ReplicationNodeId peer) {
            requireLeader(); require(writeReady && !peer.equals(local) && manifest.contains(peer), QUORUM_UNAVAILABLE, "catch-up requires an activated leader and remote voter");
            var status = rpc(peer, "ACTIVATE_EPOCH", Map.of("recovery", true));
            // rpc accepts ACTIVATION_PROMISE as the response to ACTIVATE_EPOCH.
            var image = store.image(emptyApplication); long index = number(status, "commitIndex");
            require(index <= image.index() && image.digestAt(index).equals(string(status, "commitDigest")), CONFLICTING_HISTORY, "catch-up conflicts with peer proof");
            establishPeerFloor(peer, status, image);
            boolean incremental = Boolean.TRUE.equals(status.get("voter")) && !Boolean.TRUE.equals(status.get("damagedTail"))
                    && number(status, "lastLogIndex") == index && index >= store.snapshotIndex();
            if (incremental) {
                while (index < image.index()) {
                    var entries = new ArrayList<String>(); var proofs = new ArrayList<String>(); long end = index;
                    while (end < image.index() && entries.size() < bounds.maxEntriesPerAppend()) {
                        long next = end + 1; var proof = store.proofAt(next);
                        if (proof == null) break;
                        var nextEntries = new ArrayList<>(entries); var nextProofs = new ArrayList<>(proofs);
                        nextEntries.add(Base64.getEncoder().encodeToString(store.entryAt(next).encode(bounds.maxFrameBytes())));
                        nextProofs.add(Base64.getEncoder().encodeToString(proof.encode()));
                        try { ReplicaWire.encode(request(peer, "COMMIT_ADVANCE", payload(Map.of("action", "batch", "entries", nextEntries, "proofs", nextProofs)), activeEpoch, incarnation), bounds.maxFrameBytes()); }
                        catch (ReplicationException error) { if (error.reason() == CAPACITY_EXCEEDED) break; throw error; }
                        entries = nextEntries; proofs = nextProofs; end = next;
                    }
                    if (end == index) { incremental = false; break; }
                    var reply = rpc(peer, "COMMIT_ADVANCE", Map.of("action", "batch", "entries", entries, "proofs", proofs));
                    require(number(reply, "commitIndex") == end && string(reply, "commitDigest").equals(image.digestAt(end)), INTEGRITY_FAILURE, "catch-up batch ACK mismatch"); index = end;
                }
            }
            if (!incremental) upload(peer, checkpointImage(), !Boolean.TRUE.equals(status.get("voter")));
            ready(peer, image);
            var recovered = rpc(peer, "AUTHORITY_STATUS_PROBE", Map.of()); establishPeerFloor(peer, recovered, image);
            return image.index();
    }

    private ReplicaRecoveryImage checkpointImage() {
        require(store.lastLogIndex() == store.commitIndex() && application.appliedIndex() == store.commitIndex(), CONFLICTING_HISTORY, "checkpoint requires resolved committed state");
        var history = store.image(emptyApplication);
        return new ReplicaRecoveryImage(new ReplicaSnapshot(manifest.digest(), history.anchors(), store.proofAt(store.commitIndex()), application.snapshot()), List.of(), List.of());
    }
    CompletableFuture<Long> checkpoint() {
        return enqueue(() -> {
            try { return checkpointOrdered(); }
            catch (RuntimeException error) { stopWrites(error); throw error; }
        }, false, 0);
    }
    private long checkpointOrdered() {
            requireLeader(); require(writeReady, QUORUM_UNAVAILABLE, "checkpoint requires an activated leader");
            var image = checkpointImage(); var installed = new ArrayList<ReplicationNodeId>();
            for (var member : manifest.members()) if (!member.nodeId().equals(local)) {
                try {
                    var status = rpc(member.nodeId(), "ACTIVATE_EPOCH", Map.of("recovery", true));
                    require(Boolean.TRUE.equals(status.get("voter")), CONFLICTING_HISTORY, "checkpoint cannot admit an unreconstructed voter");
                    require(number(status, "commitIndex") <= image.index() && image.digestAt(number(status, "commitIndex")).equals(string(status, "commitDigest")), CONFLICTING_HISTORY, "checkpoint conflicts with peer history");
                    establishPeerFloor(member.nodeId(), status, image); upload(member.nodeId(), image, false); ready(member.nodeId(), image); installed.add(member.nodeId());
                } catch (ReplicationException error) { if (error.reason() != QUORUM_UNAVAILABLE && error.reason() != CAPACITY_EXCEEDED) throw error; }
            }
            require(!installed.isEmpty(), QUORUM_UNAVAILABLE, "checkpoint lacks a second durable recovery source");
            if (store.snapshotIndex() > store.recoveryFloor()) { store.advanceFloor(store.snapshotIndex(), image.digestAt(store.snapshotIndex()), List.of(local, installed.getFirst())); store.compact(); }
            installLocal(image, false);
            store.advanceFloor(image.index(), image.digestAt(image.index()), List.of(local, installed.getFirst())); store.compact(); refresh();
            for (var peer : installed) {
                try { rpc(peer, "COMMIT_ADVANCE", Map.of("action", "floor", "index", image.index(), "digest", image.digestAt(image.index()), "voters", List.of(local.value(), peer.value()))); }
                catch (ReplicationException ignored) { /* A lost floor ACK retains a complete old recovery source. */ }
            }
            event("AFTER_CHECKPOINT_QUORUM", image.index()); return image.index();
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
