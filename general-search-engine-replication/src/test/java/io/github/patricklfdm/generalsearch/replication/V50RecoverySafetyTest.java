package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class V50RecoverySafetyTest {
    @TempDir Path temporary;
    private record Cut(ReplicaManifest manifest, ReplicaRecoveryImage image, byte[] empty) { }
    private Cut cut() throws Exception {
        var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE);
        byte[] state, empty;
        try (group) {
            group.leader().activate().get(10, TimeUnit.SECONDS); group.add(new Document(1, "protected")).get(10, TimeUnit.SECONDS);
            V50LeaderPathTest.await(() -> group.nodes.stream().allMatch(node -> node.status().appliedIndex() == 2));
            state = group.applications.getFirst().snapshot(); empty = group.applications.getFirst().emptySnapshot();
        }
        try (var store = ReplicaStore.open(temporary.resolve("node-1"), group.manifest, LEADER, BOUNDS, ReplicaStore.Faults.NONE)) {
            var history = store.image(empty);
            return new Cut(group.manifest, new ReplicaRecoveryImage(new ReplicaSnapshot(group.manifest.digest(), history.anchors(), store.proofAt(2), state), List.of(), List.of()), empty);
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"AFTER_RECOVERY_STAGE_CREATE", "AFTER_RECOVERY_SNAPSHOT_FILE_FORCE", "AFTER_RECOVERY_ENTRIES_FORCE",
            "AFTER_RECOVERY_PROOFS_FORCE", "AFTER_RECOVERY_STAGE_FORCE", "BEFORE_RECOVERY_POINTER_PUBLISH",
            "AFTER_RECOVERY_POINTER_RENAME", "AFTER_RECOVERY_POINTER_FORCE"})
    void interruptedGenerationKeepsOldOrCompleteNewAuthorityAndCanBeRetried(String point) throws Exception {
        var cut = cut(); UUID incarnation = UUID.randomUUID();
        var faults = new ReplicaStore.Faults() {
            public void at(String barrier) throws java.io.IOException { if (barrier.equals(point)) throw new java.io.IOException("injected generation interruption"); }
        };
        try (var store = ReplicaStore.open(temporary.resolve("node-1"), cut.manifest(), LEADER, BOUNDS, faults)) {
            store.promise(LEADER, 3, incarnation);
            assertEquals(ReplicationException.Reason.STORAGE_FAILURE, assertThrows(ReplicationException.class, () -> store.install(cut.image(), 3, incarnation, false)).reason());
        }
        assertTrue(ReplicationStorageOperations.inspect(temporary.resolve("node-1")).structurallyValid());
        try (var store = ReplicaStore.open(temporary.resolve("node-1"), cut.manifest(), LEADER, BOUNDS, ReplicaStore.Faults.NONE)) {
            assertEquals(2, store.commitIndex());
            assertEquals(point.contains("POINTER_RENAME") || point.contains("POINTER_FORCE") ? 2 : 0, store.snapshotIndex());
            if (store.snapshotIndex() > 0) { store.advanceFloor(2, cut.image().digestAt(2), List.of(LEADER, cut.manifest().members().get(1).nodeId())); store.compact(); }
            store.install(cut.image(), 3, incarnation, false);
            store.advanceFloor(2, cut.image().digestAt(2), List.of(LEADER, cut.manifest().members().get(1).nodeId())); store.compact();
            assertEquals(2, store.snapshotIndex());
            try (var app = application(temporary.resolve("rebuilt-app"), BOUNDS); var rebuilt = app.rebuild(store.image(cut.empty()))) {
                assertEquals(new Document(1, "protected"), rebuilt.read(engine -> engine.get(1)));
                assertEquals(1, rebuilt.sequence());
            }
        }
    }

    @Test
    void floorRequiresTwoDistinctSourcesAndAValidLocalSnapshot() throws Exception {
        var cut = cut(); UUID incarnation = UUID.randomUUID();
        try (var store = ReplicaStore.open(temporary.resolve("node-1"), cut.manifest(), LEADER, BOUNDS, ReplicaStore.Faults.NONE)) {
            store.promise(LEADER, 3, incarnation);
            assertThrows(ReplicationException.class, () -> store.advanceFloor(2, cut.image().digestAt(2), List.of(LEADER, cut.manifest().members().get(1).nodeId())));
            store.install(cut.image(), 3, incarnation, false);
            assertThrows(ReplicationException.class, () -> store.advanceFloor(2, cut.image().digestAt(2), List.of(LEADER)));
            assertThrows(ReplicationException.class, () -> store.advanceFloor(2, cut.image().digestAt(2), List.of(LEADER, LEADER)));
            assertThrows(ReplicationException.class, store::compact);
        }
    }

    @Test
    void missingSelectorCannotExposeTheEmptyLegacyJournals() throws Exception {
        var cut = cut(); UUID incarnation = UUID.randomUUID(); Path root = temporary.resolve("node-1");
        try (var store = ReplicaStore.open(root, cut.manifest(), LEADER, BOUNDS, ReplicaStore.Faults.NONE)) {
            store.promise(LEADER, 3, incarnation); store.install(cut.image(), 3, incarnation, false);
            store.advanceFloor(2, cut.image().digestAt(2), List.of(LEADER, cut.manifest().members().get(1).nodeId())); store.compact();
        }
        Files.delete(root.resolve(ReplicaGeneration.CURRENT)); Files.delete(root.resolve(ReplicaGeneration.FLOOR));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.inspect(root));
    }

    @Test
    void erasedReplacementMarkerCannotTurnTheDiskIntoAGenesisVoter() throws Exception {
        var manifest = manifest(ports()); Path root = temporary.resolve("replacement");
        ReplicaStore.initializeReplacement(root, manifest, LEADER, BOUNDS, ReplicaStore.Faults.NONE);
        try (var store = ReplicaStore.open(root, manifest, LEADER, BOUNDS, ReplicaStore.Faults.NONE)) { assertFalse(store.voter()); }
        Files.delete(root.resolve(ReplicaGeneration.REBUILDING));
        assertThrows(ReplicationException.class, () -> ReplicaStore.open(root, manifest, LEADER, BOUNDS, ReplicaStore.Faults.NONE));
    }

    @ParameterizedTest
    @ValueSource(booleans = {true, false})
    void conflictingValidProofsFailBeforeHistoryInstallation(boolean duringActivation) throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); group.add(new Document(1, "original")).get(10, TimeUnit.SECONDS);
            V50LeaderPathTest.await(() -> group.nodes.stream().allMatch(node -> node.status().appliedIndex() == 2));
            group.nodes.get(duringActivation ? 0 : 2).close(); group.nodes.get(1).close();
            var originalId = group.manifest.members().get(duringActivation ? 0 : 2).nodeId();
            var peer = group.manifest.members().get(1).nodeId(); Path root = temporary.resolve(peer.value());
            Files.move(root, temporary.resolve("retained-conflict-source"));
            ReplicaStore.initialize(root, group.manifest, peer, BOUNDS, ReplicaStore.Faults.NONE);
            try (var original = ReplicaStore.open(temporary.resolve(originalId.value()), group.manifest, originalId, BOUNDS, ReplicaStore.Faults.NONE);
                 var other = ReplicaStore.open(root, group.manifest, peer, BOUNDS, ReplicaStore.Faults.NONE);
                 var encoder = application(temporary.resolve("encoder"), BOUNDS)) {
                var first = original.entryAt(1); other.promise(LEADER, 2, first.incarnation()); other.append(LEADER, first); other.storeProof(LEADER, original.proofAt(1));
                var entry = new ReplicaEntry(group.manifest.digest(), 2, first.incarnation(), 2, "ADD", 2, 1, original.digestAt(1), encoder.documents("ADD", List.of(new Document(1, "conflict"))));
                var own = other.append(LEADER, entry); String digest = frameDigest(entry.encode(BOUNDS.maxFrameBytes()));
                other.storeProof(LEADER, new ReplicaProof(group.manifest.digest(), 2, entry.incarnation(), 2, digest, entry.previousDigest(),
                        List.of(ReplicaProof.acknowledgement(LEADER, entry, digest), own)));
            }
            for (int index : List.of(duringActivation ? 0 : 2, 1)) {
                var id = group.manifest.members().get(index).nodeId(); var app = application(temporary.resolve("new-app-" + index), BOUNDS);
                group.applications.set(index, app); group.nodes.set(index, new ReplicaNode<>(temporary.resolve(id.value()), group.manifest, id, BOUNDS, app, ReplicaStore.Faults.NONE, ReplicaNode.Events.NONE));
            }
            V50LeaderPathTest.rejected(ReplicationException.Reason.CONFLICTING_HISTORY, duringActivation ? group.leader().activate() : group.leader().catchUp(peer));
            assertFalse(group.leader().status().writeQuorumAvailable());
            V50LeaderPathTest.rejected(ReplicationException.Reason.QUORUM_UNAVAILABLE, group.add(new Document(2, "must reject")));
        }
    }
}
