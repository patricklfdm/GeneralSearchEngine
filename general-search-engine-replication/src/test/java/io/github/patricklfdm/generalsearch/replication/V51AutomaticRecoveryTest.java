package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class V51AutomaticRecoveryTest {
    @TempDir Path root;
    byte[] manifest, genesis;
    @BeforeEach void initialize() throws Exception {manifest=setup(root);genesis=unbase(decode(Files.readAllBytes(root.resolve("node-1/genesis.gsr")),"GENESIS").value().get("application"));}
    AutomaticStore open(int node){return open(node,AutomaticStore.Faults.NONE);}
    AutomaticStore open(int node,AutomaticStore.Faults faults){return AutomaticStore.open(root.resolve("node-"+node),manifest,"node-"+node,ReplicationBounds.defaults(),faults);}
    Record m(){return decode(manifest,"MANIFEST");}
    byte[] value(int payload){return entry(manifest,1,null,1,new byte[]{(byte)payload});}
    void commit(AutomaticStore s,byte[] entry){s.promise(promise(manifest,2));s.accept(accept(manifest,entry,2));s.prove(proof(manifest,entry,2));}
    static AutomaticStore.Faults fail(String cut){return new AutomaticStore.Faults(){public void at(String event)throws java.io.IOException{if(event.equals(cut))throw new java.io.IOException("cut "+cut);}};}

    @Test void frozenBasisRetryNeverResamplesMutableStateAndStaleChunkFails() throws Exception {
        byte[] first=value(1);
        try(var s=open(1)){
            var basis=s.prepare(promise(manifest,2),"node-1",genesis);s.accept(accept(manifest,first,2));
            var retry=s.prepare(promise(manifest,2),"node-1",new byte[]{99});assertArrayEquals(basis.record().bytes(),retry.record().bytes());assertNull(retry.image().accepted());
            assertArrayEquals(Arrays.copyOf(basis.image().encoded().bytes(),31),s.basisChunk("node-1",text(basis.record().value(),"basisId"),0,31));
            s.promise(promise(manifest,5));assertThrows(AutomaticReplicationException.class,()->s.basisChunk("node-1",text(basis.record().value(),"basisId"),0,31));
        }
        try(var s=open(1)){assertEquals(5L,s.status().get("promisedEpoch"));assertArrayEquals(first,s.acceptedEntry(1));}
    }
    @Test void incompleteBasisAfterForcedPromiseRequiresHigherBallot() {
        try(var s=open(1,fail("BASIS_IMAGE_AFTER_FORCE"))){assertThrows(AutomaticReplicationException.class,()->s.prepare(promise(manifest,2),"node-1",genesis));}
        try(var s=open(1)){assertEquals(2L,s.status().get("promisedEpoch"));assertThrows(AutomaticReplicationException.class,()->s.prepare(promise(manifest,2),"node-1",genesis));}
        try(var s=open(1)){assertNotNull(s.prepare(promise(manifest,5),"node-1",genesis));}
    }
    @Test void copiedPeerBasisCannotBecomeALocalPrepareResponse() throws Exception {
        try(var a=open(1);var b=open(2)){a.prepare(promise(manifest,2),"node-1",genesis);var remote=b.prepare(promise(manifest,2),"node-1",genesis);
            Files.write(root.resolve("node-1/basis/node-1/basis.gsr"),remote.record().bytes());Files.write(root.resolve("node-1/basis/node-1/image.gsr"),remote.image().encoded().bytes());
            assertThrows(AutomaticReplicationException.class,()->a.prepare(promise(manifest,2),"node-1",genesis));}
    }
    @Test void selectsAcceptanceBallotPreservesOriginAndReplacesOnlyAfterSelectionForce() throws Exception {
        byte[] minority=value(1),chosen=value(2);AutomaticRecovery.Selection selected;
        try(var a=open(1);var b=open(2)){
            a.promise(promise(manifest,2));a.accept(accept(manifest,minority,2));
            b.promise(promise(manifest,3));b.accept(accept(manifest,chosen,3));
            var left=a.prepare(promise(manifest,5),"node-1",genesis);var right=b.prepare(promise(manifest,5),"node-1",genesis);
            selected=a.select(List.of(left,right));assertArrayEquals(chosen,unbase(selected.record().value().get("nextEntry")));
            assertEquals(3L,number(object(selected.record().value().get("sourceBallot")),"epoch"));
            a.installSelected();assertArrayEquals(minority,a.acceptedEntry(1)); // selection is not a vote
        }
        try(var a=open(1,fail("ACCEPT_BEFORE_WRITE"))){assertThrows(AutomaticReplicationException.class,()->a.accept(accept(manifest,chosen,5)));}
        try(var a=open(1)){assertArrayEquals(minority,a.acceptedEntry(1));a.accept(accept(manifest,chosen,5));a.prove(proof(manifest,chosen,5));}
        try(var a=open(1)){assertArrayEquals(chosen,a.acceptedEntry(1));assertEquals(2L,number(decode(a.acceptedEntry(1),"ENTRY").value(),"originEpoch"));assertEquals(1,a.status().get("provenThrough"));}
    }
    @Test void equalBallotConflictsAndMixedBasisIdentityReject() {
        try(var a=open(1);var b=open(2)){
            for(var s:List.of(a,b))s.promise(promise(manifest,2));a.accept(accept(manifest,value(1),2));b.accept(accept(manifest,value(2),2));
            var left=a.prepare(promise(manifest,5),"node-1",genesis);var right=b.prepare(promise(manifest,5),"node-1",genesis);
            assertThrows(AutomaticReplicationException.class,()->AutomaticRecovery.select(m(),object(left.record().value().get("ballot")),List.of(left,right)));
            assertThrows(AutomaticReplicationException.class,()->AutomaticRecovery.Basis.read(left.record().bytes(),right.image().encoded().bytes(),m()));
            assertThrows(AutomaticReplicationException.class,()->AutomaticRecovery.select(m(),object(left.record().value().get("ballot")),List.of(left,left)));
        }
    }
    @Test void higherCampaignRetainsPreviouslySelectedButUnprovenVote() {
        byte[] minority=value(1),chosen=value(2);
        try(var a=open(1);var b=open(2)){
            a.promise(promise(manifest,2));a.accept(accept(manifest,minority,2));b.promise(promise(manifest,3));b.accept(accept(manifest,chosen,3));
            a.select(List.of(a.prepare(promise(manifest,5),"node-1",genesis),b.prepare(promise(manifest,5),"node-1",genesis)));
            a.installSelected();a.accept(accept(manifest,chosen,5));
            a.select(List.of(a.prepare(promise(manifest,8),"node-1",genesis),b.prepare(promise(manifest,8),"node-1",genesis)));
        }
        try(var a=open(1)){assertArrayEquals(chosen,a.acceptedEntry(1));a.accept(accept(manifest,chosen,8));a.prove(proof(manifest,chosen,8));}
        try(var a=open(1)){assertEquals(1,a.status().get("provenThrough"));}
    }
    @Test void selectedDecisionCannotBeChangedAtSameBallotAndItsEvidenceIsMandatory() throws Exception {
        try(var a=open(1);var b=open(2);var c=open(3)){
            var x=a.prepare(promise(manifest,2),"node-1",genesis);var y=b.prepare(promise(manifest,2),"node-1",genesis);var z=c.prepare(promise(manifest,2),"node-1",genesis);
            a.select(List.of(x,y));a.select(List.of(x,y));assertThrows(AutomaticReplicationException.class,()->a.select(List.of(x,z)));
        }
        Files.delete(root.resolve("node-1/transfer/selection-a/image-node-2.gsr"));assertThrows(AutomaticReplicationException.class,()->open(1));
    }
    @Test void corruptRemoteSourceSuffixCannotAuthorizeDeletion() {
        try(var a=open(1)){commit(a,value(1));a.checkpoint(new byte[]{1});var source=a.recoverySource();var files=source.files();byte[] ledger=files.get("accepted.gsr");files.put("accepted.gsr",Arrays.copyOf(ledger,ledger.length+7));
            assertThrows(AutomaticReplicationException.class,()->AutomaticRecoveryFiles.Source.read(files,m()));
            var wrongBase=source.files();var snapshot=copy(source.snapshot().value());snapshot.put("baseSequence",1L);snapshot.put("applicationSequence",2L);
            wrongBase.put("snapshot.gsr",encode("SNAPSHOT",snapshot));
            var error=assertThrows(AutomaticReplicationException.class,()->AutomaticRecoveryFiles.Source.read(wrongBase,m()));assertEquals("source genesis sequence",error.getMessage());}
    }
    @Test void higherAcceptedTailIsNotDeletedByAnOlderTwoSourceFloor() throws Exception {
        try(var a=open(1);var b=open(2)){
            for(var s:List.of(a,b))commit(s,value(1));byte[] second=entry(manifest,2,value(1),1,new byte[]{2});a.accept(accept(manifest,second,2));
            for(var s:List.of(a,b))s.checkpoint(new byte[]{1});a.establishRecoveryFloor(List.of(a.recoverySource(),b.recoverySource()));
            byte[] before=Files.readAllBytes(root.resolve("node-1/accepted.gsr"));assertThrows(AutomaticReplicationException.class,a::cleanup);assertArrayEquals(before,Files.readAllBytes(root.resolve("node-1/accepted.gsr")));
        }
        try(var a=open(1)){assertEquals(2,a.status().get("acceptedThrough"));assertEquals(1,a.status().get("provenThrough"));}
    }
    @Test void highestOriginDoesNotOverrideHigherAcceptanceBallot() {
        byte[] carried=value(1);var fresh=copy(decode(value(2),"ENTRY").value());fresh.put("originEpoch",5L);byte[] newerOrigin=encode("ENTRY",fresh);
        try(var a=open(1);var b=open(2)){
            a.promise(promise(manifest,8));a.accept(accept(manifest,carried,8));b.promise(promise(manifest,5));b.accept(accept(manifest,newerOrigin,5));
            var x=a.prepare(promise(manifest,11),"node-1",genesis);var y=b.prepare(promise(manifest,11),"node-1",genesis);
            assertArrayEquals(carried,unbase(a.select(List.of(x,y)).record().value().get("nextEntry")));
        }
    }
    @Test void provenPrefixWinsOverObsoleteMinorityTail() {
        try(var a=open(1);var b=open(2)){
            commit(a,value(1));b.promise(promise(manifest,2));b.accept(accept(manifest,value(2),2));
            var x=a.prepare(promise(manifest,5),"node-1",new byte[]{1});var y=b.prepare(promise(manifest,5),"node-1",genesis);
            var decision=b.select(List.of(x,y));assertEquals(1,AutomaticRecovery.index(decision.snapshot()));assertNull(decision.sourceAcceptance());b.installSelected();assertEquals(1,b.status().get("provenThrough"));
        }
        try(var b=open(2)){assertEquals(5L,b.status().get("promisedEpoch"));assertEquals(1,b.status().get("provenThrough"));assertEquals(1L,b.status().get("applicationSequence"));}
    }
    @Test void foreignProvenPrefixAndChangedSameBallotSelectionFailClosed() {
        try(var a=open(1);var b=open(2)){
            commit(a,value(1));commit(b,value(2));var x=a.prepare(promise(manifest,5),"node-1",new byte[]{1});var y=b.prepare(promise(manifest,5),"node-1",new byte[]{2});
            assertThrows(AutomaticReplicationException.class,()->a.select(List.of(x,y)));
        }
    }
    @Test void localCheckpointCannotAuthorizeDeletionAndRootPromiseSurvives() throws Exception {
        byte[] promiseBytes;
        try(var a=open(1)){commit(a,value(1));a.promise(promise(manifest,8));promiseBytes=Files.readAllBytes(root.resolve("node-1/promises.gsr"));a.checkpoint(new byte[]{1});assertThrows(AutomaticReplicationException.class,a::cleanup);}
        try(var a=open(1)){assertEquals(8L,a.status().get("promisedEpoch"));assertEquals(1,a.status().get("provenThrough"));assertArrayEquals(promiseBytes,Files.readAllBytes(root.resolve("node-1/promises.gsr")));}
    }
    @Test void twoCompleteSourcesPermitRetirementButMissingSourceEvidenceRejectsReopen() throws Exception {
        try(var a=open(1);var b=open(2)){
            for(var s:List.of(a,b)){commit(s,value(1));s.checkpoint(new byte[]{1});}
            var sources=List.of(a.recoverySource(),b.recoverySource());a.establishRecoveryFloor(sources);a.cleanup();
            assertTrue(Files.size(root.resolve("node-1/accepted.gsr"))<Files.size(root.resolve("node-1/generation-a/accepted.gsr"))+300);
        }
        try(var a=open(1)){assertEquals(1,a.status().get("provenThrough"));}
        Files.delete(root.resolve("node-1/transfer/floor-a/node-2/snapshot.gsr"));assertThrows(AutomaticReplicationException.class,()->open(1));
    }
    @Test void sameVoterOrDifferentCutCannotBecomeDurableFloor() {
        try(var a=open(1);var b=open(2)){
            commit(a,value(1));a.checkpoint(new byte[]{1});b.checkpoint(genesis);var x=a.recoverySource();var y=b.recoverySource();
            assertThrows(AutomaticReplicationException.class,()->a.establishRecoveryFloor(List.of(x,x)));
            assertThrows(AutomaticReplicationException.class,()->b.establishRecoveryFloor(List.of(x,y)));
        }
    }
    @Test void deletionCanResumeFromExactRetirementInventory() throws Exception {
        try(var a=open(1);var b=open(2)){
            for(var s:List.of(a,b)){commit(s,value(1));s.checkpoint(new byte[]{1});s.checkpoint(new byte[]{1});}
            a.establishRecoveryFloor(List.of(a.recoverySource(),b.recoverySource()));
        }
        try(var a=open(1,fail("DELETE_AFTER_FILE"))){assertThrows(AutomaticReplicationException.class,a::cleanup);}
        try(var a=open(1)){assertEquals(1,a.status().get("provenThrough"));a.cleanup();}
        assertFalse(Files.exists(root.resolve("node-1/generation-a")));
        try(var a=open(1)){assertEquals(2L,a.status().get("promisedEpoch"));}
    }
    @ParameterizedTest @ValueSource(strings={"DELETE_AFTER_DIRECTORY","DELETE_AFTER_ROOT_TRUNCATE"})
    void removedDirectoryIsNotReusableUntilRetirementFinishes(String cut) throws Exception {
        try(var a=open(1);var b=open(2)) {
            for(var s:List.of(a,b)){commit(s,value(1));s.checkpoint(new byte[]{1});s.checkpoint(new byte[]{1});}
            a.establishRecoveryFloor(List.of(a.recoverySource(),b.recoverySource()));
        }
        try(var a=open(1,fail(cut))){assertThrows(AutomaticReplicationException.class,a::cleanup);}
        assertFalse(Files.exists(root.resolve("node-1/generation-a")));
        assertTrue(Files.exists(root.resolve("node-1/transfer/retiring/generation.gsr")));
        try(var a=open(1)) {
            byte[] next=entry(manifest,2,value(1),9,new byte[0]);
            a.accept(accept(manifest,next,2));a.prove(proof(manifest,next,2));
            var snapshot=a.provenSnapshot(new byte[]{1});
            assertFalse(a.generationAvailable(snapshot));
            var error=assertThrows(AutomaticReplicationException.class,()->a.installProven(snapshot));
            assertEquals(AutomaticReplicationException.Reason.CAPACITY_EXCEEDED,error.reason());
            assertFalse(a.quarantined());assertFalse(Files.exists(root.resolve("node-1/generation-a")));
            a.cleanup();assertTrue(a.generationAvailable(snapshot));a.installProven(snapshot);
            assertEquals(2,AutomaticRecovery.index(a.currentSource().snapshot()));
        }
        try(var a=open(1)){assertEquals(2,a.status().get("provenThrough"));}
    }
    @Test void selectorNeverFallsBackToOldRootWhenActiveGenerationMissing() throws Exception {
        try(var a=open(1)){commit(a,value(1));a.checkpoint(new byte[]{1});}
        Files.delete(root.resolve("node-1/generation-a/snapshot.gsr"));assertThrows(AutomaticReplicationException.class,()->open(1));
    }
    @ParameterizedTest @ValueSource(strings={"GENERATION_ACCEPTED_WRITE_CHUNK","GENERATION_ACCEPTED_AFTER_FORCE","GENERATION_PROOFS_WRITE_CHUNK","GENERATION_SNAPSHOT_WRITE_CHUNK","GENERATION_SNAPSHOT_AFTER_FORCE","GENERATION_SEAL_WRITE_CHUNK","GENERATION_SEAL_AFTER_FORCE","SELECTOR_AFTER_FORCE"})
    void startupResumesOnlyTheExactInitialCheckpoint(String cut) throws Exception {
        for(boolean restored:List.of(false,true)) {
            Path scenario=Files.createDirectory(root.resolve(cut+"-"+restored));byte[] localManifest=setup(scenario);
            byte[] first=entry(localManifest,1,null,1,new byte[]{1});
            byte[] tail=entry(localManifest,2,first,1,new byte[]{2});
            var fault=new AutomaticStore.Faults() {
                public int maximumWriteBytes(){return cut.endsWith("_WRITE_CHUNK")?7:Integer.MAX_VALUE;}
                public void at(String event)throws java.io.IOException {if(event.equals(cut))throw new java.io.IOException("cut "+cut);}
            };
            try(var store=AutomaticStore.open(scenario.resolve("node-1"),localManifest,"node-1",ReplicationBounds.defaults(),fault)) {
                store.promise(promise(localManifest,2));store.accept(accept(localManifest,first,2));store.prove(proof(localManifest,first,2));
                store.accept(accept(localManifest,tail,2));
                assertThrows(AutomaticReplicationException.class,()->store.checkpoint(new byte[]{1}));
            }
            byte[] promises=Files.readAllBytes(scenario.resolve("node-1/promises.gsr"));
            try(var store=AutomaticStore.open(scenario.resolve("node-1"),localManifest,"node-1",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE)) {
                assertNull(store.currentSource());var protocol=new AutomaticProtocol(store,()->0,java.util.UUID::randomUUID);
                if(restored)protocol.restored(new byte[]{1});
                protocol.start(0);
                if(!restored) {
                    var rebuild=(AutomaticProtocol.Reconstruct)protocol.drain().getFirst();
                    protocol.reconstructed(rebuild.id(),new byte[]{1},null,0);
                }
                assertEquals(AutomaticReplicationState.FOLLOWER,protocol.view().state());
                assertNotNull(store.currentSource(),"unpublished first checkpoint must not pin the recovery slot forever");
                assertEquals(1,AutomaticRecovery.index(store.currentSource().snapshot()));
                assertArrayEquals(tail,store.acceptedEntry(2));
                assertArrayEquals(promises,Files.readAllBytes(scenario.resolve("node-1/promises.gsr")));
                assertFalse(Files.exists(scenario.resolve("node-1/recovery-floor.gsr")),"resumption cannot authorize retirement");
            }
        }
    }
    @Test void startupDoesNotRewriteAnUnrelatedUnpublishedSnapshot() throws Exception {
        try(var store=open(1,fail("GENERATION_SNAPSHOT_AFTER_FORCE"))) {
            commit(store,value(1));assertThrows(AutomaticReplicationException.class,()->store.checkpoint(new byte[]{1}));
        }
        Path path=root.resolve("node-1/generation-a/snapshot.gsr");byte[] before=Files.readAllBytes(path);
        try(var store=open(1)) {
            var protocol=new AutomaticProtocol(store,()->0,java.util.UUID::randomUUID);
            protocol.restored(new byte[]{2});protocol.start(0);
            assertNull(store.currentSource());assertArrayEquals(before,Files.readAllBytes(path));
            assertThrows(AutomaticReplicationException.class,()->store.checkpoint(new byte[]{2}));
            assertArrayEquals(before,Files.readAllBytes(path));
        }
    }
    @Test void selectorPublicationChoosesCompleteOldOrNewAuthority() {
        try(var a=open(1,fail("SELECTOR_AFTER_FORCE"))){commit(a,value(1));assertThrows(AutomaticReplicationException.class,()->a.checkpoint(new byte[]{1}));}
        try(var a=open(1)){assertEquals(1,a.status().get("provenThrough"));assertArrayEquals(value(1),a.acceptedEntry(1));a.checkpoint(new byte[]{1});}
        try(var a=open(1)){assertEquals(1,a.status().get("provenThrough"));assertThrows(AutomaticReplicationException.class,()->a.acceptedEntry(1));}
    }
    @Test void firstVoteAfterSelectorCutForcesFallbackMarkerBeforeAccepting() throws Exception {
        try(var a=open(1,fail("SELECTOR_AFTER_RENAME"))){commit(a,value(1));assertThrows(AutomaticReplicationException.class,()->a.checkpoint(new byte[]{1}));}
        assertFalse(Files.exists(root.resolve("node-1/generation-started.gsr")));
        try(var a=open(1)){byte[] next=entry(manifest,2,value(1),9,new byte[0]);a.accept(accept(manifest,next,2));}
        assertTrue(Files.isRegularFile(root.resolve("node-1/generation-started.gsr")));
        Files.delete(root.resolve("node-1/current.gsr"));assertThrows(AutomaticReplicationException.class,()->open(1));
    }
    @Test void transferProgressRetriesAndRestartBindExactImage() throws Exception {
        byte[] image;String id="33333333-3333-3333-3333-333333333333";
        try(var a=open(1)){var basis=a.prepare(promise(manifest,2),"node-1",genesis);image=basis.image().encoded().bytes();a.beginTransfer(transfer(image,id));assertEquals(19,a.transferChunk(id,0,Arrays.copyOf(image,19)));assertEquals(19,a.transferChunk(id,0,Arrays.copyOf(image,19)));}
        try(var a=open(1,fail("TRANSFER_DATA_AFTER_FORCE"))){assertThrows(AutomaticReplicationException.class,()->a.transferChunk(id,19,Arrays.copyOfRange(image,19,image.length)));}
        try(var a=open(1)){assertEquals(image.length,a.transferChunk(id,19,Arrays.copyOfRange(image,19,image.length)));assertArrayEquals(image,a.completeTransfer(id).encoded().bytes());}
    }
    @Test void transferRejectsWrongOffsetOrIdentityWithoutPromotingPartialBytes() {
        try(var a=open(1)){byte[] image=a.prepare(promise(manifest,2),"node-1",genesis).image().encoded().bytes();String id="33333333-3333-3333-3333-333333333333";a.beginTransfer(transfer(image,id));assertThrows(AutomaticReplicationException.class,()->a.transferChunk(id,1,new byte[]{0}));}
        try(var a=open(1)){assertEquals(2L,a.status().get("promisedEpoch"));}
    }
    @Test void cannotForceAnAcceptanceTooLargeForTheFrozenBasisDescriptor() throws Exception {
        try(var a=open(1)){a.promise(promise(manifest,2));byte[] before=Files.readAllBytes(root.resolve("node-1/accepted.gsr"));
            byte[] large=entry(manifest,1,null,1,new byte[100_000]);
            var error=assertThrows(AutomaticReplicationException.class,()->a.accept(accept(manifest,large,2)));
            assertEquals(AutomaticReplicationException.Reason.CAPACITY_EXCEEDED,error.reason());assertEquals(0,a.status().get("acceptedThrough"));assertArrayEquals(before,Files.readAllBytes(root.resolve("node-1/accepted.gsr")));}
    }
    private byte[] transfer(byte[] image,String id){return encode("TRANSFER",Map.of("manifestDigest",digest(manifest),"node","node-1","ballot",AutomaticRecovery.ballotOf(decode(promise(manifest,2),"PROMISE")),"imageBytes",(long)image.length,"imageDigest",digest(image),"transferId",id,"receivedBytes",0L));}
}
