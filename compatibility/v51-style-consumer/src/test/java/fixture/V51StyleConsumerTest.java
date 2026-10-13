package fixture;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.replication.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51StyleConsumerTest {
    @TempDir Path root;

    @Test void stoppedHandleAndPlanningDoNotCreateAuthority() throws Exception {
        var request = V51StyleConsumer.request(root, null);
        assertEquals("gse-replication/1.2", AutomaticReplicatedSearchEngines.PROTOCOL);
        assertEquals("gse-replication/1.1", ReplicatedSearchEngines.PROTOCOL);
        try (var engine = V51StyleConsumer.stopped(request.replicas().getFirst())) {
            assertEquals(AutomaticReplicationState.STOPPED, engine.leadershipStatus().state());
            assertTrue(engine.leadershipStatus().observedLeader().isEmpty());
        }
        var plan = AutomaticReplicationStorageOperations.planBootstrap(V51StyleConsumer.application(), request);
        assertEquals(plan, AutomaticReplicationStorageOperations.planBootstrap(V51StyleConsumer.application(), request));
        assertEquals(3, plan.absentReplicaTargets().size());
        try (var files = Files.list(root)) { assertEquals(0, files.count()); }
    }

    @Test void emptyBootstrapResumesAndRejectsConfiguredReaderOrCommittedCleanup() throws Exception {
        var request = V51StyleConsumer.request(root, null);
        var plan = AutomaticReplicationStorageOperations.planBootstrap(V51StyleConsumer.application(), request);
        var result = AutomaticReplicationStorageOperations.applyBootstrap(V51StyleConsumer.application(), request, plan);
        assertEquals(0, result.applicationSequence());
        assertEquals(result, AutomaticReplicationStorageOperations.readBootstrapResult(request.operationDirectory()));
        assertEquals(result, AutomaticReplicationStorageOperations.resumeBootstrap(V51StyleConsumer.application(), request, plan));
        Map<String, String> before = hashes(root);
        assertThrows(ReplicationException.class, () -> ReplicationStorageOperations.readBootstrapResult(request.operationDirectory()));
        assertThrows(AutomaticReplicationException.class, () -> V51StyleConsumer.cleanup(request.operationDirectory()));
        assertEquals(before, hashes(root));
        for (var config : request.replicas()) assertFalse(Files.exists(config.materialization().directory()));
    }

    @Test void canonicalBackupCreatesNewHistoryAndPreservesSourceAndSequence() throws Exception {
        Path backup = root.resolve("backup"); UUID history = UUID.randomUUID();
        var state = new DurableApplicationState<>(history, 41,
                List.of(new AutomaticDocument(3, "shared"), new AutomaticDocument(1, "shared")),
                List.of(IndexDefinition.equality(V51StyleConsumer.BODY)));
        V51StyleConsumer.application().writeDurableBackup(state, V51StyleConsumer.storage(root.resolve("anchor")),
                new DurableBackupRequest(backup, 1L << 20));
        Map<String, String> before = hashes(backup);
        var request = V51StyleConsumer.request(root, backup);
        var missingStartupIndex = io.github.patricklfdm.generalsearch.engine.SearchEngine
                .builder(AutomaticDocument.class, V51StyleConsumer.ID).field(V51StyleConsumer.BODY);
        assertThrows(AutomaticReplicationException.class,
                () -> AutomaticReplicationStorageOperations.planBootstrap(missingStartupIndex, request));
        assertFalse(Files.exists(request.operationDirectory()));
        assertEquals(before, hashes(backup));
        var plan = AutomaticReplicationStorageOperations.planBootstrap(V51StyleConsumer.application(), request);
        var result = AutomaticReplicationStorageOperations.applyBootstrap(V51StyleConsumer.application(), request, plan);
        assertEquals(41, result.applicationSequence());
        assertNotEquals(history, result.applicationHistory());
        assertEquals(before, hashes(backup));
        assertEquals(result, AutomaticReplicationStorageOperations.resumeBootstrap(V51StyleConsumer.application(), request, plan));
        assertEquals(before, hashes(backup));
    }

    private static Map<String, String> hashes(Path directory) throws Exception {
        var values = new TreeMap<String, String>();
        try (var files = Files.walk(directory)) {
            for (var file : files.filter(Files::isRegularFile).toList())
                values.put(directory.relativize(file).toString(), HexFormat.of().formatHex(
                        MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file))));
        }
        return values;
    }
}
