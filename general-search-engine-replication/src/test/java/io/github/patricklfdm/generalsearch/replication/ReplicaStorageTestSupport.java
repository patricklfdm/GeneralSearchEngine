package io.github.patricklfdm.generalsearch.replication;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import java.util.stream.IntStream;

final class ReplicaStorageTestSupport {
    static final ReplicationNodeId LEADER = new ReplicationNodeId("node-1");
    static final ReplicationNodeId LOCAL = new ReplicationNodeId("node-2");
    static final UUID INCARNATION = UUID.fromString("22222222-2222-2222-2222-222222222222");
    static final ReplicationBounds BOUNDS = ReplicationBounds.defaults();
    static final ReplicaManifest MANIFEST = new ReplicaManifest(
            new ReplicationGroupId(UUID.fromString("11111111-1111-1111-1111-111111111111")),
            "config-v1", LEADER, IntStream.rangeClosed(1, 3).mapToObj(i -> new ReplicationMember(
            new ReplicationNodeId("node-" + i), new ReplicationEndpoint("10.0.0." + i, 19501))).toList(),
            "fixture-codec", 1, "fixture-schema", 1, ReplicaFormat.sha256(new byte[0]));

    static void initialize(Path directory) {
        ReplicaStore.initialize(directory, MANIFEST, LOCAL, BOUNDS, ReplicaStore.Faults.NONE);
    }

    static ReplicaStore open(Path directory) {
        return ReplicaStore.open(directory, MANIFEST, LOCAL, BOUNDS, ReplicaStore.Faults.NONE);
    }

    static ReplicaEntry next(ReplicaStore store, String operation, String payload) {
        return new ReplicaEntry(MANIFEST.digest(), 2, INCARNATION, store.lastLogIndex() + 1,
                operation, store.lastEntryEpoch(), store.lastLogIndex(), store.lastEntryDigest(),
                payload.getBytes(StandardCharsets.UTF_8));
    }

    static ReplicaProof proof(ReplicaEntry entry) {
        String digest = ReplicaFormat.frameDigest(entry.encode(BOUNDS.maxFrameBytes()));
        return new ReplicaProof(MANIFEST.digest(), entry.epoch(), entry.incarnation(), entry.index(),
                digest, entry.previousDigest(), List.of(
                ReplicaProof.acknowledgement(LEADER, entry, digest),
                ReplicaProof.acknowledgement(LOCAL, entry, digest)));
    }

    static void populate(ReplicaStore store) {
        store.promise(LEADER, 2, INCARNATION);
        store.append(LEADER, next(store, "NO_OP", ""));
        ReplicaEntry second = next(store, "ADD_ALL", "two-documents");
        store.append(LEADER, second);
        store.append(LEADER, next(store, "UPDATE", "uncommitted"));
        store.storeProof(LEADER, proof(second));
    }

    static ReplicationBounds bounds(int frame, long retained) {
        return new ReplicationBounds(frame, BOUNDS.maxEntriesPerAppend(), BOUNDS.maxInFlightPerPeer(),
                BOUNDS.maxPendingClientOperations(), BOUNDS.maxRetryAttempts(), BOUNDS.requestTimeoutMillis(),
                BOUNDS.retryBackoffMillis(), BOUNDS.snapshotChunkBytes(), retained, BOUNDS.maxSnapshotStagingBytes());
    }
}
