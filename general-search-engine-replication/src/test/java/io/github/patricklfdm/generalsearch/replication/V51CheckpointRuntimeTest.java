package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Public checkpoint regressions over deliberately seeded retained storage, not public fault evidence. */
class V51CheckpointRuntimeTest {
    @TempDir Path root;
    List<AutomaticReplicationGroupConfig<Integer,Doc>> configs;
    byte[] manifest, application, first;

    private void retained(boolean advance) throws Exception {
        configs=V51PublicRuntimeTest.configs(root);
        var request=new AutomaticReplicationBootstrapRequest<>(ReplicationBootstrapSource.EMPTY,null,configs,
                root.resolve("operation"),1L<<30,1L<<30);
        AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,
                AutomaticReplicationStorageOperations.planBootstrap(builder(),request));
        manifest=Files.readAllBytes(root.resolve("node-1/manifest.gsr"));
        application=unbase(decode(Files.readAllBytes(root.resolve("node-1/genesis.gsr")),"GENESIS").value().get("application"));
        first=entry(manifest,1,null,9,new byte[0]);
        try(var store=open(1)) {
            store.checkpoint(application); // Older generation at genesis.
            store.promise(promise(manifest,2));prove(store,first);
            store.checkpoint(application); // Active generation at index 1; no floor can retire the older one.
            if(advance)prove(store,entry(manifest,2,first,9,new byte[0]));
        }
        assertTrue(Files.isDirectory(root.resolve("node-1/generation-a")));
        assertTrue(Files.isDirectory(root.resolve("node-1/generation-b")));
        assertFalse(Files.exists(root.resolve("node-1/recovery-floor.gsr")));
    }
    private AutomaticStore open(int node) {
        return AutomaticStore.open(root.resolve("node-"+node),manifest,"node-"+node,
                V51PublicRuntimeTest.BOUNDS,AutomaticStore.Faults.NONE);
    }
    private void prove(AutomaticStore store,byte[] entry) {
        store.accept(accept(manifest,entry,2));store.prove(proof(manifest,entry,2));
    }
    private AutomaticReplicatedSearchEngine<Integer,Doc> engine() {
        return AutomaticReplicatedSearchEngines.builder(builder(),configs.getFirst()).build();
    }
    private Map<Path,byte[]> generationBytes() throws Exception {
        var files=new LinkedHashMap<Path,byte[]>();
        files.put(root.resolve("node-1/current.gsr"),Files.readAllBytes(root.resolve("node-1/current.gsr")));
        for(String generation:List.of("generation-a","generation-b"))
            for(String name:AutomaticRecoveryFiles.GENERATION_FILES) {
                Path path=root.resolve("node-1").resolve(generation).resolve(name);files.put(path,Files.readAllBytes(path));
            }
        return files;
    }
    private void unchanged(Map<Path,byte[]> files) throws Exception {
        for(var file:files.entrySet())assertArrayEquals(file.getValue(),Files.readAllBytes(file.getKey()),file.getKey().toString());
    }
    @Test void identicalCheckpointReusesActiveGenerationWithoutQuorumOrRetirement() throws Exception {
        retained(false);var before=generationBytes();
        // Only this voter starts, so background maintenance cannot establish a two-source floor.
        for(int reopen=0;reopen<2;reopen++)try(var engine=engine()) {
            assertEquals(1,engine.start().get(15,TimeUnit.SECONDS).appliedIndex());
            for(int retry=0;retry<3;retry++)engine.checkpoint().get(15,TimeUnit.SECONDS);
            assertEquals(0,engine.durabilityMetrics().checkpointSequence());
            assertEquals(1,engine.leadershipStatus().provenIndex());
            unchanged(before);assertFalse(Files.exists(root.resolve("node-1/recovery-floor.gsr")));
        }
        try(var store=open(1)){assertFalse(store.quarantined());assertEquals(1,store.status().get("provenThrough"));}
    }
    @Test void newerCheckpointWaitsForDurableFloorWithoutQuarantiningVoter() throws Exception {
        retained(true);var before=generationBytes();
        try(var engine=engine()) {
            assertEquals(2,engine.start().get(15,TimeUnit.SECONDS).appliedIndex());
            var failed=assertThrows(ExecutionException.class,()->engine.checkpoint().get(15,TimeUnit.SECONDS));
            var error=assertInstanceOf(AutomaticReplicationException.class,failed.getCause());
            assertEquals(AutomaticReplicationException.Reason.CAPACITY_EXCEEDED,error.reason());
            assertEquals(AutomaticReplicationException.Outcome.NOT_APPLICABLE,error.outcome());
            assertEquals(0,engine.durabilityMetrics().currentSequence());
            assertNotEquals(AutomaticReplicationState.FAILED,engine.leadershipStatus().state());
            unchanged(before);assertFalse(Files.exists(root.resolve("node-1/recovery-floor.gsr")));
        }
        try(var local=open(1);var peer=open(2)) {
            assertFalse(local.quarantined());assertEquals(2,local.status().get("provenThrough"));
            peer.promise(promise(manifest,2));prove(peer,first);peer.checkpoint(application);
            local.establishRecoveryFloor(List.of(local.recoverySource(),peer.recoverySource()));local.cleanup();
        }
        byte[] floor=Files.readAllBytes(root.resolve("node-1/recovery-floor.gsr"));
        try(var engine=engine()) {
            engine.start().get(15,TimeUnit.SECONDS);engine.checkpoint().get(15,TimeUnit.SECONDS);
            engine.checkpoint().get(15,TimeUnit.SECONDS);
            assertEquals(2,engine.leadershipStatus().provenIndex());
            assertArrayEquals(floor,Files.readAllBytes(root.resolve("node-1/recovery-floor.gsr")));
        }
        try(var store=open(1)) {
            assertFalse(store.quarantined());assertEquals(2,AutomaticRecovery.index(store.currentSource().snapshot()));
        }
    }
}
