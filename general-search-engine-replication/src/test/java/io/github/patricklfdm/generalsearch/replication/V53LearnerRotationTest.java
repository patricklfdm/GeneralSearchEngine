package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Conditional voter fixtures, actual retained generations and core decoding.
 * Selector/clear exception cuts do not replace the deferred process matrix. */
class V53LearnerRotationTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerRotationCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerReuseTest helper(){var h=new V53LearnerReuseTest();h.temp=temp;return h;}
    MembershipLearnerSlot.View rotate(V53LearnerMaterializationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        var h=helper();h.select(f);
        try(var old=h.current(f)) {
            var pending=h.helper().install(f,old.currentHead(),cut);
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                var selected=typed.promoteSlot(old.currentHead());assertThrows(IllegalArgumentException.class,old::currentHead);assertThrows(IllegalArgumentException.class,pending::source);return selected;
            }
        }
    }
    @Test void selectingReusedARevokesBAndReclaimsOnlyCoveredBFilesBeforeColdTypedReopen()throws Exception {
        try(var f=helper().helper().fixture(3,"ADD")) {
            var events=new ArrayList<String>();var selected=rotate(f,e->{events.add(e);
                if(e.equals("LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED"))assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                if(e.equals("LEARNER_SLOT_RETIRE_RELEASED"))assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
            });
            assertEquals(MembershipLearnerSuccessor.typedDirectory(f.summary),selected.typedDirectory());
            assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));selected.retirePredecessor();
            Path root=MembershipLearnerSlot.directory(f.summary),head=root.resolve(MembershipLearnerSlot.HEAD),clear=root.resolve(MembershipLearnerSlot.CLEARED);
            byte[] headBytes=Files.readAllBytes(head),clearBytes=Files.readAllBytes(clear);Object headKey=MembershipBasisSources.key(head),clearKey=MembershipBasisSources.key(clear);
            assertFalse(Files.exists(root.resolve(MembershipLearnerSlot.SOURCE)));assertFalse(Files.exists(MembershipLearnerSlot.typedDirectory(f.summary)));
            assertTrue(Files.exists(root.resolve("b.json")));assertTrue(Files.exists(root.resolve("b.installed.json")));
            assertTrue(events.indexOf("LEARNER_SLOT_ROLLING_HEAD_RENAMED")<events.indexOf("LEARNER_SLOT_RETIRE_BEFORE_DELETE"));
            assertTrue(events.indexOf("LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED")<events.indexOf("LEARNER_SLOT_RETIRE_RELEASED"));
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            try(var probe=f.source.client.reserve(Unit.GENERATION,"cold-selected-a-probe",1)) {
                f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{});
                try(var current=helper().current(f)) {
                    current.currentHead().check();assertEquals(f.original,current.state());assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                }
                assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(headKey,MembershipBasisSources.key(head));assertEquals(clearKey,MembershipBasisSources.key(clear));
                assertArrayEquals(headBytes,Files.readAllBytes(head));assertArrayEquals(clearBytes,Files.readAllBytes(clear));f.store.close();assertEquals(1,f.source.client.usage().leases());
            }
            // A copied selector cannot authorize even a no-op cold retirement.
            Path kept=f.base.resolve("kept-rolling-head");Files.move(head,kept);Files.copy(kept,head);before=V53ReplayFilesTest.files(f.base);
            assertEquals("learner slot original head inode changed",assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly)).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
            Files.delete(head);Files.move(kept,head);
            Path duplicate=root.resolve("b.next.json");Files.copy(root.resolve("b.json"),duplicate);before=V53ReplayFilesTest.files(f.base);
            assertEquals("learner retired plan has unbound candidate",assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly)).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());Files.delete(duplicate);
            for(Path recreated:List.of(root.resolve(MembershipLearnerSlot.SOURCE),MembershipLearnerSlot.typedDirectory(f.summary))) {
                Files.createDirectory(recreated);Files.write(recreated.resolve("foreign"),new byte[]{1});before=V53ReplayFilesTest.files(f.base);
                assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly));
                assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
                Files.delete(recreated.resolve("foreign"));Files.delete(recreated);
            }
        }
    }
    @Test void completeRollingCandidateAndRenamedHeadRecoverTheirDistinctOriginalStates()throws Exception {
        for(String cut:List.of("LEARNER_SLOT_ROLLING_HEAD_CANDIDATE_WRITTEN","LEARNER_SLOT_ROLLING_HEAD_RENAMED")) {
            System.out.println("v53LearnerRotationCut="+cut);
            try(var f=helper().helper().fixture(4,"REPLACE")) {
                var reached=new AtomicBoolean();assertThrows(IOException.class,()->rotate(f,e->{if(e.equals(cut)){reached.set(true);throw new IOException(e);}}));assertTrue(reached.get());
                Path root=MembershipLearnerSlot.directory(f.summary),original=root.resolve(cut.endsWith("WRITTEN")?MembershipLearnerSlot.HEAD_NEXT:MembershipLearnerSlot.HEAD);
                Object inode=MembershipBasisSources.key(original);byte[] bytes=Files.readAllBytes(original);f.store.close();
                f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{});
                if(cut.endsWith("WRITTEN"))try(var current=helper().current(f)) {
                    assertEquals(MembershipLearnerSlot.typedDirectory(f.summary),f.store.currentSource().typedDirectory());
                    var pending=f.store.resumeSlot(current.currentHead());
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {typed.promoteSlot(current.currentHead()).retirePredecessor();}
                }
                assertEquals(inode,MembershipBasisSources.key(root.resolve(MembershipLearnerSlot.HEAD)));assertArrayEquals(bytes,Files.readAllBytes(root.resolve(MembershipLearnerSlot.HEAD)));
                assertFalse(Files.exists(root.resolve(MembershipLearnerSlot.HEAD_NEXT)));
                try(var current=helper().current(f)){current.currentHead().check();assertEquals(f.original,current.state());}
                assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
            }
        }
    }
    @Test void partialRollingCandidateRefusesWithoutRecoveryWritesOrDiscardingEitherImage()throws Exception {
        try(var f=helper().helper().fixture(5,"REPLACE")) {
            var reached=new AtomicBoolean();assertThrows(IOException.class,()->rotate(f,e->{if(e.equals("LEARNER_SLOT_ROLLING_HEAD_CANDIDATE_PREFIX_WRITTEN")){reached.set(true);throw new IOException(e);}}));assertTrue(reached.get());
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly));
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    private void readOnly(String event){if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("invalid rolling recovery forced: "+event);}
}
