package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50PublicLifecycleTest {
    @TempDir Path directory;
    @AfterEach void reset() { ReplicaRuntimeHooks.CURRENT.remove(); }
    private List<ReplicationGroupConfig<Integer, Doc>> bootstrap() {
        var request = request(directory, null);
        ReplicationStorageOperations.applyBootstrap(builder(), request, ReplicationStorageOperations.planBootstrap(builder(), request));
        return request.replicas();
    }
    private void hook(ReplicaNode.Events events) {
        ReplicaRuntimeHooks.CURRENT.set(new ReplicaRuntimeHooks.Hooks(ReplicaStore.Faults.NONE, events, ReplicaTransport.Events.NONE));
    }
    private static void waitFor(CountDownLatch latch) throws java.io.IOException {
        try { if (!latch.await(10, TimeUnit.SECONDS)) throw new java.io.IOException("test latch expired"); }
        catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
    }
    @Test void cancellingStartCopyDoesNotCancelSharedAttemptOrAcquireAnotherOwner() throws Exception {
        var configs = bootstrap(); var entered = new CountDownLatch(1); var release = new CountDownLatch(1); var attempts = new AtomicInteger();
        hook((barrier, index) -> { if (barrier.equals("AFTER_PUBLIC_AUTHORITY_OPEN")) { attempts.incrementAndGet(); entered.countDown(); waitFor(release); } });
        try (var engine = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build()) {
            var cancelled = engine.start(); assertTrue(entered.await(5, TimeUnit.SECONDS));
            var retained = engine.start(); assertTrue(cancelled.cancel(true));
            assertEquals(ReplicaState.STARTING, engine.replicationStatus().state());
            assertTimeoutPreemptively(Duration.ofMillis(200), engine::replicationDiagnostics);
            release.countDown(); assertEquals(ReplicaState.CATCHING_UP, retained.get(5, TimeUnit.SECONDS).state());
            assertEquals(1, attempts.get()); assertEquals(retained.join(), engine.start().join());
        } finally { release.countDown(); }
    }
    @Test void closeDuringStartupPreventsPublicationAndReleasesOwnership() throws Exception {
        var configs = bootstrap(); var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        hook((barrier, index) -> { if (barrier.equals("AFTER_PUBLIC_AUTHORITY_OPEN")) { entered.countDown(); waitFor(release); } });
        var engine = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build();
        var start = engine.start(); assertTrue(entered.await(5, TimeUnit.SECONDS));
        var close = CompletableFuture.runAsync(engine::close);
        try {
            assertThrows(CompletionException.class, () -> start.orTimeout(2, TimeUnit.SECONDS).join());
            release.countDown(); close.get(5, TimeUnit.SECONDS);
            assertEquals(ReplicaState.CLOSED, engine.replicationStatus().state());
        } finally { release.countDown(); engine.close(); }
        ReplicaRuntimeHooks.CURRENT.remove();
        try (var reopened = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build()) {
            assertEquals(ReplicaState.CATCHING_UP, reopened.start().join().state());
        }
    }
    @Test void activationCopiesShareBarrierAndCompletionCallbackCanClose() throws Exception {
        var configs = bootstrap(); var entered = new CountDownLatch(1); var release = new CountDownLatch(1); var attempts = new AtomicInteger();
        hook((barrier, index) -> { if (barrier.equals("AFTER_PROMISE_QUORUM")) { attempts.incrementAndGet(); entered.countDown(); waitFor(release); } });
        try (var leader = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build();
             var follower = ReplicatedSearchEngines.builder(builder(), configs.get(1)).build();
             var third = ReplicatedSearchEngines.builder(builder(), configs.get(2)).build()) {
            for (var node : List.of(leader, follower, third)) node.start().join();
            var cancelled = leader.activateConfiguredLeader(); assertTrue(entered.await(5, TimeUnit.SECONDS));
            var accepted = leader.activateConfiguredLeader(); cancelled.cancel(true);
            assertTimeoutPreemptively(Duration.ofMillis(200), leader::replicationDiagnostics);
            release.countDown(); var active = accepted.get(5, TimeUnit.SECONDS);
            assertEquals(1, attempts.get()); assertEquals(active.activeEpoch(), leader.activateConfiguredLeader().join().activeEpoch());
            leader.add(new Doc(1, "shared")).thenRun(leader::close).get(5, TimeUnit.SECONDS);
            assertEquals(ReplicaState.CLOSED, leader.replicationStatus().state());
        } finally { release.countDown(); }
    }
    @Test void incompleteSealAndChangedGenesisFailBeforePublicAdmission() throws Exception {
        var configs = bootstrap(); Path target = configs.getFirst().replicaDirectory();
        byte[] seal = Files.readAllBytes(target.resolve("bootstrap-seal.gsr")); Files.delete(target.resolve("bootstrap-seal.gsr"));
        try (var engine = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build()) {
            var error = assertThrows(CompletionException.class, () -> engine.start().join());
            assertEquals(ReplicationException.Reason.INTEGRITY_FAILURE, ((ReplicationException) error.getCause()).reason());
        }
        Files.write(target.resolve("bootstrap-seal.gsr"), seal);
        byte[] genesis = Files.readAllBytes(target.resolve("genesis.gsr")); genesis[genesis.length - 1] ^= 1; Files.write(target.resolve("genesis.gsr"), genesis);
        try (var engine = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build()) {
            var error = assertThrows(CompletionException.class, () -> engine.start().join());
            assertEquals(ReplicationException.Reason.INTEGRITY_FAILURE, ((ReplicationException) error.getCause()).reason());
            assertArrayEquals(genesis, Files.readAllBytes(target.resolve("genesis.gsr")));
        }
    }
    @Test void changedCapturedPlannerAndLocalBoundsRejectSealedAuthority() {
        var configs = bootstrap();
        var changed = builder().plannerConfig(io.github.patricklfdm.generalsearch.query.PlannerConfig.DEFAULT);
        try (var engine = ReplicatedSearchEngines.builder(changed, configs.getFirst()).build()) {
            var error = assertThrows(CompletionException.class, () -> engine.start().join());
            assertEquals(ReplicationException.Reason.PROTOCOL_MISMATCH, ((ReplicationException) error.getCause()).reason());
        }
    }

    @Test void cancelledPublishedBackupRetainsQueueSlotUntilSettledAndNeverDeletesOutput() throws Exception {
        var original = configurations(directory); var b = original.getFirst().bounds();
        var bounds = new ReplicationBounds(b.maxFrameBytes(), b.maxEntriesPerAppend(), b.maxInFlightPerPeer(), 1,
                b.maxRetryAttempts(), b.requestTimeoutMillis(), b.retryBackoffMillis(), b.snapshotChunkBytes(), b.maxRetainedLogBytes(), b.maxSnapshotStagingBytes());
        var configs = original.stream().map(c -> new ReplicationGroupConfig<>(c.groupId(), c.configurationId(), c.localNodeId(),
                c.configuredLeaderId(), c.members(), c.replicaDirectory(), c.materialization(), bounds)).toList();
        var request = new ReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY, null, configs, directory.resolve("operation"), 1 << 20, 1 << 20);
        ReplicationStorageOperations.applyBootstrap(builder(), request, ReplicationStorageOperations.planBootstrap(builder(), request));
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        hook((barrier, index) -> { if (barrier.equals("AFTER_PUBLIC_BACKUP")) { entered.countDown(); waitFor(release); } });
        try (var leader = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build();
             var follower = ReplicatedSearchEngines.builder(builder(), configs.get(1)).build();
             var third = ReplicatedSearchEngines.builder(builder(), configs.get(2)).build()) {
            for (var node : List.of(leader, follower, third)) node.start().join();
            leader.activateConfiguredLeader().join(); leader.add(new Doc(1, "shared")).join();
            Path target = directory.resolve("backup");
            var backup = leader.backup(new io.github.patricklfdm.generalsearch.durability.DurableBackupRequest(target, 1 << 20));
            assertTrue(entered.await(5, TimeUnit.SECONDS)); assertTrue(backup.cancel(true));
            assertTrue(Files.isDirectory(target)); assertEquals(1, leader.replicationStatus().pendingClientOperations());
            var refused = assertThrows(CompletionException.class, () -> leader.add(new Doc(2, "no admission")).join());
            assertEquals(ReplicationException.Reason.CAPACITY_EXCEEDED, ((ReplicationException) refused.getCause()).reason());
            release.countDown();
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
            while (leader.replicationStatus().pendingClientOperations() != 0 && System.nanoTime() < deadline) Thread.sleep(2);
            assertEquals(0, leader.replicationStatus().pendingClientOperations());
            var exported = builder().readDurableBackup(target, new io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig<>(
                    "fixture-store", "fixture-schema", new Codec(), 1, 1024, 65536, 10000), 1 << 20);
            assertEquals(1, exported.sequence()); assertEquals(List.of(new Doc(1, "shared")), exported.documents());
        } finally { release.countDown(); }
    }

    @Test void diagnosticsCoalescePerPeerAndDoNotRefreshQuorumEvidence() throws Exception {
        var configs = bootstrap(); var probes = new AtomicInteger();
        ReplicaRuntimeHooks.CURRENT.set(new ReplicaRuntimeHooks.Hooks(ReplicaStore.Faults.NONE, ReplicaNode.Events.NONE,
                (barrier, request, response) -> {
                    if (barrier.equals("BEFORE_REQUEST_WRITE") && request.get("sender").equals("node-1")
                            && request.get("type").equals("AUTHORITY_STATUS_PROBE")) probes.incrementAndGet();
                }));
        try (var leader = ReplicatedSearchEngines.builder(builder(), configs.getFirst()).build();
             var follower = ReplicatedSearchEngines.builder(builder(), configs.get(1)).build();
             var third = ReplicatedSearchEngines.builder(builder(), configs.get(2)).build()) {
            for (var node : List.of(leader, follower, third)) node.start().join();
            leader.activateConfiguredLeader().join(); probes.set(0);
            var first = leader.replicationDiagnostics();
            for (int i = 0; i < 1000; i++) leader.replicationDiagnostics();
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
            while (probes.get() < 2 && System.nanoTime() < deadline) Thread.sleep(2);
            assertEquals(2, probes.get());
            var last = leader.replicationDiagnostics(); assertEquals(first.lastQuorumSuccess(), last.lastQuorumSuccess());
            assertEquals(List.of(new ReplicationNodeId("node-2"), new ReplicationNodeId("node-3")), last.peers().stream().map(ReplicationPeerStatus::nodeId).toList());
            assertTrue(last.peers().stream().allMatch(peer -> peer.matchIndex() <= peer.durableIndex() && peer.appliedIndex() <= peer.durableIndex()));
        }
    }
}
