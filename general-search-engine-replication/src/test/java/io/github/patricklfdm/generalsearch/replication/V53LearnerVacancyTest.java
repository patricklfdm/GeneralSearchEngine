package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Original files and real typed decode with conditional voter histories.
 * Exception cuts are not a substitute for the deferred native process matrix. */
class V53LearnerVacancyTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerVacancyCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerSlotTest helper(){var helper=new V53LearnerSlotTest();helper.temp=temp;return helper;}
    MembershipLearnerSlot.View selected(V53LearnerMaterializationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        var helper=helper();
        try(var old=helper.current(f)) {
            var pending=helper.install(f,old.currentHead(),cut);
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                return typed.promoteSlot(old.currentHead());
            }
        }
    }
    @Test void durableVacancyFollowsParentForcesAndAvoidsPhantomColdGenerationCharges()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            var events=new ArrayList<String>();var current=selected(f,event->{events.add(event);
                if(event.equals("LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED"))assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                if(event.equals("LEARNER_SLOT_RETIRE_RELEASED"))assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
            });current.retirePredecessor();
            assertTrue(events.indexOf("LEARNER_SLOT_RETIRE_PARENTS_FORCED")<events.indexOf("LEARNER_SLOT_CLEAR_CANDIDATE_CREATED"));
            assertTrue(events.indexOf("LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED")<events.indexOf("LEARNER_SLOT_RETIRE_RELEASED"));
            Path cleared=MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.CLEARED);
            assertTrue(Files.isRegularFile(cleared));assertFalse(Files.exists(cleared.resolveSibling(MembershipLearnerSlot.CLEARED_NEXT)));
            f.store.close();assertEquals(0,f.source.client.usage().leases());
            try(var occupied=f.source.client.reserve(Unit.GENERATION,"unrelated-generation-probe",1)) {
                var before=V53ReplayFilesTest.files(f.base);
                f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{})) {
                    typed.currentHead().check();assertEquals(f.original,typed.state());
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                }
                assertEquals(before,V53ReplayFilesTest.files(f.base));f.store.close();assertEquals(1,f.source.client.usage().leases());
                // Absence by itself must not waive the original seed's charge.
                Path kept=f.base.resolve("kept-cleared.json");Files.move(cleared,kept);var unmarked=V53ReplayFilesTest.files(f.base);
                assertEquals("resource ownership/count",assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,e->{})).getMessage());
                assertEquals(unmarked,V53ReplayFilesTest.files(f.base));assertEquals(1,f.source.client.usage().leases());Files.move(kept,cleared);
            }
            assertEquals(0,f.source.client.usage().leases());assertTrue(MembershipLearnerSlot.METADATA_MAXIMUM<=Unit.MISC.bytes);
        }
    }
    @Test void completeCandidateAndUnforcedActiveMarkerResumeTheSameOriginalBeforeWaivingCharges()throws Exception {
        for(String point:List.of("LEARNER_SLOT_CLEAR_CANDIDATE_WRITTEN","LEARNER_SLOT_CLEAR_RENAMED")) {
            System.out.println("v53LearnerVacancyCut="+point);
            try(var f=helper().fixture(4,"REPLACE")) {
                var reached=new AtomicBoolean();var current=selected(f,event->{if(event.equals(point)){reached.set(true);throw new IOException(point);}});
                assertThrows(IOException.class,current::retirePredecessor);assertTrue(reached.get());
                assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                Path directory=MembershipLearnerSlot.directory(f.summary);
                Path original=directory.resolve(point.endsWith("WRITTEN")?MembershipLearnerSlot.CLEARED_NEXT:MembershipLearnerSlot.CLEARED);
                byte[] bytes=Files.readAllBytes(original);Object inode=MembershipBasisSources.key(original);
                f.store.close();
                try(var probe=f.source.client.reserve(Unit.GENERATION,"cold-vacancy-probe",1)) {
                    var events=new ArrayList<String>();f.store=MembershipLearnerStore.resume(f.summary,f.source.client,events::add);
                    assertArrayEquals(bytes,Files.readAllBytes(directory.resolve(MembershipLearnerSlot.CLEARED)));
                    assertEquals(inode,MembershipBasisSources.key(directory.resolve(MembershipLearnerSlot.CLEARED)));
                    assertFalse(Files.exists(directory.resolve(MembershipLearnerSlot.CLEARED_NEXT)));
                    assertTrue(events.indexOf("LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED")<events.indexOf("LEARNER_SLOT_INITIAL_RETIREMENT_FORCED"));
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{})) {
                        typed.currentHead().check();assertEquals(f.original,typed.state());
                    }
                    f.store.close();assertEquals(1,f.source.client.usage().leases());
                }
            }
        }
    }
    @Test void partialVacancyRefusesUnchangedBeforeAnyRecoveryForce()throws Exception {
        try(var f=helper().fixture(5,"REPLACE")) {
            var reached=new AtomicBoolean();var current=selected(f,event->{if(event.equals("LEARNER_SLOT_CLEAR_CANDIDATE_PREFIX_WRITTEN")){reached.set(true);throw new IOException(event);}});
            assertThrows(IOException.class,current::retirePredecessor);assertTrue(reached.get());f.store.close();
            var before=V53ReplayFilesTest.files(f.base);assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly));
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void copiedVacancyAndRecreatedOldRootsAreNeverAcceptedAsOriginalClearedState()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            selected(f,e->{}).retirePredecessor();f.store.close();
            Path marker=MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.CLEARED),kept=f.base.resolve("original-vacancy.json");
            byte[] original=Files.readAllBytes(marker);Object inode=MembershipBasisSources.key(marker);Files.move(marker,kept);Files.write(marker,original);
            assertNotEquals(inode,MembershipBasisSources.key(marker));var before=V53ReplayFilesTest.files(f.base);
            assertEquals("learner slot original vacancy inode changed",assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly)).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());Files.delete(marker);Files.move(kept,marker);
            for(Path path:List.of(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.SOURCE),MembershipLearnerSuccessor.typedDirectory(f.summary))) {
                Files.createDirectory(path);Files.write(path.resolve("foreign"),new byte[]{1});before=V53ReplayFilesTest.files(f.base);
                assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly));
                assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
                Files.delete(path.resolve("foreign"));Files.delete(path);
            }
        }
    }
    private void readOnly(String event){if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("invalid vacancy recovery wrote: "+event);}
}
