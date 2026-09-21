package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import java.nio.file.*;
import java.io.IOException;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class V51BootstrapTest {
    @TempDir Path root;
    @AfterEach void clear() { AdmissionIo.FAULTS.remove(); }
    static AutomaticReplicationBootstrapRequest<Integer,Doc> automatic(Path root,Path source) {
        var configs=configurations(root).stream().map(c -> new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),
                c.members(),c.replicaDirectory(),c.materialization(),c.bounds(),AutomaticLeadershipPolicy.forBounds(c.bounds()))).toList();
        return new AutomaticReplicationBootstrapRequest<>(source==null?ReplicationBootstrapSource.EMPTY:ReplicationBootstrapSource.VERIFIED_V44_BACKUP,
                source,configs,root.resolve("operation"),1L<<30,1L<<30);
    }
    private void cut(String point) { AdmissionIo.FAULTS.set(p -> { if(p.equals(point)) throw new IOException("test cut"); }); }
    @Test void emptyReadOnlyPlanCreatesThreeAdmissibleLocalSeals() throws Exception {
        var request=automatic(root,null); var plan=AutomaticReplicationStorageOperations.planBootstrap(builder(),request);
        assertEquals(plan,AutomaticReplicationStorageOperations.planBootstrap(builder(),request));
        try(var paths=Files.list(root)) { assertEquals(0,paths.count()); }
        var result=AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,plan);
        assertEquals(0,result.applicationSequence());
        assertEquals(result,AutomaticReplicationStorageOperations.readBootstrapResult(request.operationDirectory()));
        assertEquals(result,AutomaticReplicationStorageOperations.resumeBootstrap(builder(),request,plan));
        for(var c:request.replicas()) {
            assertFalse(Files.exists(c.materialization().directory()));
            var manifest=decode(Files.readAllBytes(c.replicaDirectory().resolve("manifest.gsr")),"MANIFEST");
            try(var store=AutomaticStore.open(c.replicaDirectory(),manifest.bytes(),c.localNodeId().value(),c.bounds(),AutomaticStore.Faults.NONE)) {
                assertEquals(1,number(store.promised().value(),"epoch"));
            }
        }
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.planCleanup(request.operationDirectory()));
        assertThrows(ReplicationException.class,() -> ReplicationStorageOperations.readBootstrapResult(request.operationDirectory()));
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicatedSearchEngines.builder(builder(),request.replicas().getFirst()).build());
    }
    @Test void importedFormatsPreserveSequenceIndexesDocumentOrderAndSourceBytes() throws Exception {
        for(int minor=0;minor<3;minor++) {
            Path dir=Files.createDirectory(root.resolve("v"+minor)),source=dir.resolve("source");
            var state=new DurableApplicationState<>(UUID.randomUUID(),41,List.of(new Doc(3,"shared"),new Doc(1,"shared")),List.of(IndexDefinition.equality(VALUE)));
            builder().writeDurableBackup(state,storage(dir.resolve("anchor"),minor),new DurableBackupRequest(source,1<<20));
            var before=AdmissionPaths.inventory(source,1<<20); var request=automatic(dir,source);
            var plan=AutomaticReplicationStorageOperations.planBootstrap(builder(),request);
            var result=AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,plan);
            assertEquals(41,result.applicationSequence()); assertNotEquals(state.history(),result.applicationHistory());
            assertEquals(before,AdmissionPaths.inventory(source,1<<20));
            var genesis=decode(Files.readAllBytes(dir.resolve("node-1/genesis.gsr")),"GENESIS");
            assertArrayEquals(AdmissionBootstrap.application(builder().configuration(),state.documents(),request.replicas().getFirst().materialization(),IMAGE),unbase(genesis.value().get("application")));
            try(var files=Files.list(source)) { for(Path p:files.toList()) Files.delete(p); } Files.delete(source);
            assertEquals(result,AutomaticReplicationStorageOperations.resumeBootstrap(builder(),request,plan));
        }
    }
    @Test void everyForceAndPublicationCutResumesExactlyOneDecision() throws Exception {
        var barriers=new ArrayList<String>(); Path baseline=Files.createDirectory(root.resolve("baseline"));
        var request=automatic(baseline,null); var plan=AutomaticReplicationStorageOperations.planBootstrap(builder(),request);
        AdmissionIo.FAULTS.set(barriers::add); AutomaticReplicationStorageOperations.applyBootstrap(builder(),request,plan); clear();
        assertTrue(barriers.size()>40);
        for(int i=0;i<barriers.size();i++) {
            var r=automatic(Files.createDirectory(root.resolve("cut-"+i)),null); var p=AutomaticReplicationStorageOperations.planBootstrap(builder(),r);
            cut(barriers.get(i)); assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyBootstrap(builder(),r,p),barriers.get(i)); clear();
            var result=AutomaticReplicationStorageOperations.resumeBootstrap(builder(),r,p);
            assertEquals(result,AutomaticReplicationStorageOperations.readBootstrapResult(r.operationDirectory()),barriers.get(i));
        }
    }
    @Test void cleanupEveryDeletionCutResumesAndNeverTouchesSource() throws Exception {
        var baseline=automatic(Files.createDirectory(root.resolve("baseline")),null);
        interrupted(baseline,"AUTO_BOOTSTRAP_PREPARED"); var expected=AutomaticReplicationStorageOperations.planCleanup(baseline.operationDirectory());
        for(int i=0;i<expected.deletePaths().size()-1;i++) {
            var r=automatic(Files.createDirectory(root.resolve("delete-"+i)),null); interrupted(r,"AUTO_BOOTSTRAP_PREPARED");
            var plan=AutomaticReplicationStorageOperations.planCleanup(r.operationDirectory());
            cut("AUTO_BOOTSTRAP_CLEANUP_DELETE_"+i); assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyCleanup(plan)); clear();
            assertEquals(plan,AutomaticReplicationStorageOperations.planCleanup(r.operationDirectory()));
            assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.resumeBootstrap(builder(),r,
                    new ReplicationBootstrapPlan(r.replicas().getFirst().groupId(),"config-v1",ReplicationBootstrapSource.EMPTY,null,r.replicas().stream().map(AutomaticReplicationGroupConfig::replicaDirectory).toList(),"wrong")));
            AutomaticReplicationStorageOperations.applyCleanup(plan);
            try(var paths=Files.list(r.operationDirectory().getParent())) { assertEquals(0,paths.count()); }
        }
    }
    static void interrupted(AutomaticReplicationBootstrapRequest<Integer,Doc> r,String barrier) {
        var p=AutomaticReplicationStorageOperations.planBootstrap(builder(),r);
        AdmissionIo.FAULTS.set(v -> { if(v.equals(barrier)) throw new IOException("test cut"); });
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyBootstrap(builder(),r,p)); AdmissionIo.FAULTS.remove();
    }
    @Test void cleanupRejectsUnknownMembersLiveOwnersAndAmbiguousDecision() throws Exception {
        var r=automatic(root,null); interrupted(r,"AUTO_BOOTSTRAP_PREPARED");
        var plan=AutomaticReplicationStorageOperations.planCleanup(r.operationDirectory());
        Path unknown=root.resolve("node-1/unknown"); Files.writeString(unknown,"keep");
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyCleanup(plan)); assertEquals("keep",Files.readString(unknown)); Files.delete(unknown);
        try(var owner=AdmissionPaths.own(root.resolve("node-1/replica.lock"),false)) {
            assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyCleanup(plan));
            assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.planCleanup(r.operationDirectory()));
        }
        Path journal=r.operationDirectory().resolve("operation.gsr"); var original=Files.readAllBytes(journal);
        Files.write(journal,new byte[]{71},StandardOpenOption.APPEND);
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.planCleanup(r.operationDirectory()));
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyCleanup(plan));
        Files.write(journal,original); AutomaticReplicationStorageOperations.applyCleanup(plan);
    }
    @Test void changedApplicationPathsPoliciesAndForgedSummariesRejectBeforeCreation() throws Exception {
        var r=automatic(root,null); var plan=AutomaticReplicationStorageOperations.planBootstrap(builder(),r);
        var configs=new ArrayList<>(r.replicas()); var c=configs.getFirst();
        configs.set(0,new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),c.members(),c.replicaDirectory(),
                storage(root.resolve("different"),1),c.bounds(),c.leadershipPolicy()));
        var changed=new AutomaticReplicationBootstrapRequest<>(r.source(),null,configs,r.operationDirectory(),r.maxSourceBytes(),r.maxOperationBytes());
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyBootstrap(builder(),changed,plan));
        assertFalse(Files.exists(r.operationDirectory()));
        Files.createDirectory(c.materialization().directory());
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.planBootstrap(builder(),r));
        Files.delete(c.materialization().directory());
        var wrong=new ReplicationBootstrapPlan(plan.groupId(),plan.configurationId(),plan.source(),null,plan.absentReplicaTargets(),"0".repeat(64));
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyBootstrap(builder(),r,wrong));
        assertFalse(Files.exists(r.operationDirectory()));
    }
    @Test void additiveCatalogMatchesReviewedSchemasWithoutChangingOriginalKinds() throws Exception {
        try(var input=getClass().getResourceAsStream("/replication/v51/bootstrap-catalog.json")) {
            var schema=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)));
            assertEquals(Set.of("BOOTSTRAP_BINDING","BOOTSTRAP_CLEANUP"),schema.keySet());
            for(var entry:schema.entrySet()) assertArrayEquals(canonical(entry.getValue()),canonical(CATALOG.get(entry.getKey())));
        }
    }
    @Test void parentReplacementAndSymlinksRejectBeforeCreatingAuthority() throws Exception {
        Path volume=Files.createDirectory(root.resolve("volume")); var r=automatic(volume,null);
        var plan=AutomaticReplicationStorageOperations.planBootstrap(builder(),r);
        Files.move(volume,root.resolve("old-volume")); Files.createDirectory(volume);
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.applyBootstrap(builder(),r,plan));
        assertFalse(Files.exists(r.operationDirectory())); Files.delete(volume); Files.createSymbolicLink(volume,root.resolve("old-volume"));
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.planBootstrap(builder(),r));
        try(var paths=Files.list(root.resolve("old-volume"))) { assertEquals(0,paths.count()); }
    }
    @Test void partialCommitRowIsNotCleanupAuthorityButExactResumeCanCompleteIt() throws Exception {
        var r=automatic(root,null); var summary=AutomaticReplicationStorageOperations.planBootstrap(builder(),r);
        interrupted(r,"AUTO_BOOTSTRAP_PREPARED"); var plan=AutomaticBootstrap.readPlan(r.operationDirectory());
        Files.write(r.operationDirectory().resolve("operation.gsr"),Arrays.copyOf(plan.row(3),57),StandardOpenOption.APPEND);
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.planCleanup(r.operationDirectory()));
        var result=AutomaticReplicationStorageOperations.resumeBootstrap(builder(),r,summary);
        assertEquals(result,AutomaticReplicationStorageOperations.readBootstrapResult(r.operationDirectory()));
    }
    @Test void prematureReceiptCannotAdvanceAnUncommittedDecision() throws Exception {
        var r=automatic(root,null); var summary=AutomaticReplicationStorageOperations.planBootstrap(builder(),r);
        interrupted(r,"AUTO_BOOTSTRAP_PREPARED"); var plan=AutomaticBootstrap.readPlan(r.operationDirectory());
        Files.write(r.operationDirectory().resolve("receipt.gsr"),plan.receipt());
        var before=AdmissionPaths.inventory(root,1<<30);
        assertThrows(AutomaticReplicationException.class,() -> AutomaticReplicationStorageOperations.resumeBootstrap(builder(),r,summary));
        assertEquals(before,AdmissionPaths.inventory(root,1<<30));
    }
}
