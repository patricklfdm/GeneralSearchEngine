package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual transferred descriptors, native journal and cold recovery. Historical
 * membership proofs use conditional fixtures; no autonomous quorum is claimed. */
class V53JoinedNativeOwnerTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53JoinedNativeCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerJoinedAdmissionTest helper(){var h=new V53LearnerJoinedAdmissionTest();h.temp=temp;return h;}
    MembershipGrantJournal reopen(V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.reopenJoined(f.local.summary,f.local.source.client,f.local.captured,f.local.config,cut);
    }
    Map<String,Object> ballot(V53LearnerCancellationTest.Fixture f,long counter) {
        var identity=f.local.config.localIdentity();return Map.of("counter",counter,"proposer",identity.nodeId().value(),"incarnation",identity.storageId().toString());
    }
    @Test void actualDescriptorAndChargesReachNativeCounterAndGrantAcrossColdOpen()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            MembershipFormat.Decoded grant;long counter;
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})) {
                    var before=f.local.source.client.usage();var events=new ArrayList<String>();
                    try(var nativeOwner=MembershipGrantJournal.openJoined(retired,f.local.captured,f.local.config,e->{
                        events.add(e);if(e.equals("JOINED_NATIVE_TRANSFERRED"))assertDoesNotThrow(()->new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock")));})) {
                        var usage=f.local.source.client.usage();assertEquals(1,usage.counts().get(MembershipResources.Unit.GENERATION));
                        assertEquals(1,usage.counts().get(MembershipResources.Unit.JOURNAL));assertEquals(1,usage.counts().get(MembershipResources.Unit.MISC));
                        assertFalse(usage.counts().containsKey(MembershipResources.Unit.LEARNER));assertTrue(usage.staging()<before.staging());
                        assertTrue(events.indexOf("JOINED_NATIVE_DECISION_FORCED")<events.indexOf("JOINED_NATIVE_TRANSFERRED"));
                        assertThrows(Exception.class,retired::check);assertThrows(Exception.class,joined::check);
                        retired.close();placement.close();f.typed.close();f.local.store.close();assertEquals(usage,f.local.source.client.usage());
                        counter=nativeOwner.reserveCounter();grant=nativeOwner.prepareCurrent(ballot(f,counter));assertEquals("BASIS",grant.kind());
                        assertEquals(f.local.config.localIdentity().nodeId().value(),grant.value().get("voter"));
                        assertFalse(Files.exists(f.local.config.replicaDirectory().resolve(MembershipBootstrapAdmissionData.FILE)));
                        new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock"));
                    }
                }
            }
            assertEquals(0,f.local.source.client.usage().leases());
            try(var nativeOwner=reopen(f,e->{})) {
                assertArrayEquals(grant.bytes(),nativeOwner.prepareCurrent(ballot(f,counter)).bytes());
                assertTrue(nativeOwner.reserveCounter()>counter);new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock"));
            }
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void forcedHandoffCutCanReopenButMissingCopiedAndChangedProofsCannot()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})) {
                    var usage=f.local.source.client.usage();var hit=new AtomicBoolean();
                    assertThrows(IOException.class,()->MembershipGrantJournal.openJoined(retired,f.local.captured,f.local.config,e->{if(e.equals("JOINED_NATIVE_DECISION_FORCED")){hit.set(true);throw new IOException(e);}}));
                    assertTrue(hit.get());assertEquals(usage,f.local.source.client.usage());retired.check();
                }
            }
            Path file=MembershipJoinedOwner.directory(f.local.summary).resolve(MembershipJoinedOwner.FILE),saved=temp.resolve("original-native");
            byte[] bytes=Files.readAllBytes(file);Files.move(file,saved);
            try {
                assertThrows(Exception.class,()->reopen(f,e->fail("missing native handoff")));assertFalse(Files.exists(file));
                Files.copy(saved,file);assertThrows(Exception.class,()->reopen(f,e->fail("copied native handoff")));Files.delete(file);
            }finally{Files.move(saved,file);}
            try{Files.write(file,Arrays.copyOf(bytes,bytes.length/2));assertThrows(Exception.class,()->reopen(f,e->fail("torn native handoff")));}
            finally{Files.write(file,bytes);}
            Path typed=f.local.typed().resolve(MembershipLearnerMaterialization.RECEIPT);byte[] receipt=Files.readAllBytes(typed);
            try{Files.writeString(typed,"changed");assertThrows(Exception.class,()->reopen(f,e->fail("changed typed proof")));}finally{Files.write(typed,receipt);}
            assertEquals(0,f.local.source.client.usage().leases());try(var nativeOwner=reopen(f,e->{})){assertTrue(nativeOwner.reserveCounter()>0);}
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void completedReplacementRecoversAfterTransferAndRejectsLiveProofMutationBeforeWriting()throws Exception {
        var fixtures=new V53LearnerIntentTest();fixtures.temp=temp;var h=helper();
        try(var f=fixtures.fixture("COMPLETED",5,"REPLACE",false)) {
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})) {
                    var hit=new AtomicBoolean();
                    assertThrows(IOException.class,()->MembershipGrantJournal.openJoined(retired,f.local.captured,f.local.config,e->{
                        if(e.equals("JOINED_NATIVE_TRANSFERRED")){hit.set(true);throw new IOException(e);}
                    }));assertTrue(hit.get());assertThrows(Exception.class,retired::check);
                }
            }
            assertEquals(0,f.local.source.client.usage().leases());
            long counter;MembershipFormat.Decoded basis;
            try(var owner=reopen(f,e->{})) {
                counter=owner.reserveCounter();basis=owner.prepareCurrent(ballot(f,counter));
                assertEquals("BASIS",basis.kind());
                Path proof=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerJoinedAdmission.FILE);
                byte[] bytes=Files.readAllBytes(proof);Files.writeString(proof,"changed");
                var before=V53ReplayFilesTest.files(f.local.config.replicaDirectory());
                assertThrows(Exception.class,owner::reserveCounter);
                assertEquals(before,V53ReplayFilesTest.files(f.local.config.replicaDirectory()));Files.write(proof,bytes);
            }
            try(var owner=reopen(f,e->{})){assertArrayEquals(basis.bytes(),owner.prepareCurrent(ballot(f,counter)).bytes());}
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void originalJoinedGrantSurvivesInterruptedCounterRecoveryWithoutBootstrapAuthority()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            long first;
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{});
                        var owner=MembershipGrantJournal.openJoined(retired,f.local.captured,f.local.config,e->{})){first=owner.reserveCounter();}
            }
            var hit=new AtomicBoolean();
            try(var owner=reopen(f,e->{if(e.equals("ALLOCATOR_FORCED")){hit.set(true);throw new IOException(e);}})) {
                assertThrows(IOException.class,owner::reserveCounter);assertTrue(hit.get());
            }
            try(var owner=reopen(f,e->{})){assertEquals(first+2,owner.reserveCounter());}
            assertEquals(0,f.local.source.client.usage().leases());
            var before=V53ReplayFilesTest.files(f.local.config.replicaDirectory());
            assertThrows(Exception.class,()->MembershipGrantJournal.openBootstrapped(f.local.config.replicaDirectory(),f.local.config.materialization().directory(),
                    f.local.config.root(),f.local.config.localIdentity(),f.local.source.client,MembershipGrantJournal.MAXIMUM,e->fail("joined proof is not bootstrap authority")));
            assertEquals(before,V53ReplayFilesTest.files(f.local.config.replicaDirectory()));assertEquals(0,f.local.source.client.usage().leases());
        }
    }
}
