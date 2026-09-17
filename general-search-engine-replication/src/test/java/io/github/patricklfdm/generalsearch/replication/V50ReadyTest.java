package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.V50LeaderPathTest.await;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;
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
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            group.add(new Document(1, "before isolation")).get(10, TimeUnit.SECONDS);
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
            for (int retry = 0; retry < 3; retry++) {
                assertEquals(committed, group.leader().catchUp(peer).get(10, TimeUnit.SECONDS));
                assertEquals(ReplicaState.READY, group.nodes.get(2).status().state());
                assertEquals(committed, app.appliedIndex());
                assertEquals(group.leader().status().applicationSequence(), app.sequence());
                assertEquals(group.leader().<Document>read(engine -> engine.get(1)), app.read(engine -> engine.get(1)));
                assertEquals(installedDecodes.get(), codec.decodes.get(), "READY must not replay an already published history");
            }
            // The reused private working state must support the next real quorum write.
            group.nodes.get(1).close();
            group.add(new Document(2, "new quorum")).get(10, TimeUnit.SECONDS);
            assertEquals(new Document(2, "new quorum"), app.read(engine -> engine.get(2)));
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
