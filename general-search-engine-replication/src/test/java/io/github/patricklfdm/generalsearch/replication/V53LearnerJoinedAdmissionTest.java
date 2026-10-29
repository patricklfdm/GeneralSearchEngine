package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed/INTENT/placement custody; historical quorum fixtures remain
 * conditional. Exception/cold-open cuts are not halt/SIGKILL qualification. */
class V53LearnerJoinedAdmissionTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo test){System.out.println("v53JoinedAdmissionCase="+test.getTestMethod().orElseThrow().getName());}
    V53LearnerCancellationTest.Fixture fixture()throws Exception {
        var helper=new V53LearnerIntentTest();helper.temp=temp;return helper.fixture("JOINT",3,"ADD",false);
    }
    MembershipLearnerPlacement place(V53LearnerCancellationTest.Fixture f)throws Exception {
        try(var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{})) {
            var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{});
            try{return MembershipLearnerPlacement.install(custody,e->{});}catch(Exception error){custody.close();throw error;}
        }
    }
    MembershipLearnerPlacement recover(V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipLearnerPlacement.recover(f.local.summary,f.local.source.client,f.local.captured,f.local.config,cut);
    }
    MembershipLearnerJoinedAdmission join(MembershipLearnerPlacement placement,V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipLearnerJoinedAdmission.install(placement,f.local.captured,f.local.config,cut);
    }
    @Test void actualInstalledOwnerForcesExactJoiningProofWithoutReleasingLocksOrChargingAgain()throws Exception {
        try(var f=fixture();var placement=place(f)) {
            var usage=f.local.source.client.usage();var receipt=placement.custody().receipt();var source=placement.custody().source();
            var joined=join(placement,f,e->{});joined.check();var value=object(parse(joined.originalRecord(),MembershipLearnerJoinedAdmission.MAXIMUM));
            assertEquals("gse-v53-joined-admission/1.3",value.get("schema"));assertEquals(f.local.summary.planDigest(),value.get("plan"));
            assertEquals(MembershipBootstrapSeed.identity(f.local.config.localIdentity()),value.get("identity"));
            assertArrayEquals(receipt.bytes(),MembershipBootstrapPlanData.unbase(value.get("receipt"),16384));
            var certificate=decode(MembershipBootstrapPlanData.unbase(value.get("certificate"),16384),"records","CERTIFICATE");
            var entry=decode(MembershipBootstrapPlanData.unbase(value.get("intent"),16384),"records","ENTRY");
            assertEquals(entry.digest(),certificate.value().get("entry"));assertEquals("INTENT",entry.value().get("kind"));
            assertEquals(hash(source.packet.bytes()),value.get("source"));assertEquals(source.context.cut,value.get("cut"));
            assertEquals(usage,f.local.source.client.usage());assertEquals(2,usage.counts().get(MembershipResources.Unit.GENERATION));
            Path record=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerJoinedAdmission.FILE);
            assertEquals(MembershipBasisSources.key(record).toString(),value.get("recordKey"));
            assertEquals(f.local.config.materialization().directory().toString(),object(value.get("materialization")).get("path"));
            var root=f.local.config.replicaDirectory().resolve("replica.lock");new V53MembershipOwnershipTest().probe(root);
            f.typed.close();f.local.store.close();joined.check();new V53MembershipOwnershipTest().probe(root);
            assertFalse(Files.exists(f.local.config.replicaDirectory().resolve(MembershipBootstrapAdmissionData.FILE)));
            assertThrows(Exception.class,()->MembershipBallotAllocator.openBootstrapped(f.local.config.replicaDirectory(),f.local.config.materialization().directory(),
                    f.local.config.root(),f.local.config.localIdentity(),e->fail("joined record cannot fabricate bootstrap admission")));
            joined.check();placement.close();assertThrows(Exception.class,joined::check);assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void originalAdmissionPrefixRecoversAcrossEveryWriteAndForceBoundary()throws Exception {
        try(var f=fixture()) {
            MembershipLearnerPlacement placement=place(f);Object originalKey=null;
            for(String event:List.of("LEARNER_PLACEMENT_CREATED:joined.json","LEARNER_PLACEMENT_PREFIX_WRITTEN:joined.json",
                    "LEARNER_PLACEMENT_WRITTEN:joined.json","LEARNER_PLACEMENT_FORCED:joined.json",
                    "LEARNER_PLACEMENT_RECORD_PARENT_FORCED:joined.json","LEARNER_JOINED_ADMISSION_FORCED")) {
                System.out.println("v53JoinedAdmissionCut="+event);var hit=new AtomicBoolean();var current=placement;
                try(current) {
                    assertThrows(IOException.class,()->join(current,f,e->{if(e.equals(event)){hit.set(true);throw new IOException(e);}}));
                    assertTrue(hit.get());Path record=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerJoinedAdmission.FILE);
                    Object key=MembershipBasisSources.key(record);if(originalKey==null)originalKey=key;else assertEquals(originalKey,key);
                }
                assertEquals(0,f.local.source.client.usage().leases());placement=recover(f,e->{});
            }
            try(var current=placement) {
                var joined=join(current,f,e->{});joined.check();
                assertEquals(originalKey,MembershipBasisSources.key(MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerJoinedAdmission.FILE)));
            }
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void foreignConfigurationCopiedRecordAndLastBoundaryCorruptionCannotAcquireAdmission()throws Exception {
        try(var f=fixture()) {
            Path record=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerJoinedAdmission.FILE);
            try(var placed=place(f)) {
                var old=f.local.config;var storage=old.materialization();
                var wrong=io.github.patricklfdm.generalsearch.durability.DurableStorageConfig.builder(temp.resolve("foreign-core"),storage.codec())
                        .format(storage.format()).storageIdentity(storage.storageIdentity()).schemaIdentity(storage.schemaIdentity())
                        .maxEncodedKeyBytes(storage.maxEncodedKeyBytes()).maxEncodedDocumentBytes(storage.maxEncodedDocumentBytes()).maxBulkElements(storage.maxBulkElements())
                        .maxDocuments(storage.maxDocuments()).checkpointWalBytes(storage.checkpointWalBytes()).maxRetainedBytes(storage.maxRetainedBytes()).maxDerivedStateBytes(storage.maxDerivedStateBytes()).build();
                var config=new MembershipReplicaConfig<>(old.root(),old.localIdentity(),List.of(),old.replicaDirectory(),wrong,old.bounds(),old.leadershipPolicy());
                var before=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
                assertThrows(Exception.class,()->MembershipLearnerJoinedAdmission.install(placed,f.local.captured,config,e->fail("foreign config must not write")));
                assertFalse(Files.exists(record));assertEquals(before,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));
                join(placed,f,e->{}).check();
            }
            Path saved=temp.resolve("original-joined");Files.move(record,saved);Files.copy(saved,record);
            byte[] copied=Files.readAllBytes(record);
            assertThrows(Exception.class,()->recover(f,e->fail("copied admission must not force")));
            assertArrayEquals(copied,Files.readAllBytes(record));assertEquals(0,f.local.source.client.usage().leases());
            Files.delete(record);Files.move(saved,record);
            try(var placed=recover(f,e->{})) {
                var hit=new AtomicBoolean();assertThrows(Exception.class,()->join(placed,f,e->{
                    if(e.equals("LEARNER_JOINED_ADMISSION_FORCED")){hit.set(true);Files.writeString(record,"changed-at-last-boundary");}
                }));assertTrue(hit.get());
            }
            assertEquals("changed-at-last-boundary",Files.readString(record));assertEquals(0,f.local.source.client.usage().leases());
            assertThrows(Exception.class,()->recover(f,e->fail("corrupt admission must not force")));
            assertEquals("changed-at-last-boundary",Files.readString(record));assertEquals(0,f.local.source.client.usage().leases());
        }
    }
}
