package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

class V50RecoveryFormatTest {
    @org.junit.jupiter.api.io.TempDir Path temporary;

    @Test
    void transferBoundsAndIdenticalChunkRetriesPreserveStaging() throws Exception {
        var manifest = ReplicaLeaderTestSupport.manifest(java.util.List.of(21001, 21002, 21003));
        var bounds = new ReplicationBounds(4096, 2, 1, 1, 1, 1000, 10, 8, 65536, 65536);
        var transfer = new ReplicaTransfer(temporary, manifest, ReplicaLeaderTestSupport.LEADER, bounds);
        byte[] bytes = "abcdefghijklmnopqrst".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        var id = java.util.UUID.randomUUID(); transfer.begin(id, bytes.length, sha256(bytes));
        assertEquals(8, transfer.chunk(id, 0, java.util.Arrays.copyOf(bytes, 8)));
        assertEquals(8, transfer.chunk(id, 0, java.util.Arrays.copyOf(bytes, 8)));
        assertThrows(ReplicationException.class, () -> transfer.chunk(id, 0, new byte[8]));
        assertThrows(ReplicationException.class, () -> transfer.chunk(id, 16, java.util.Arrays.copyOfRange(bytes, 16, 20)));
        assertThrows(ReplicationException.class, () -> transfer.complete(id));
        transfer.chunk(id, 8, java.util.Arrays.copyOfRange(bytes, 8, 16));
        transfer.chunk(id, 16, java.util.Arrays.copyOfRange(bytes, 16, 20));
        assertArrayEquals(bytes, transfer.complete(id)); transfer.abort();
        assertThrows(ReplicationException.class, () -> transfer.begin(java.util.UUID.randomUUID(), 65536, sha256(bytes)));
        assertFalse(Files.exists(temporary.resolve(ReplicaTransfer.DIRECTORY)));
    }

    @Test
    void invalidSnapshotBoundFailsBeforeAcquiringTheStoreOwner() {
        var manifest = ReplicaLeaderTestSupport.manifest(java.util.List.of(21001, 21002, 21003));
        var bounds = new ReplicationBounds(4096, 2, 1, 1, 1, 1000, 10, 8, 65536, 1);
        Path directory = temporary.resolve("replica");
        ReplicaStore.initialize(directory, manifest, ReplicaLeaderTestSupport.LEADER, bounds, ReplicaStore.Faults.NONE);
        var application = ReplicaLeaderTestSupport.application(temporary.resolve("application-reserved"), bounds);
        assertThrows(ReplicationException.class, () -> new ReplicaNode<>(directory, manifest, ReplicaLeaderTestSupport.LEADER, bounds, application, ReplicaStore.Faults.NONE, ReplicaNode.Events.NONE));
        try (var store = ReplicaStore.open(directory, manifest, ReplicaLeaderTestSupport.LEADER, bounds, ReplicaStore.Faults.NONE)) { assertEquals(0, store.commitIndex()); }
    }

    @Test
    void independentSnapshotBytesRoundTripAndInspectWithoutAnApplicationCodec() throws Exception {
        Path root = Path.of(getClass().getResource("/replication/v50-recovery-v1/node-2").toURI());
        assertTrue(ReplicationStorageOperations.inspect(root).structurallyValid());
        var manifest = ReplicaManifest.decode(decodeRecord(Files.readAllBytes(root.resolve("manifest.gsr")), MANIFEST, MAX_METADATA_BYTES));
        byte[] bytes = Files.readAllBytes(root.resolve("generation-a/snapshot.gsr"));
        var snapshot = ReplicaSnapshot.decode(bytes, manifest, ReplicaSnapshot.MAX_BYTES);
        assertArrayEquals(bytes, snapshot.encode(ReplicaSnapshot.MAX_BYTES));
        assertEquals(2, snapshot.index()); assertEquals(1, snapshot.sequence());
        assertEquals(2, snapshot.proof().index());
    }

    @Test
    void independentRecoveryFixtureChecksumsRemainExact() throws Exception {
        Path root = Path.of(getClass().getResource("/replication/v50-recovery-v1").toURI());
        Path inventory = Path.of(getClass().getResource("/replication/v50-recovery-v1.sha256").toURI());
        for (String line : Files.readAllLines(inventory)) {
            String[] pair = line.split("  ", 2); assertEquals(pair[0], sha256(Files.readAllBytes(root.resolve(pair[1]))), pair[1]);
        }
    }
}
