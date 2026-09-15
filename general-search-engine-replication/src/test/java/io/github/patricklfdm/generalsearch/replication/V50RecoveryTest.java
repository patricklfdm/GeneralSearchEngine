package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.V50LeaderPathTest.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50RecoveryTest {
    @TempDir Path temporary;

    private static void restart(Group group, int ordinal) {
        group.nodes.get(ordinal).close();
        var id = group.manifest.members().get(ordinal).nodeId();
        var app = application(group.root.resolve("recovered-app-" + ordinal), group.bounds);
        group.applications.set(ordinal, app);
        group.nodes.set(ordinal, new ReplicaNode<>(group.root.resolve(id.value()), group.manifest, id, group.bounds,
                app, ReplicaStore.Faults.NONE, ReplicaNode.Events.NONE));
    }
    private static void settled(Group group, long index) throws Exception {
        await(() -> group.nodes.stream().allMatch(node -> node.status().appliedIndex() == index));
    }
    private static void replace(Group group, int ordinal) throws Exception {
        group.nodes.get(ordinal).close();
        var id = group.manifest.members().get(ordinal).nodeId(); Path directory = group.root.resolve(id.value());
        Files.move(directory, group.root.resolve("retained-lost-" + id.value()));
        ReplicaStore.initializeReplacement(directory, group.manifest, id, group.bounds, ReplicaStore.Faults.NONE);
        restart(group, ordinal);
    }

    @Test
    void restartDiscardsOnlyAnUncommittedSuffixAfterNewPromiseQuorum() throws Exception {
        try (var group = new Group(temporary, BOUNDS, (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_LOCAL_ENTRY_FORCE")) throw new java.io.IOException("injected stop before remote append");
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 1);
            rejected(ReplicationException.Reason.STORAGE_FAILURE, group.add(new Document(1, "uncommitted")));
            restart(group, 0);
            group.leader().activate().get(10, TimeUnit.SECONDS);
            assertEquals(3, group.leader().status().activeEpoch());
            assertEquals(0, group.leader().status().applicationSequence());
            assertNull(group.leader().read(engine -> engine.get(1)));
            group.add(new Document(1, "new committed history")).get(10, TimeUnit.SECONDS);
            assertEquals("new committed history", group.leader().read(engine -> engine.get(1)).value());
        }
    }

    @Test
    void survivingLocalProofIsRecoveredEvenWhenTheOriginalFutureFailed() throws Exception {
        try (var group = new Group(temporary, BOUNDS, (barrier, index) -> {
            if (index == 2 && barrier.equals("AFTER_LOCAL_PROOF_FORCE")) throw new java.io.IOException("lost proof response");
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 1);
            rejected(ReplicationException.Reason.STORAGE_FAILURE, group.add(new Document(1, "protected")));
            restart(group, 0); group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 3);
            assertEquals(new Document(1, "protected"), group.leader().read(engine -> engine.get(1)));
            assertEquals(1, group.leader().status().applicationSequence());
            group.add(new Document(2, "next")).get(10, TimeUnit.SECONDS);
        }
    }

    @Test
    void recoveryFetchesTheHigherCommittedProofFromAFollower() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS);
            group.add(new Document(1, "survives missing local proof")).get(10, TimeUnit.SECONDS); settled(group, 2);
            group.leader().close(); Path proof = temporary.resolve("node-1/proofs.gsr");
            byte[] bytes = Files.readAllBytes(proof); var header = java.nio.ByteBuffer.wrap(bytes);
            int offset = 48 + header.getInt(12); offset += 48 + header.getInt(offset + 12);
            Files.write(proof, java.util.Arrays.copyOf(bytes, offset));
            restart(group, 0); assertEquals(1, group.leader().status().commitIndex());
            group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 3);
            assertNotNull(group.leader().read(engine -> engine.get(1)));
            assertEquals(1, group.leader().status().applicationSequence());
        }
    }

    @Test
    void laggingFollowerReceivesBoundedIncrementalBatches() throws Exception {
        var bounds = new ReplicationBounds(BOUNDS.maxFrameBytes(), 2, 8, 8, 1, 1200, 20, 4096, 64 * 1024 * 1024, 64 * 1024 * 1024);
        try (var group = new Group(temporary, bounds, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 1); group.nodes.get(2).close();
            for (int i = 1; i <= 5; i++) group.add(new Document(i, "value-" + i)).get(10, TimeUnit.SECONDS);
            restart(group, 2);
            assertEquals(6, group.leader().catchUp(group.manifest.members().get(2).nodeId()).get(10, TimeUnit.SECONDS));
            assertEquals(5, group.nodes.get(2).status().applicationSequence());
            assertEquals(new Document(5, "value-5"), group.applications.get(2).read(engine -> engine.get(5)));
            group.nodes.get(1).close(); group.add(new Document(6, "new quorum")).get(10, TimeUnit.SECONDS);
        }
    }

    @Test
    void snapshotCompactsPayloadsAndRestoresTheCompactedPrefixToALaggingVoter() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 1); group.nodes.get(2).close();
            group.add(new Document(1, "x".repeat(8192))).get(10, TimeUnit.SECONDS);
            for (int i = 0; i < 12; i++) group.leader().submit("UPDATE", group.applications.getFirst().documents("UPDATE", List.of(new Document(1, "value-" + i + "x".repeat(8192))))).get(10, TimeUnit.SECONDS);
            long before = group.leader().status().retainedLogBytes(); long sequence = group.leader().status().applicationSequence();
            long checkpoint = group.leader().checkpoint().get(15, TimeUnit.SECONDS);
            assertTrue(group.leader().status().retainedLogBytes() < before / 2);
            assertEquals(sequence, group.leader().status().applicationSequence());
            restart(group, 2); group.leader().catchUp(group.manifest.members().get(2).nodeId()).get(15, TimeUnit.SECONDS);
            assertEquals(sequence, group.nodes.get(2).status().applicationSequence());
            assertEquals(group.leader().<Document>read(engine -> engine.get(1)), group.applications.get(2).<Document>read(engine -> engine.get(1)));
            restart(group, 0); group.leader().activate().get(15, TimeUnit.SECONDS);
            assertEquals(checkpoint + 1, group.leader().status().appliedIndex());
            assertEquals(sequence, group.leader().status().applicationSequence());
            group.add(new Document(2, "after compacted restart")).get(10, TimeUnit.SECONDS);
        }
    }

    @Test
    void replacementFollowerRemainsNonVotingUntilSnapshotReconstruction() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); group.add(new Document(1, "protected")).get(10, TimeUnit.SECONDS); settled(group, 2);
            replace(group, 2);
            assertEquals(0, group.nodes.get(2).status().appliedIndex());
            group.leader().catchUp(group.manifest.members().get(2).nodeId()).get(15, TimeUnit.SECONDS);
            restart(group, 2); group.leader().catchUp(group.manifest.members().get(2).nodeId()).get(15, TimeUnit.SECONDS);
            group.nodes.get(1).close(); group.add(new Document(2, "replacement votes now")).get(10, TimeUnit.SECONDS);
            assertEquals(2, group.nodes.get(2).status().applicationSequence());
        }
    }

    @Test
    void replacementLeaderRequiresBothSurvivorsBeforeItCanVote() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); group.add(new Document(1, "protected")).get(10, TimeUnit.SECONDS); settled(group, 2);
            replace(group, 0); group.nodes.get(2).close();
            rejected(ReplicationException.Reason.CONFLICTING_HISTORY, group.leader().activate());
            rejected(ReplicationException.Reason.QUORUM_UNAVAILABLE, group.leader().reconstructLeader());
            assertEquals(0, group.leader().status().lastLogIndex());
            restart(group, 2); group.leader().reconstructLeader().get(15, TimeUnit.SECONDS);
            assertNotNull(group.leader().read(engine -> engine.get(1)));
            group.add(new Document(2, "after two-survivor reconstruction")).get(10, TimeUnit.SECONDS);
        }
    }

    @Test
    void incompleteUncommittedEntryTailIsRepairedOnlyDuringFencedRecovery() throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            group.leader().activate().get(10, TimeUnit.SECONDS); settled(group, 1); group.leader().close();
            Files.write(temporary.resolve("node-1/entries.gsr"), new byte[]{0x47, 0x53, 0x45}, java.nio.file.StandardOpenOption.APPEND);
            assertThrows(ReplicationException.class, () -> ReplicaStore.open(temporary.resolve("node-1"), group.manifest, LEADER, BOUNDS, ReplicaStore.Faults.NONE));
            restart(group, 0); group.leader().activate().get(10, TimeUnit.SECONDS);
            assertEquals(0, group.leader().status().applicationSequence());
            group.add(new Document(1, "after repair")).get(10, TimeUnit.SECONDS);
        }
    }
}
