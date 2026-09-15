package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50OfflineAuthorityTest {
    @TempDir Path directory;
    @AfterEach void clearFaults() { AdmissionIo.FAULTS.remove(); }

    @Test
    void deterministicEmptyBootstrapPublishesOneDecisionAndThreeSelfContainedSeals() throws Exception {
        var request = request(directory, null);
        var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        assertEquals(plan, ReplicationStorageOperations.planBootstrap(builder(), request));
        try (var members = Files.list(directory)) { assertEquals(0, members.count()); }
        var result = ReplicationStorageOperations.applyBootstrap(builder(), request, plan);
        assertEquals(0, result.applicationSequence()); assertEquals(result, ReplicationStorageOperations.readBootstrapResult(request.operationDirectory()));
        assertEquals(result, ReplicationStorageOperations.resumeBootstrap(builder(), request, plan));
        for (var local : request.replicas()) {
            var status = ReplicationStorageOperations.inspect(local.replicaDirectory());
            assertEquals(1, status.formatMinor()); assertTrue(status.structurallyValid());
            assertFalse(Files.exists(local.materialization().directory()));
            try (var handle = ReplicatedSearchEngines.builder(builder(), local).build()) { assertEquals(ReplicaState.STARTING, handle.replicationStatus().state()); }
        }
    }

    @Test
    void importsEveryV4FormatWithoutChangingSourceAndRetainsSequenceAndCanonicalOrder() throws Exception {
        for (int minor = 0; minor < 3; minor++) {
            Path root = Files.createDirectory(directory.resolve("minor-" + minor)), source = root.resolve("source");
            var state = new DurableApplicationState<>(UUID.fromString("33333333-3333-3333-3333-333333333333"), 41,
                    List.of(new Doc(3, "shared"), new Doc(1, "shared")), List.of(IndexDefinition.equality(VALUE)));
            builder().writeDurableBackup(state, storage(root.resolve("anchor"), minor), new DurableBackupRequest(source, 1 << 20));
            var before = AdmissionPaths.inventory(source, 1 << 20); var request = request(root, source);
            var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
            var result = ReplicationStorageOperations.applyBootstrap(builder(), request, plan);
            assertEquals(41, result.applicationSequence()); assertNotEquals(state.history(), result.applicationHistory());
            assertEquals(before, AdmissionPaths.inventory(source, 1 << 20));
            var manifest = AdmissionFormat.Manifest.read(AdmissionPaths.read(root.resolve("node-1/manifest.gsr"), AdmissionFormat.META));
            var genesis = AdmissionFormat.Genesis.read(AdmissionPaths.read(root.resolve("node-1/genesis.gsr"), AdmissionFormat.IMAGE), manifest);
            assertEquals(41, genesis.base()); assertEquals(state.history(), genesis.source().history());
            assertArrayEquals(AdmissionBootstrap.application(builder().configuration(), state.documents(), storage(root.resolve("unused"), minor), AdmissionFormat.IMAGE), genesis.application());
        }
    }

    @Test
    void everyBootstrapForceBoundaryCanResumeWithoutMintingAnotherDecision() throws Exception {
        var barriers = new ArrayList<String>();
        AdmissionIo.FAULTS.set(barriers::add);
        Path baseline = Files.createDirectory(directory.resolve("baseline")); var baselineRequest = request(baseline, null);
        ReplicationStorageOperations.applyBootstrap(builder(), baselineRequest, ReplicationStorageOperations.planBootstrap(builder(), baselineRequest));
        AdmissionIo.FAULTS.remove();
        for (int cut = 0; cut < barriers.size(); cut++) {
            String barrier = barriers.get(cut); Path root = Files.createDirectory(directory.resolve("cut-" + cut)); var request = request(root, null);
            var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
            AdmissionIo.FAULTS.set(name -> { if (name.equals(barrier)) throw new IOException("injected cut"); });
            assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyBootstrap(builder(), request, plan), barrier);
            AdmissionIo.FAULTS.remove();
            var result = ReplicationStorageOperations.resumeBootstrap(builder(), request, plan);
            assertEquals(result, ReplicationStorageOperations.resumeBootstrap(builder(), request, plan), barrier);
        }
        assertTrue(barriers.size() >= 40);
    }

    @Test
    void committedResumeNeedsNoSourceAndCleanupNeverDeletesCommittedOutput() throws Exception {
        Path source = directory.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(), 41, List.of(new Doc(1, "shared")), List.of(IndexDefinition.equality(VALUE))),
                storage(directory.resolve("anchor"), 2), new DurableBackupRequest(source, 1 << 20));
        var request = request(directory, source); var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        AdmissionIo.FAULTS.set(name -> { if (name.equals("BOOTSTRAP_COMMITTED_FORCED")) throw new IOException("cut"); });
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyBootstrap(builder(), request, plan)); AdmissionIo.FAULTS.remove();
        var before = AdmissionPaths.inventory(directory.resolve("node-1"), 1 << 20);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        assertEquals(before, AdmissionPaths.inventory(directory.resolve("node-1"), 1 << 20));
        try (var members = Files.list(source)) { for (var member : members.toList()) Files.delete(member); } Files.delete(source);
        assertEquals(41, ReplicationStorageOperations.resumeBootstrap(builder(), request, plan).applicationSequence());
    }

    @Test
    void cleanupBindsExactInventoryAndResumesOnlyADeletedPrefix() throws Exception {
        var request = request(directory, null); var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        AdmissionIo.FAULTS.set(name -> { if (name.equals("BOOTSTRAP_PREPARED_FORCED")) throw new IOException("cut"); });
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyBootstrap(builder(), request, plan)); AdmissionIo.FAULTS.remove();
        var cleanup = ReplicationStorageOperations.planCleanup(request.operationDirectory());
        Files.writeString(directory.resolve("node-1/unknown"), "preserve");
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyCleanup(cleanup));
        assertEquals("preserve", Files.readString(directory.resolve("node-1/unknown"))); Files.delete(directory.resolve("node-1/unknown"));
        AdmissionIo.FAULTS.set(name -> { if (name.equals("CLEANUP_DELETE_2_FORCED")) throw new IOException("cut"); });
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyCleanup(cleanup)); AdmissionIo.FAULTS.remove();
        assertEquals(cleanup, ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        ReplicationStorageOperations.applyCleanup(cleanup);
        try (var children = Files.list(directory)) { assertEquals(0, children.count()); }
    }

    @Test
    void replacementUsesOriginalReceiptButIsDurablyNonvotingAndSourcePreserving() throws Exception {
        var request = request(directory, null); var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        ReplicationStorageOperations.applyBootstrap(builder(), request, plan);
        var old = request.replicas().get(2); Path target = directory.resolve("replacement");
        var config = new ReplicationGroupConfig<>(old.groupId(), old.configurationId(), old.localNodeId(), old.configuredLeaderId(),
                old.members(), target, old.materialization(), old.bounds());
        Path source = directory.resolve("node-1"); var before = AdmissionPaths.inventory(source, 1 << 20);
        var replacement = ReplicationStorageOperations.planReplacement(config, source, directory.resolve("replacement-operation"));
        ReplicationStorageOperations.applyReplacement(config, replacement); ReplicationStorageOperations.resumeReplacement(config, replacement);
        assertEquals(before, AdmissionPaths.inventory(source, 1 << 20));
        var view = AdmissionNode.read(target, 1 << 20); assertTrue(view.replacement()); assertEquals(old.localNodeId(), view.node());
        assertEquals(plan.planDigest(), view.plan().digest()); assertTrue(Files.exists(target.resolve("rebuilding.gsr")));
    }

    @Test
    void forgedPlanOccupiedTargetsOverlapsAndLowBoundsRejectBeforeWrites() throws Exception {
        var request = request(directory, null); var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        var forged = new ReplicationBootstrapPlan(plan.groupId(), plan.configurationId(), plan.source(), plan.sourcePath(), plan.absentReplicaTargets(), "ab".repeat(32));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyBootstrap(builder(), request, forged));
        assertFalse(Files.exists(request.operationDirectory()));
        var low = new ReplicationBootstrapRequest<>(request.source(), null, request.replicas(), request.operationDirectory(), 1, 1);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planBootstrap(builder(), low));
        Files.createDirectory(directory.resolve("node-2"));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planBootstrap(builder(), request));
        assertFalse(Files.exists(request.operationDirectory()));
    }
}
