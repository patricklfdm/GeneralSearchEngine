package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50PressureHardeningTest {
    @TempDir Path temporary;

    @Test
    void fullWriterQueueIsClassifiedAndCloseResolvesQueuedCancelledAndRunningWork() throws Exception {
        var reached = new CountDownLatch(1); var release = new CountDownLatch(1);
        var bounds = new ReplicationBounds(8192, 2, 1, 2, 1, 1500, 10, 256, 1048576, 1048576);
        var group = new Group(temporary, bounds, (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_ENTRY_QUORUM")) {
                reached.countDown();
                try { release.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
            }
        });
        try {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            var active = group.add(new Document(1, "in flight")); assertTrue(reached.await(5, TimeUnit.SECONDS));
            var queued = group.add(new Document(2, "queued")); assertTrue(queued.cancel(true));
            assertEquals(2, group.leader().status().pendingClientOperations());
            V50LeaderPathTest.rejected(ReplicationException.Reason.CAPACITY_EXCEEDED, group.add(new Document(3, "no slot")));
            var maintenance = new ArrayList<CompletableFuture<Long>>();
            for (int i = 0; i < 4; i++) maintenance.add(group.leader().checkpoint());
            V50LeaderPathTest.rejected(ReplicationException.Reason.CAPACITY_EXCEEDED, group.leader().checkpoint());
            group.leader().close();
            assertTrue(active.isCompletedExceptionally()); assertTrue(queued.isCancelled());
            assertTrue(maintenance.stream().allMatch(CompletableFuture::isCompletedExceptionally));
            assertEquals(0, group.leader().status().pendingClientOperations());
            assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        } finally { release.countDown(); group.close(); }
    }

    @Test
    void aggregateOutboundBytesStayBoundedAndCloseResolvesAdmittedExchanges() throws Exception {
        var manifest = manifest(ports()); var peer = manifest.members().get(1).nodeId();
        var bounds = new ReplicationBounds(8192, 1, 8, 2, 1, 1500, 10, 256, 1048576, 1048576);
        var reached = new CountDownLatch(1);
        try (var server = new ReplicaTransport(manifest, peer, bounds, request -> request);
             var client = new ReplicaTransport(manifest, LEADER, bounds, request -> request, (barrier, request, response) -> {
                 if (barrier.equals("BEFORE_REQUEST_WRITE")) {
                     reached.countDown();
                     try { new CountDownLatch(1).await(); }
                     catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
                 }
             })) {
            var request = ReplicaWire.message(manifest, LEADER, peer, 2, UUID.randomUUID(), "AUTHORITY_STATUS_PROBE",
                    Map.of("manifestDigest", manifest.digest(), "padding", "x".repeat(6500)), UUID.randomUUID(), 1);
            var accepted = new ArrayList<CompletableFuture<Map<String, Object>>>();
            for (int i = 0; i < 4; i++) accepted.add(client.exchange(peer, request));
            assertTrue(reached.await(5, TimeUnit.SECONDS));
            V50LeaderPathTest.rejected(ReplicationException.Reason.CAPACITY_EXCEEDED, client.exchange(peer, request));
            assertTrue(accepted.getFirst().cancel(true));
            V50LeaderPathTest.rejected(ReplicationException.Reason.CAPACITY_EXCEEDED, client.exchange(peer, request));
            client.close(); assertTrue(accepted.stream().allMatch(CompletableFuture::isDone));
        }
    }

    @Test
    void retainedCapacityFailurePreservesCommittedPrefixAndNeverExceedsDiskBound() throws Exception {
        var bounds = new ReplicationBounds(8192, 2, 8, 4, 1, 1500, 10, 256, 12000, 65536);
        var group = new Group(temporary, bounds, ReplicaNode.Events.NONE);
        long successful = 1; boolean full = false;
        try {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            for (int i = 1; i < 10; i++) {
                try { group.add(new Document(i, "x".repeat(2800))).get(10, TimeUnit.SECONDS); successful++; }
                catch (java.util.concurrent.ExecutionException error) {
                    assertInstanceOf(ReplicationException.class, error.getCause());
                    assertTrue(List.of(ReplicationException.Reason.CAPACITY_EXCEEDED, ReplicationException.Reason.QUORUM_UNAVAILABLE)
                            .contains(((ReplicationException) error.getCause()).reason())); full = true; break;
                }
            }
            assertTrue(full); assertTrue(successful > 1);
            assertEquals(successful, group.leader().status().appliedIndex());
            assertFalse(group.leader().status().writeQuorumAvailable());
        } finally { group.close(); }
        int protectedVoters = 0;
        for (var member : group.manifest.members()) {
            var status = ReplicationStorageOperations.inspect(temporary.resolve(member.nodeId().value()));
            assertTrue(status.structurallyValid());
            try (var store = ReplicaStore.open(temporary.resolve(member.nodeId().value()), group.manifest, member.nodeId(), bounds, ReplicaStore.Faults.NONE)) {
                if (store.commitIndex() >= successful) protectedVoters++;
            }
            assertTrue(ReplicaGeneration.directoryBytes(temporary.resolve(member.nodeId().value())) <= bounds.maxRetainedLogBytes());
        }
        assertTrue(protectedVoters >= 2);
    }

    @Test
    void impossibleChunkEnvelopeAndCorruptStagingRejectBeforeAuthorityInstallation() throws Exception {
        var manifest = manifest(ports());
        var tiny = new ReplicationBounds(2048, 1, 1, 1, 1, 1000, 10, 1, 65536, 65536);
        var tinyTransfer = new ReplicaTransfer(temporary, manifest, LEADER, tiny);
        assertEquals(ReplicationException.Reason.CAPACITY_EXCEEDED, assertThrows(ReplicationException.class,
                () -> tinyTransfer.begin(UUID.randomUUID(), 1, ReplicaFormat.sha256(new byte[1]))).reason());
        assertFalse(java.nio.file.Files.exists(temporary.resolve("transfer")));
        var bounds = bounds(1000, 4); var transfer = new ReplicaTransfer(temporary, manifest, LEADER, bounds);
        var id = UUID.randomUUID(); transfer.begin(id, 3, ReplicaFormat.sha256(new byte[]{1, 2, 3}));
        transfer.chunk(id, 0, new byte[]{1, 2, 4}); var corrupted = transfer;
        assertEquals(ReplicationException.Reason.INTEGRITY_FAILURE, assertThrows(ReplicationException.class, () -> corrupted.complete(id)).reason());
        transfer.abort(); assertFalse(java.nio.file.Files.exists(temporary.resolve("transfer")));
    }
}
