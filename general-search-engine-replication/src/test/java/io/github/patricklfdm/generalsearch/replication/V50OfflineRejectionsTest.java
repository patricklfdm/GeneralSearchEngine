package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50OfflineRejectionsTest {
    @TempDir Path root;
    @AfterEach void clear() { AdmissionIo.FAULTS.remove(); }

    private ReplicationBootstrapPlan stop(String barrier, Path source) {
        var request = request(root, source); var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        AdmissionIo.FAULTS.set(name -> { if (name.equals(barrier)) throw new IOException("cut"); });
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyBootstrap(builder(), request, plan));
        AdmissionIo.FAULTS.remove(); return plan;
    }

    @Test
    void liveCleanupOwnerSurvivesDeletionOfOriginalOperationLock() throws Exception {
        stop("BOOTSTRAP_PREPARED_FORCED", null);
        var cleanup = ReplicationStorageOperations.planCleanup(root.resolve("operation"));
        int index = cleanup.deletePaths().indexOf(root.resolve("operation/operation.lock"));
        assertTrue(index >= 0);
        var observed = new java.util.concurrent.atomic.AtomicBoolean();
        AdmissionIo.FAULTS.set(barrier -> {
            if (barrier.equals("CLEANUP_DELETE_" + index + "_FORCED")) {
                assertEquals(ReplicationException.Reason.STORAGE_FAILURE, assertThrows(ReplicationException.class,
                        () -> ReplicationStorageOperations.planCleanup(root.resolve("operation"))).reason());
                observed.set(true); throw new IOException("stop after original ownership path deletion");
            }
        });
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyCleanup(cleanup));
        assertTrue(observed.get()); AdmissionIo.FAULTS.remove();
        ReplicationStorageOperations.applyCleanup(cleanup);
        assertFalse(Files.exists(root.resolve("operation")));
    }

    @Test
    void callerCannotChangeCapturedBuilderSettingsOrBindingsAfterPlanning() throws Exception {
        var request = request(root, null); var plan = ReplicationStorageOperations.planBootstrap(builder(), request);
        var changed = builder().config(new SnapshotEngineConfig(32, 7, Duration.ofNanos(1_234_567)));
        assertEquals(ReplicationException.Reason.CONFLICTING_HISTORY,
                assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.applyBootstrap(changed, request, plan)).reason());
        try (var files = Files.list(root)) { assertEquals(0, files.count()); }
    }

    @Test
    void liveTargetOwnerRejectsResumeAndCleanupWithoutChangingBytes() throws Exception {
        var plan = stop("BOOTSTRAP_PREPARED_FORCED", null); var request = request(root, null);
        var before = AdmissionPaths.inventory(root, 1 << 20);
        try (var channel = FileChannel.open(root.resolve("node-2/replica.lock"), StandardOpenOption.WRITE); var lock = channel.lock()) {
            assertEquals(ReplicationException.Reason.STORAGE_FAILURE,
                    assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.resumeBootstrap(builder(), request, plan)).reason());
            assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        }
        assertEquals(before, AdmissionPaths.inventory(root, 1 << 20));
    }

    @Test
    void corruptJournalNeverAuthorizesResumeOrCleanup() throws Exception {
        var plan = stop("BOOTSTRAP_PREPARED_FORCED", null); var request = request(root, null);
        Path journal = root.resolve("operation/operation.gsr"); byte[] bytes = Files.readAllBytes(journal);
        Files.write(journal, Arrays.copyOf(bytes, bytes.length - 1)); var before = AdmissionPaths.inventory(root, 1 << 20);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.resumeBootstrap(builder(), request, plan));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        assertEquals(before, AdmissionPaths.inventory(root, 1 << 20));
    }

    @Test
    void prematureReceiptCannotBePromotedIntoACommit() throws Exception {
        var plan = stop("BOOTSTRAP_PREPARED_FORCED", null); var request = request(root, null);
        var retained = AdmissionPlan.read(Files.readAllBytes(root.resolve("operation/plan.gsr")));
        Files.write(root.resolve("operation/receipt.gsr"), retained.receipt()); var before = AdmissionPaths.inventory(root, 1 << 20);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.resumeBootstrap(builder(), request, plan));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        assertEquals(before, AdmissionPaths.inventory(root, 1 << 20));
    }

    @Test
    void interruptedPendingSealCompletesButAlteredPublishedSealIsNeverOverwritten() throws Exception {
        var plan = stop("BOOTSTRAP_COMMITTED_FORCED", null); var request = request(root, null);
        var retained = AdmissionPlan.read(Files.readAllBytes(root.resolve("operation/plan.gsr")));
        Files.write(root.resolve("node-1/bootstrap-seal.pending.gsr"), Arrays.copyOf(retained.seal(0), 73));
        ReplicationStorageOperations.resumeBootstrap(builder(), request, plan);
        assertFalse(Files.exists(root.resolve("node-1/bootstrap-seal.pending.gsr")));
        Path seal = root.resolve("node-2/bootstrap-seal.gsr"); byte[] damaged = Files.readAllBytes(seal); damaged[damaged.length - 1] ^= 1; Files.write(seal, damaged);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.resumeBootstrap(builder(), request, plan));
        assertArrayEquals(damaged, Files.readAllBytes(seal));
    }

    @Test
    void changedSourceBeforeCommitRejectsAndLeavesPreparedOutputUntouched() throws Exception {
        Path source = root.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(), 41, List.of(new Doc(1, "shared")), List.of(IndexDefinition.equality(VALUE))),
                storage(root.resolve("anchor"), 2), new DurableBackupRequest(source, 1 << 20));
        var plan = stop("BOOTSTRAP_PREPARED_FORCED", source); var request = request(root, source);
        Path member = source.resolve("gse-backup-checkpoint"); byte[] damaged = Files.readAllBytes(member); damaged[damaged.length - 1] ^= 1; Files.write(member, damaged);
        var before = AdmissionPaths.inventory(root, 1 << 20);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.resumeBootstrap(builder(), request, plan));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planCleanup(request.operationDirectory()));
        assertEquals(before, AdmissionPaths.inventory(root, 1 << 20));
    }

    @Test
    void symlinkParentsAndHardlinkedSourceMembersRejectBeforeCreatingOperation() throws Exception {
        Path actual = Files.createDirectory(root.resolve("real")); Path link = root.resolve("link"); Files.createSymbolicLink(link, actual);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planBootstrap(builder(), request(link, null)));
        Path source = root.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(), 0, List.of(), List.of(IndexDefinition.equality(VALUE))),
                storage(root.resolve("anchor"), 0), new DurableBackupRequest(source, 1 << 20));
        Files.createLink(root.resolve("aliased-checkpoint"), source.resolve("gse-backup-checkpoint"));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planBootstrap(builder(), request(root, source)));
        assertFalse(Files.exists(root.resolve("operation"))); assertFalse(Files.exists(root.resolve("node-1")));
    }

    @Test
    void sourceAtMaximumSequenceHasNoLegalBootstrapContinuation() throws Exception {
        Path source = root.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(), Long.MAX_VALUE, List.of(), List.of(IndexDefinition.equality(VALUE))),
                storage(root.resolve("anchor"), 0), new DurableBackupRequest(source, 1 << 20));
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.planBootstrap(builder(), request(root, source)));
        assertFalse(Files.exists(root.resolve("operation")));
    }
}
