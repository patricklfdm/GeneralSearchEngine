package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.CopyOnWriteArrayList;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50LeaderPathTest {
    @TempDir Path temporary;

    @Test
    void zeroEpochHandshakeIsReadOnlyAndUnactivatedAppendRejects() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().close();
            var peer = group.manifest.members().get(1).nodeId();
            var follower = group.nodes.get(1);
            var before = follower.status();
            try (var client = new ReplicaTransport(group.manifest, LEADER, BOUNDS, request -> request)) {
                for (String type : List.of("HANDSHAKE", "AUTHORITY_STATUS_PROBE", "APPEND")) {
                    var request = ReplicaWire.message(group.manifest, LEADER, peer, type.equals("HANDSHAKE") ? 0 : 2,
                            ReplicaFormat.NO_INCARNATION, type, java.util.Map.of("manifestDigest", group.manifest.digest()),
                            java.util.UUID.randomUUID(), 1);
                    var response = client.exchange(peer, request).get(5, TimeUnit.SECONDS);
                    String expected = type.equals("HANDSHAKE") ? "HANDSHAKE"
                            : type.equals("AUTHORITY_STATUS_PROBE") ? "AUTHORITY_STATUS" : "REJECT";
                    assertEquals(expected, response.get("type"));
                    if (type.equals("APPEND")) assertEquals("STALE_EPOCH",
                            ReplicaWire.object(response.get("payload")).get("reason"));
                }
            }
            assertEquals(before, follower.status());
        }
    }

    @Test
    void activationAndApplicationRequireTwoDistinctDurableQuorums() throws Exception {
        var events = new CopyOnWriteArrayList<String>();
        try (var group = new Group(temporary, BOUNDS, (barrier, index) -> events.add(index + ":" + barrier))) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            assertEquals(1, group.leader().status().lastLogIndex());
            assertEquals(0, group.leader().status().applicationSequence());
            group.add(new Document(1, "one")).get(10, TimeUnit.SECONDS);
            assertEquals(new Document(1, "one"), group.leader().read(engine -> engine.get(1)));
            var status = group.leader().status();
            assertEquals(2, status.appliedIndex()); assertEquals(2, status.commitIndex());
            assertEquals(1, status.applicationSequence());
            int cursor = -1;
            for (String barrier : List.of("AFTER_LOCAL_ENTRY_FORCE", "AFTER_ENTRY_QUORUM", "AFTER_LOCAL_PROOF_FORCE",
                    "AFTER_PROOF_QUORUM", "BEFORE_APPLICATION_PUBLICATION", "AFTER_APPLICATION_PUBLICATION", "BEFORE_CLIENT_SUCCESS")) {
                int next = events.indexOf("2:" + barrier);
                assertTrue(next > cursor, barrier); cursor = next;
            }
            await(() -> group.nodes.get(1).status().appliedIndex() == 2 && group.nodes.get(2).status().appliedIndex() == 2);
            for (int i = 1; i < 3; i++) {
                var follower = group.nodes.get(i);
                assertEquals(ReplicationException.Reason.NOT_CONFIGURED_LEADER,
                        assertThrows(ReplicationException.class, () -> follower.read(engine -> engine.get(1))).reason());
                rejected(ReplicationException.Reason.NOT_CONFIGURED_LEADER, follower.submit("ADD", new byte[0]));
                rejected(ReplicationException.Reason.NOT_CONFIGURED_LEADER, follower.activate());
            }
        }
    }

    @Test
    void oneFollowerLossCommitsAndTwoFollowerLossKeepsLastPublishedState() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            group.add(new Document(1, "one")).get(10, TimeUnit.SECONDS);
            await(() -> group.nodes.get(1).status().appliedIndex() == 2 && group.nodes.get(2).status().appliedIndex() == 2);
            group.nodes.get(2).close();
            group.add(new Document(2, "two")).get(10, TimeUnit.SECONDS);
            group.nodes.get(1).close();
            rejected(ReplicationException.Reason.QUORUM_UNAVAILABLE, group.add(new Document(3, "hidden")));
            assertNull(group.leader().read(engine -> engine.get(3)));
            assertEquals(new Document(2, "two"), group.leader().read(engine -> engine.get(2)));
            assertFalse(group.leader().status().writeQuorumAvailable());
            assertEquals(2, group.leader().status().applicationSequence());
            rejected(ReplicationException.Reason.QUORUM_UNAVAILABLE, group.add(new Document(4, "rejected")));
        }
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings = {"AFTER_ENTRY_QUORUM", "AFTER_LOCAL_PROOF_FORCE", "AFTER_PROOF_QUORUM", "BEFORE_APPLICATION_PUBLICATION"})
    void publicationAndSuccessfulFutureWaitForProofQuorum(String stopAt) throws Exception {
        var reached = new CountDownLatch(1); var release = new CountDownLatch(1);
        try (var group = new Group(temporary, BOUNDS, (barrier, index) -> {
            if (index == 2 && barrier.equals(stopAt)) {
                reached.countDown();
                try { if (!release.await(5, TimeUnit.SECONDS)) throw new java.io.IOException("barrier timed out"); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new java.io.IOException(error); }
            }
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            var future = group.add(new Document(1, "one"));
            assertTrue(reached.await(5, TimeUnit.SECONDS));
            assertFalse(future.isDone()); assertNull(group.leader().read(engine -> engine.get(1)));
            assertEquals(0, group.leader().status().applicationSequence());
            release.countDown(); future.get(10, TimeUnit.SECONDS);
            assertNotNull(group.leader().read(engine -> engine.get(1)));
        } finally { release.countDown(); }
    }

    @Test
    void entryQuorumWithoutProofQuorumCannotPublishOrCompleteSuccessfully() throws Exception {
        var reference = new java.util.concurrent.atomic.AtomicReference<Group>();
        try (var group = new Group(temporary, BOUNDS, (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_ENTRY_QUORUM")) {
                reference.get().nodes.get(1).close(); reference.get().nodes.get(2).close();
            }
        })) {
            reference.set(group);
            group.leader().activate().get();
            rejected(ReplicationException.Reason.QUORUM_UNAVAILABLE, group.add(new Document(1, "must remain private")));
            assertEquals(1, group.leader().status().appliedIndex());
            assertNull(group.leader().read(engine -> engine.get(1)));
            assertEquals(0, group.leader().status().applicationSequence());
        }
    }

    @Test
    void validationAndBulkFailureDoNotAppendOrPublishPartialDocuments() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            group.add(new Document(1, "one")).get(10, TimeUnit.SECONDS);
            var app = group.applications.getFirst();
            var before = group.leader().status();
            var rejected = group.leader().submit("ADD_ALL", app.documents("ADD_ALL", List.of(new Document(2, "two"), new Document(1, "duplicate"))));
            assertThrows(java.util.concurrent.ExecutionException.class, () -> rejected.get(5, TimeUnit.SECONDS));
            assertEquals(before.lastLogIndex(), group.leader().status().lastLogIndex());
            assertNull(group.leader().read(engine -> engine.get(2)));
            group.leader().submit("ADD_ALL", app.documents("ADD_ALL", List.of(new Document(2, "two"), new Document(3, "three")))).get(10, TimeUnit.SECONDS);
            assertEquals(before.lastLogIndex() + 1, group.leader().status().lastLogIndex());
            assertEquals(2, group.leader().status().applicationSequence());
            assertNotNull(group.leader().read(engine -> engine.get(3)));
        }
    }

    @Test
    void cancellationDoesNotRetractAcceptedEntryAndQueueAdmissionIsBounded() throws Exception {
        var reached = new CountDownLatch(1); var release = new CountDownLatch(1);
        try (var group = new Group(temporary, bounds(1200, 1), (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_ENTRY_QUORUM")) {
                reached.countDown();
                try { release.await(5, TimeUnit.SECONDS); }
                catch (InterruptedException error) { throw new java.io.IOException(error); }
            }
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            var accepted = group.add(new Document(1, "committed despite cancellation"));
            assertTrue(reached.await(5, TimeUnit.SECONDS));
            assertTrue(accepted.cancel(true));
            rejected(ReplicationException.Reason.CAPACITY_EXCEEDED, group.add(new Document(2, "no slot")));
            release.countDown();
            await(() -> group.leader().status().applicationSequence() == 1);
            assertNotNull(group.leader().read(engine -> engine.get(1)));
            assertTrue(accepted.isCancelled());
        } finally { release.countDown(); }
    }

    static void await(java.util.function.BooleanSupplier condition) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(8);
        while (!condition.getAsBoolean()) {
            assertTrue(System.nanoTime() < deadline, "condition did not become true");
            Thread.sleep(10);
        }
    }

    @Test
    void updatesRemovalsAndIndexLifecycleUseOneOrderedApplicationSequence() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            var app = group.applications.getFirst();
            group.leader().submit("ADD_ALL", app.documents("ADD_ALL", List.of(new Document(1, "one"), new Document(2, "two")))).get();
            group.leader().submit("UPDATE_ALL", app.documents("UPDATE_ALL", List.of(new Document(1, "updated"), new Document(2, "second")))).get();
            group.leader().submit("INDEX_DROP", app.dropIndex("value")).get();
            group.leader().submit("INDEX_CREATE", app.index(io.github.patricklfdm.generalsearch.index.IndexDefinition.prefix(VALUE))).get();
            group.leader().submit("REMOVE_ALL", app.keys("REMOVE_ALL", List.of(2))).get();
            assertEquals(5, group.leader().status().applicationSequence());
            assertEquals(6, group.leader().status().appliedIndex());
            assertEquals(new Document(1, "updated"), group.leader().read(engine -> engine.get(1)));
            assertNull(group.leader().read(engine -> engine.get(2)));
        }
    }

    @Test
    void retiredReaderCannotObserveNextUncommittedPreparation() throws Exception {
        var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        try (var group = new Group(temporary, bounds(3000, 8), ReplicaNode.Events.NONE)) {
            group.leader().activate().get(); group.add(new Document(1, "one")).get();
            var oldRead = CompletableFuture.supplyAsync(() -> group.leader().read(engine -> {
                entered.countDown();
                try { release.await(5, TimeUnit.SECONDS); }
                catch (InterruptedException error) { throw new AssertionError(error); }
                return engine.get(2);
            }));
            assertTrue(entered.await(5, TimeUnit.SECONDS));
            group.add(new Document(2, "two")).get();
            var third = group.add(new Document(3, "three"));
            assertEquals(3, group.leader().status().lastLogIndex());
            assertFalse(third.isDone());
            assertNull(group.leader().read(engine -> engine.get(3)));
            release.countDown(); assertNull(oldRead.get()); third.get();
            assertNotNull(group.leader().read(engine -> engine.get(3)));
        } finally { release.countDown(); }
    }

    @Test
    void matchedCommittedRestartUsesHigherEpochAndPreservesApplicationSequence() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(); group.add(new Document(1, "retained")).get();
            await(() -> group.nodes.get(1).status().appliedIndex() == 2 && group.nodes.get(2).status().appliedIndex() == 2);
            group.leader().close();
            var app = application(temporary.resolve("reopened-app"), BOUNDS);
            try (var reopened = new ReplicaNode<>(temporary.resolve("node-1"), group.manifest, LEADER, BOUNDS,
                    app, ReplicaStore.Faults.NONE, ReplicaNode.Events.NONE)) {
                assertThrows(ReplicationException.class, () -> reopened.read(engine -> engine.get(1)));
                reopened.activate().get();
                assertEquals(3, reopened.status().activeEpoch());
                assertEquals(3, reopened.status().appliedIndex());
                assertEquals(1, reopened.status().applicationSequence());
                assertEquals(new Document(1, "retained"), reopened.read(engine -> engine.get(1)));
            }
        }
    }

    @Test
    void closeFromCompletionCallbackReleasesOwnershipWithoutDeadlock() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get();
            group.add(new Document(1, "one")).thenRun(group.leader()::close).get(10, TimeUnit.SECONDS);
            assertEquals(ReplicaState.CLOSED, group.leader().status().state());
            assertEquals(0, group.leader().status().pendingClientOperations());
            assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        }
    }
    static void rejected(ReplicationException.Reason reason, CompletableFuture<?> future) {
        var error = assertThrows(java.util.concurrent.ExecutionException.class, () -> future.get(10, TimeUnit.SECONDS));
        assertInstanceOf(ReplicationException.class, error.getCause());
        assertEquals(reason, ((ReplicationException) error.getCause()).reason());
    }
}
