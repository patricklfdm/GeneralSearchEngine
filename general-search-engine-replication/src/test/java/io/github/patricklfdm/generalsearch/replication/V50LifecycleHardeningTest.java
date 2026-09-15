package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50LifecycleHardeningTest {
    @TempDir Path temporary;

    @Test
    void interruptedCloseCanBeRetriedAndReleasesStorageOwnership() throws Exception {
        try (var group = new Group(temporary, bounds(500, 4), ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            Thread.currentThread().interrupt();
            try { assertThrows(ReplicationException.class, group.leader()::close); }
            finally { assertTrue(Thread.interrupted(), "close must preserve caller interruption"); }
            assertFalse(group.leader().status().writeQuorumAvailable());
            assertEquals(ReplicaState.UNAVAILABLE, group.leader().status().state());
            group.leader().close();
            assertEquals(ReplicaState.CLOSED, group.leader().status().state());
            assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        }
    }

    @Test
    void timedOutCloseKeepsOwnerUntilWriterStopsThenRetryCompletes() throws Exception {
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        var group = new Group(temporary, bounds(500, 4), (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_LOCAL_ENTRY_FORCE")) {
                entered.countDown();
                boolean interrupted = false;
                while (release.getCount() != 0) {
                    try { release.await(); }
                    catch (InterruptedException error) { interrupted = true; }
                }
                if (interrupted) Thread.currentThread().interrupt();
            }
        });
        try {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            var mutation = group.add(new Document(1, "indeterminate"));
            assertTrue(entered.await(5, TimeUnit.SECONDS));
            assertThrows(ReplicationException.class, group.leader()::close);
            assertTrue(mutation.isCompletedExceptionally());
            assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.inspect(temporary.resolve("node-1")));
            release.countDown(); group.leader().close();
            assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        } finally { release.countDown(); group.close(); }
    }

    @Test
    void closeDoesNotInterruptAProofRecordHalfwayThroughItsWrite() throws Exception {
        var armed = new java.util.concurrent.atomic.AtomicBoolean();
        var reached = new CountDownLatch(1); var release = new CountDownLatch(1);
        var interruptedInsideRecord = new java.util.concurrent.atomic.AtomicBoolean();
        try (var group = new Group(temporary, bounds(2000, 4), ReplicaNode.Events.NONE)) {
            group.leader().close();
            var app = application(temporary.resolve("replacement-app"), group.bounds);
            var faults = new ReplicaStore.Faults() {
                public int maxWriteBytes() { return 1; }
                public void at(String barrier) throws java.io.IOException {
                    if (armed.get() && barrier.equals("AFTER_PROOF_WRITE_CHUNK") && reached.getCount() != 0) {
                        reached.countDown();
                        try { release.await(10, TimeUnit.SECONDS); }
                        catch (InterruptedException error) { interruptedInsideRecord.set(true); throw new java.io.IOException(error); }
                    }
                }
            };
            var leader = new ReplicaNode<>(temporary.resolve("node-1"), group.manifest, LEADER, group.bounds, app, faults, ReplicaNode.Events.NONE);
            group.nodes.set(0, leader); group.applications.set(0, app);
            leader.activate().get(10, TimeUnit.SECONDS); armed.set(true);
            var mutation = group.add(new Document(1, "indeterminate"));
            assertTrue(reached.await(5, TimeUnit.SECONDS));
            var closerThread = new java.util.concurrent.atomic.AtomicReference<Thread>();
            var closer = CompletableFuture.runAsync(() -> { closerThread.set(Thread.currentThread()); leader.close(); });
            V50LeaderPathTest.await(() -> !leader.status().writeQuorumAvailable());
            V50LeaderPathTest.await(() -> closer.isDone() || closerThread.get().getState() == Thread.State.BLOCKED);
            release.countDown(); closer.get(10, TimeUnit.SECONDS);
            assertTrue(mutation.isDone()); assertFalse(interruptedInsideRecord.get());
            assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        } finally { release.countDown(); }
    }

    @Test
    void concurrentCloseAndCompletionCallbackShareOneSafeShutdown() throws Exception {
        var reached = new CountDownLatch(1); var release = new CountDownLatch(1);
        try (var group = new Group(temporary, bounds(1000, 4), (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_ENTRY_QUORUM")) {
                reached.countDown();
                try { release.await(5, TimeUnit.SECONDS); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
            }
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            var pending = group.add(new Document(1, "uncertain"));
            assertTrue(reached.await(5, TimeUnit.SECONDS));
            var callback = pending.handle((value, error) -> { group.leader().close(); return true; });
            var closers = java.util.stream.IntStream.range(0, 4)
                    .mapToObj(ignored -> CompletableFuture.runAsync(group.leader()::close)).toArray(CompletableFuture[]::new);
            CompletableFuture.allOf(closers).get(10, TimeUnit.SECONDS);
            assertTrue(callback.get(5, TimeUnit.SECONDS));
            assertEquals(ReplicaState.CLOSED, group.leader().status().state());
            assertEquals(0, group.leader().status().pendingClientOperations());
            assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        } finally { release.countDown(); }
    }

    @Test
    void checkpointReplacementPreservesAnAlreadyLeasedReaderView() throws Exception {
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        try (var group = new Group(temporary, bounds(2000, 4), ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); group.add(new Document(1, "original")).get(10, TimeUnit.SECONDS);
            var read = CompletableFuture.supplyAsync(() -> group.leader().read(engine -> {
                entered.countDown();
                try { release.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException error) { throw new AssertionError(error); }
                return engine.get(1);
            }));
            assertTrue(entered.await(5, TimeUnit.SECONDS));
            group.leader().checkpoint().get(10, TimeUnit.SECONDS);
            group.leader().submit("UPDATE", group.applications.getFirst().documents("UPDATE", java.util.List.of(new Document(1, "new")))).get(10, TimeUnit.SECONDS);
            release.countDown();
            assertEquals(new Document(1, "original"), read.get(5, TimeUnit.SECONDS));
            assertEquals(new Document(1, "new"), group.leader().read(engine -> engine.get(1)));
        } finally { release.countDown(); }
    }

    @Test
    void transportCanCloseInsideItsCompletionCallback() throws Exception {
        var manifest = manifest(ports()); var peer = manifest.members().get(1).nodeId();
        var bounds = bounds(500, 4);
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        try (var server = new ReplicaTransport(manifest, peer, bounds, request -> {
            entered.countDown();
            try { release.await(5, TimeUnit.SECONDS); }
            catch (InterruptedException error) { throw new RuntimeException(error); }
            var reply = new java.util.TreeMap<>(request);
            reply.put("sender", peer.value()); reply.put("recipient", LEADER.value()); return reply;
        }); var client = new ReplicaTransport(manifest, LEADER, bounds, request -> request)) {
            var request = ReplicaWire.message(manifest, LEADER, peer, 2, UUID.randomUUID(), "AUTHORITY_STATUS_PROBE",
                    Map.of("manifestDigest", manifest.digest()), UUID.randomUUID(), 1);
            // Queue the exchange only after attaching the callback to avoid caller-thread completion.
            var start = new CompletableFuture<Void>();
            var finished = start.thenCompose(ignored -> client.exchange(peer, request)).thenRun(client::close);
            start.complete(null); assertTrue(entered.await(5, TimeUnit.SECONDS));
            release.countDown(); finished.get(5, TimeUnit.SECONDS);
            V50LeaderPathTest.rejected(ReplicationException.Reason.CLOSED, client.exchange(peer, request));
        }
    }
}
