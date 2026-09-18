package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.V50LeaderPathTest.await;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class V50ReadyTest {
    @TempDir Path temporary;

    /** Count actual replay work without relying on machine speed or a sleep. */
    private static final class CountingCodec implements DurableCodec<Integer, Document> {
        private final Codec delegate = new Codec();
        final AtomicInteger decodes = new AtomicInteger();
        public String codecId() { return delegate.codecId(); }
        public int codecVersion() { return delegate.codecVersion(); }
        public byte[] encodeKey(Integer key) { return delegate.encodeKey(key); }
        public Integer decodeKey(byte[] bytes) { return delegate.decodeKey(bytes); }
        public byte[] encodeDocument(Document document) { return delegate.encodeDocument(document); }
        public Document decodeDocument(byte[] bytes) {
            decodes.incrementAndGet();
            return delegate.decodeDocument(bytes);
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"restart", "incremental", "snapshot"})
    void readyAndRetriesReuseTheReconstructedApplication(String recovery) throws Exception {
        var holdResponse = new AtomicBoolean();
        var responseHeld = new CountDownLatch(1); var releaseResponse = new CountDownLatch(1);
        var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE, local -> (barrier, request, response) -> {
            if (local == 0 && barrier.equals("AFTER_RESPONSE_READ") && request.get("recipient").equals("node-3")
                    && request.get("type").equals("COMMIT_PROOF")
                    && Long.valueOf(2).equals(ReplicaWire.object(response.get("payload")).get("index"))
                    && holdResponse.compareAndSet(true, false)) {
                responseHeld.countDown();
                try {
                    if (!releaseResponse.await(10, TimeUnit.SECONDS)) throw new java.io.IOException("response release missing");
                } catch (InterruptedException error) {
                    Thread.currentThread().interrupt(); throw new java.io.IOException(error);
                }
            }
        });
        try {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            // Hold the sender before it releases its slot, then fill its queue while the
            // other follower supplies quorum. This forces the CI admission race locally.
            holdResponse.set(recovery.equals("incremental"));
            group.add(new Document(1, "before isolation")).get(10, TimeUnit.SECONDS);
            if (recovery.equals("incremental")) assertTrue(responseHeld.await(5, TimeUnit.SECONDS));
            await(() -> group.nodes.get(2).status().appliedIndex() == 2);
            group.nodes.get(2).close();
            if (!recovery.equals("restart")) {
                for (int i = 0; i < 20; i++) group.leader().submit("UPDATE",
                        group.applications.getFirst().documents("UPDATE", List.of(new Document(1, "update-" + i))))
                        .get(10, TimeUnit.SECONDS);
            }
            if (recovery.equals("snapshot")) group.leader().checkpoint().get(10, TimeUnit.SECONDS);

            var codec = new CountingCodec();
            var config = DurableStorageConfig.builder(temporary.resolve("restarted-app"), codec)
                    .storageIdentity("fixture-storage").schemaIdentity("fixture-schema")
                    .maxDocuments(1000).maxBulkElements(100).build();
            var app = new ReplicaApplication<>(SCHEMA, INDEXES, config, BOUNDS);
            var peer = group.manifest.members().get(2).nodeId();
            var installedDecodes = new AtomicInteger();
            group.applications.set(2, app);
            group.nodes.set(2, new ReplicaNode<>(temporary.resolve(peer.value()), group.manifest, peer,
                    BOUNDS, app, ReplicaStore.Faults.NONE, (barrier, index) -> {
                        if (barrier.equals("AFTER_RECOVERY_APPLICATION_PUBLICATION")) installedDecodes.set(codec.decodes.get());
                    }));
            installedDecodes.set(codec.decodes.get());
            long committed = group.leader().status().commitIndex();
            var backpressure = new AtomicInteger();
            for (int retry = 0; retry < 3; retry++) {
                assertEquals(committed, catchUpWhenAdmitted(group, peer, () -> {
                    backpressure.incrementAndGet(); releaseResponse.countDown();
                }));
                assertEquals(ReplicaState.READY, group.nodes.get(2).status().state());
                assertEquals(committed, app.appliedIndex());
                assertEquals(group.leader().status().applicationSequence(), app.sequence());
                assertEquals(group.leader().<Document>read(engine -> engine.get(1)), app.read(engine -> engine.get(1)));
                assertEquals(installedDecodes.get(), codec.decodes.get(), "READY must not replay an already published history");
            }
            if (recovery.equals("incremental")) assertTrue(backpressure.get() > 0, "fixture must exercise admission backpressure");
            // The reused private working state must support the next real quorum write.
            group.nodes.get(1).close();
            group.add(new Document(2, "new quorum")).get(10, TimeUnit.SECONDS);
            assertEquals(new Document(2, "new quorum"), app.read(engine -> engine.get(2)));
        } finally { releaseResponse.countDown(); group.close(); }
    }

    private static long catchUpWhenAdmitted(Group group, ReplicationNodeId peer, Runnable onBackpressure) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (true) {
            long remaining = deadline - System.nanoTime();
            assertTrue(remaining > 0, "catch-up admission did not recover within the test deadline");
            try { return group.leader().catchUp(peer).get(remaining, TimeUnit.NANOSECONDS); }
            catch (ExecutionException error) {
                // Quorum completion does not drain the unavailable peer's asynchronous
                // requests. Only admission backpressure is expected here; READY, replay,
                // timeout and integrity failures must still fail this regression.
                if (!(error.getCause() instanceof ReplicationException failure)
                        || failure.reason() != ReplicationException.Reason.CAPACITY_EXCEEDED) throw error;
                onBackpressure.run();
                Thread.sleep(10);
            }
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"published", "private", "missing"})
    void incrementalCatchupReplaysOnlyTheMissingTailOfAPublishedPrefix(String materialization) throws Exception {
        var isolated = new AtomicBoolean();
        int history = materialization.equals("published") ? 300 : 20;
        long prefix = history + 2, target = prefix + 10;
        var defaults = BOUNDS;
        var bounds = new ReplicationBounds(defaults.maxFrameBytes(), 4, defaults.maxInFlightPerPeer(),
                defaults.maxPendingClientOperations(), defaults.maxRetryAttempts(), defaults.requestTimeoutMillis(),
                defaults.retryBackoffMillis(), defaults.snapshotChunkBytes(), defaults.maxRetainedLogBytes(), defaults.maxSnapshotStagingBytes());
        try (var group = new Group(temporary, bounds, ReplicaNode.Events.NONE, local -> (barrier, request, response) -> {
            if (local == 0 && isolated.get() && barrier.equals("BEFORE_REQUEST_WRITE")
                    && request.get("recipient").equals("node-3")) throw new java.io.IOException("isolated follower");
        })) {
            group.nodes.get(2).close();
            var codec = new CountingCodec();
            var config = DurableStorageConfig.builder(temporary.resolve("counted-app"), codec)
                    .storageIdentity("fixture-storage").schemaIdentity("fixture-schema")
                    .maxDocuments(1000).maxBulkElements(100).build();
            var app = new ReplicaApplication<>(SCHEMA, INDEXES, config, bounds);
            var peer = group.manifest.members().get(2).nodeId();
            var installs = new AtomicInteger();
            group.applications.set(2, app);
            group.nodes.set(2, new ReplicaNode<>(temporary.resolve(peer.value()), group.manifest, peer, bounds, app,
                    ReplicaStore.Faults.NONE, (barrier, index) -> {
                        if (barrier.equals("AFTER_RECOVERY_INSTALL") && index > prefix) {
                            // The new authority is durable, but the rebuilt batch is still private.
                            assertTrue(app.appliedIndex() < index);
                            assertNotEquals(new Document(1, "update-" + (index - 3)), app.read(engine -> engine.get(1)));
                            installs.incrementAndGet();
                        }
                    }));
            group.leader().activate().get(10, TimeUnit.SECONDS);
            group.add(new Document(1, "initial")).get(10, TimeUnit.SECONDS);
            for (int i = 0; i < history; i++) group.leader().submit("UPDATE",
                    group.applications.getFirst().documents("UPDATE", List.of(new Document(1, "update-" + i))))
                    .get(10, TimeUnit.SECONDS);
            await(() -> app.appliedIndex() == prefix);
            isolated.set(true);
            for (int i = history; i < history + 10; i++) group.leader().submit("UPDATE",
                    group.applications.getFirst().documents("UPDATE", List.of(new Document(1, "update-" + i))))
                    .get(10, TimeUnit.SECONDS);
            assertEquals(prefix, app.appliedIndex());
            if (materialization.equals("private")) {
                app.prepare(new ReplicaEntry(group.manifest.digest(), group.leader().status().activeEpoch(), java.util.UUID.randomUUID(),
                        prefix + 1, "ADD", group.leader().status().activeEpoch(), prefix, "0".repeat(64),
                        app.documents("ADD", List.of(new Document(99, "uncommitted")))));
            } else if (materialization.equals("missing")) {
                try (var empty = application(temporary.resolve("empty-materialization"), bounds)) { app.replaceWith(empty); }
            }
            codec.decodes.set(0);
            isolated.set(false);
            assertEquals(target, catchUpWhenAdmitted(group, peer, () -> { }));
            assertEquals(3, installs.get(), "ten missing entries require three bounded batches");
            if (materialization.equals("published")) assertTrue(codec.decodes.get() < 64,
                    "catch-up replayed the existing 300 updates: " + codec.decodes.get());
            else assertTrue(codec.decodes.get() >= history, "unsafe or missing state must rebuild from durable authority");
            assertEquals(ReplicaState.READY, group.nodes.get(2).status().state());
            assertEquals(target, app.appliedIndex());
            assertEquals(0, group.nodes.get(2).durabilityMetrics().checkpointSequence(), "private cut must not become a durable checkpoint");
            assertEquals(group.leader().status().applicationSequence(), app.sequence());
            assertEquals(new Document(1, "update-" + (history + 9)), app.read(engine -> engine.get(1)));
            assertNull(app.read(engine -> engine.get(99)));
            int decodes = codec.decodes.get();
            assertEquals(target, catchUpWhenAdmitted(group, peer, () -> { }));
            assertEquals(decodes, codec.decodes.get(), "duplicate catch-up must not replay");
            group.nodes.get(1).close();
            group.add(new Document(2, "next quorum")).get(10, TimeUnit.SECONDS);
            assertEquals(new Document(2, "next quorum"), app.read(engine -> engine.get(2)));
        }
    }

    @ParameterizedTest
    @ValueSource(booleans = {true, false})
    void readyRebuildsUnresolvedPrivateOrMissingPublishedState(boolean unresolved) throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            group.add(new Document(1, "committed")).get(10, TimeUnit.SECONDS);
            await(() -> group.nodes.get(2).status().appliedIndex() == 2);
            var app = group.applications.get(2);
            var leader = group.leader().status();
            if (unresolved) {
                // Model preparation succeeding before the durable append is accepted.
                app.prepare(new ReplicaEntry(group.manifest.digest(), leader.activeEpoch(), java.util.UUID.randomUUID(),
                        3, "ADD", leader.activeEpoch(), 2, "0".repeat(64),
                        app.documents("ADD", List.of(new Document(2, "uncommitted")))));
            } else {
                // Model durable authority whose application publication still needs rebuilding.
                try (var empty = application(temporary.resolve("empty-app"), BOUNDS)) { app.replaceWith(empty); }
            }
            assertNull(app.read(engine -> engine.get(2)));
            assertEquals(2, group.leader().catchUp(group.manifest.members().get(2).nodeId()).get(10, TimeUnit.SECONDS));
            assertEquals(new Document(1, "committed"), app.read(engine -> engine.get(1)));
            group.nodes.get(1).close();
            group.add(new Document(2, "committed after recovery")).get(10, TimeUnit.SECONDS);
            assertEquals(new Document(2, "committed after recovery"), app.read(engine -> engine.get(2)));
        }
    }
}
