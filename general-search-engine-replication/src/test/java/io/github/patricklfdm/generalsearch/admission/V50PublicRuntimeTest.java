package io.github.patricklfdm.generalsearch.admission;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletionException;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.replication.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50PublicRuntimeTest {
    @TempDir Path directory;
    static void reason(ReplicationException.Reason reason, Runnable action) {
        Throwable error = assertThrows(RuntimeException.class, action::run);
        while (error instanceof CompletionException && error.getCause() != null) error = error.getCause();
        assertInstanceOf(ReplicationException.class, error);
        assertEquals(reason, ((ReplicationException) error).reason());
    }
    @Test void stoppedHandleHasNoResourcesAndFreezesConfiguration() throws Exception {
        var builder = builder(); var config = configurations(directory).getFirst();
        try (var engine = ReplicatedSearchEngines.builder(builder, config).build()) {
            builder.index(IndexDefinition.prefix(VALUE));
            assertEquals(ReplicaState.STARTING, engine.replicationStatus().state());
            assertEquals(0, engine.replicationStatus().promisedEpoch());
            assertEquals(2, engine.replicationDiagnostics().peers().size());
            assertTrue(engine.replicationDiagnostics().manifestDigest().isEmpty());
            assertSame(ID, engine.field("id"));
            reason(ReplicationException.Reason.QUORUM_UNAVAILABLE, () -> engine.get(1));
            reason(ReplicationException.Reason.QUORUM_UNAVAILABLE, () -> engine.add(null).join());
            reason(ReplicationException.Reason.QUORUM_UNAVAILABLE, engine::durabilityMetrics);
            try (var files = Files.list(directory)) { assertEquals(0, files.count()); }
        }
    }
    @Test void absentAuthorityFailsAndNeverBootstraps() {
        var engine = ReplicatedSearchEngines.builder(builder(), configurations(directory).getFirst()).build();
        reason(ReplicationException.Reason.STORAGE_FAILURE, () -> engine.start().join());
        assertEquals(ReplicaState.FAILED, engine.replicationStatus().state());
        reason(ReplicationException.Reason.STORAGE_FAILURE, () -> engine.start().join());
        assertFalse(Files.exists(directory.resolve("node-1")));
        engine.close(); assertEquals(ReplicaState.CLOSED, engine.replicationStatus().state());
    }
    @Test void everyFollowerOverloadRejectsBeforeNullArguments() {
        try (var engine = ReplicatedSearchEngines.builder(builder(), configurations(directory).get(1)).build()) {
            var reason = ReplicationException.Reason.NOT_CONFIGURED_LEADER;
            reason(reason, () -> engine.add(null).join()); reason(reason, () -> engine.update(null).join());
            reason(reason, () -> engine.remove(null).join()); reason(reason, () -> engine.addAll(null).join());
            reason(reason, () -> engine.updateAll(null).join()); reason(reason, () -> engine.removeAll(null).join());
            reason(reason, () -> engine.createIndex(null).join()); reason(reason, () -> engine.dropIndex(null).join());
            reason(reason, () -> engine.get(null)); reason(reason, () -> engine.search((Query<Doc>) null));
            reason(reason, () -> engine.search((io.github.patricklfdm.generalsearch.search.SearchRequest<Doc>) null));
            reason(reason, () -> engine.search((io.github.patricklfdm.generalsearch.search.SearchPageRequest<Doc>) null));
            reason(reason, () -> engine.search((io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest<Doc>) null));
            reason(reason, () -> engine.searchTopK(null)); reason(reason, () -> engine.explain(null, null));
            reason(reason, engine::metrics); reason(reason, engine::currentSequence);
            reason(reason, () -> engine.backup(null).join()); reason(reason, () -> engine.activateConfiguredLeader().join());
            reason(reason, () -> engine.catchUp(null).join()); reason(reason, () -> engine.reconstructConfiguredLeader().join());
        }
    }
    @Test void importedGenesisActivatesMutatesCheckpointsExportsAndRestarts() throws Exception {
        Path source = directory.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(), 41,
                List.of(new Doc(3, "shared"), new Doc(1, "shared")), List.of(IndexDefinition.equality(VALUE))),
                storage(directory.resolve("anchor"), 2), new DurableBackupRequest(source, 1 << 20));
        var request = request(directory, source);
        var result = ReplicationStorageOperations.applyBootstrap(builder(), request, ReplicationStorageOperations.planBootstrap(builder(), request));
        try (var leader = ReplicatedSearchEngines.builder(builder(), request.replicas().getFirst()).build();
             var follower = ReplicatedSearchEngines.builder(builder(), request.replicas().get(1)).build();
             var third = ReplicatedSearchEngines.builder(builder(), request.replicas().get(2)).build()) {
            for (var node : List.of(leader, follower, third)) {
                assertEquals(ReplicaState.CATCHING_UP, node.start().join().state());
                assertEquals(41, node.replicationStatus().applicationSequence());
                assertEquals(0, node.replicationStatus().appliedIndex());
                assertEquals(RecoverySource.CHECKPOINT_ONLY, node.durabilityMetrics().recoverySource());
            }
            reason(ReplicationException.Reason.QUORUM_UNAVAILABLE, () -> leader.get(3));
            follower.checkpoint().join();
            assertEquals(0, follower.replicationDiagnostics().recoveryFloor());
            var active = leader.activateConfiguredLeader().join();
            assertEquals(active.activeEpoch(), leader.activateConfiguredLeader().join().activeEpoch());
            assertEquals(41, leader.currentSequence());
            assertEquals(List.of(3, 1), leader.search(doc -> true).stream().map(Doc::id).toList());
            long beforeRejectedIndex = leader.replicationStatus().lastLogIndex();
            var foreign = io.github.patricklfdm.generalsearch.schema.Field.of("value", String.class, Doc::value);
            var invalidIndex = assertThrows(CompletionException.class, () -> leader.createIndex(IndexDefinition.prefix(foreign)).join());
            assertInstanceOf(IllegalArgumentException.class, invalidIndex.getCause());
            reason(ReplicationException.Reason.PROTOCOL_MISMATCH,
                    () -> leader.createIndex(IndexDefinition.prefix(VALUE)).join());
            assertEquals(beforeRejectedIndex, leader.replicationStatus().lastLogIndex());
            assertEquals(41, leader.currentSequence());
            leader.addAll(List.of(new Doc(2, "shared"), new Doc(4, "other"))).join();
            leader.update(new Doc(4, "changed")).join(); leader.remove(2).join();
            leader.dropIndex("value").join(); leader.createIndex(IndexDefinition.prefix(VALUE)).join();
            assertEquals(46, leader.currentSequence());
            Path unsafeBackup = request.replicas().getFirst().replicaDirectory().resolve("backup");
            var unsafe = assertThrows(CompletionException.class, () -> leader.backup(new DurableBackupRequest(unsafeBackup, 1 << 20)).join());
            assertEquals(DurableOperationException.Reason.TARGET_INVALID, ((DurableOperationException) unsafe.getCause()).reason());
            assertFalse(Files.exists(unsafeBackup));
            long boundary = leader.catchUp(request.replicas().get(2).localNodeId()).join();
            assertEquals(leader.replicationStatus().commitIndex(), boundary);
            leader.checkpoint().join();
            assertEquals(46, leader.durabilityMetrics().checkpointSequence());
            assertEquals(0, leader.replicationDiagnostics().recoveryFloor());
            Path backup = directory.resolve("backup");
            leader.backup(new DurableBackupRequest(backup, 1 << 20)).join();
            var exported = io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(Doc.class, ID).index(IndexDefinition.prefix(VALUE)).readDurableBackup(backup, new DurableVerificationConfig<>("fixture-store", "fixture-schema", new Codec(), 1, 1024, 65536, 10000), 1 << 20);
            assertEquals(result.applicationHistory(), exported.history()); assertEquals(46, exported.sequence());
            assertEquals(List.of(3, 1, 4), exported.documents().stream().map(Doc::id).toList());
            assertEquals(1, exported.indexes().size());
        }
        try (var reopened = ReplicatedSearchEngines.builder(builder(), request.replicas().getFirst()).build()) {
            reopened.start().join(); assertEquals(46, reopened.replicationStatus().applicationSequence());
            assertEquals(RecoverySource.CHECKPOINT_ONLY, reopened.durabilityMetrics().recoverySource());
            reason(ReplicationException.Reason.QUORUM_UNAVAILABLE, () -> reopened.get(3));
        }
    }

    @Test void applicationSequenceExhaustionRejectsBeforeAllocatingAnotherEntry() {
        Path source = directory.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(), Long.MAX_VALUE - 1,
                List.<Doc>of(), List.of(IndexDefinition.equality(VALUE))), storage(directory.resolve("anchor"), 2), new DurableBackupRequest(source, 1 << 20));
        var request = request(directory, source);
        ReplicationStorageOperations.applyBootstrap(builder(), request, ReplicationStorageOperations.planBootstrap(builder(), request));
        try (var leader = ReplicatedSearchEngines.builder(builder(), request.replicas().getFirst()).build();
             var follower = ReplicatedSearchEngines.builder(builder(), request.replicas().get(1)).build();
             var third = ReplicatedSearchEngines.builder(builder(), request.replicas().get(2)).build()) {
            for (var node : List.of(leader, follower, third)) node.start().join();
            leader.activateConfiguredLeader().join(); assertEquals(Long.MAX_VALUE - 1, leader.currentSequence());
            leader.add(new Doc(1, "last")).join(); assertEquals(Long.MAX_VALUE, leader.currentSequence());
            long index = leader.replicationStatus().lastLogIndex();
            reason(ReplicationException.Reason.CAPACITY_EXCEEDED, () -> leader.add(new Doc(2, "overflow")).join());
            assertEquals(index, leader.replicationStatus().lastLogIndex()); assertNull(leader.get(2));
            assertEquals(ReplicaState.READY, leader.replicationStatus().state());
            leader.checkpoint().join(); assertEquals(Long.MAX_VALUE, leader.durabilityMetrics().checkpointSequence());
        }
    }
}
