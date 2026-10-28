package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Conditional original history, real core decoding and forced handoff files.
 * Physical retirement and native/crash matrices are separate qualifications. */
class V53LearnerHandoffTest {
    @TempDir Path temp;
    V53LearnerSuccessorTest helper(){var h=new V53LearnerSuccessorTest();h.temp=temp;return h;}
    @Test void forcedHeadClosesOldHandlesAndReopensWithoutDependingOnThem()throws Exception {
        var h=helper();try(var f=h.fixture(3,"ADD")) {
            byte[] packet;var events=new ArrayList<String>();
            try(var prior=f.prepare(e->{})) {
                var old=prior.retainGeneration();var installed=h.install(f,old,events::add);
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,1),f.captured,f.config,e->{})) {
                    var files=V53ReplayFilesTest.files(f.base);var usage=f.source.client.usage();packet=installed.source().packet.bytes();
                    var promoted=typed.promoteSuccessor();assertTrue(prior.closed());assertTrue(typed.closed());
                    assertThrows(IllegalArgumentException.class,old::source);assertThrows(IllegalArgumentException.class,installed::source);
                    assertArrayEquals(packet,promoted.source().packet.bytes());assertEquals(usage,f.source.client.usage());
                    var after=V53ReplayFilesTest.files(f.base);
                    for(var row:files.entrySet())assertEquals(row.getValue(),after.get(row.getKey()));
                    assertEquals(2,usage.counts().get(Unit.GENERATION));assertEquals(4,usage.counts().get(Unit.APPLICATION));
                    assertTrue(events.indexOf("LEARNER_HEAD_CANDIDATE_PARENT_FORCED")<events.indexOf("LEARNER_HEAD_RENAMED"));
                    assertTrue(events.indexOf("LEARNER_HEAD_ACTIVE_PARENT_FORCED")<events.indexOf("LEARNER_HEAD_BEFORE_RETURN"));
                    assertTrue(Files.size(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.HEAD))<=4096);
                }
            }
            var before=V53ReplayFilesTest.files(f.base);f.reopen();var promoted=f.store.promotedSuccessor();
            assertArrayEquals(packet,promoted.source().packet.bytes());
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(promoted,1),f.captured,f.config,e->{})) {
                assertEquals(f.original,typed.state());assertThrows(IllegalArgumentException.class,typed::promoteSuccessor);
            }
            assertEquals(before,V53ReplayFilesTest.files(f.base));
            // This handoff deliberately retains original files until bounded
            // retirement is implemented. Changing an original still revokes it.
            Path changed=f.typed().resolve("prepared.json");Files.write(changed,new byte[]{0});var preserved=V53ReplayFilesTest.files(f.base);
            assertEquals("learner handoff original typed members changed",assertThrows(IllegalArgumentException.class,promoted::source).getMessage());
            assertEquals("learner handoff original typed members changed",assertThrows(IllegalArgumentException.class,f::reopen).getMessage());
            assertEquals(preserved,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void completeCandidateNeedsMatchingTypedOwnersBeforeExplicitResume()throws Exception {
        var h=helper();try(var f=h.fixture(3,"ADD")) {
            var reached=new AtomicBoolean();
            try(var prior=f.prepare(e->{})) {
                var installed=h.install(f,prior.retainGeneration(),e->{if(e.equals("LEARNER_HEAD_CANDIDATE_WRITTEN")){reached.set(true);throw new IOException(e);}});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,1),f.captured,f.config,e->{})) {
                    assertThrows(IOException.class,typed::promoteSuccessor);assertTrue(reached.get());
                    assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.HEAD)));
                }
            }
            f.reopen();assertEquals("learner original handoff not committed",assertThrows(IllegalArgumentException.class,f.store::promotedSuccessor).getMessage());
            try(var prior=f.prepare(e->{});var typed=MembershipLearnerMaterialization.prepare(
                    MembershipLearnerPreparation.from(prior.retainGeneration().successor(),1),f.captured,f.config,e->{})) {
                typed.promoteSuccessor().source();
            }
            assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.HEAD_NEXT)));
            f.reopen();f.store.promotedSuccessor().source();assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
        }
    }
    @Test void closingThePredecessorDuringHandoffPreventsItsActiveCommit()throws Exception {
        var h=helper();try(var f=h.fixture(3,"ADD");var prior=f.prepare(e->{})) {
            var reached=new AtomicBoolean();
            var installed=h.install(f,prior.retainGeneration(),e->{if(e.equals("LEARNER_HEAD_CANDIDATE_WRITTEN")){reached.set(true);prior.close();}});
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,1),f.captured,f.config,e->{})) {
                assertEquals("learner typed owner closed or failed",assertThrows(IllegalArgumentException.class,typed::promoteSuccessor).getMessage());
                assertTrue(reached.get());assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.HEAD)));
                assertThrows(IllegalArgumentException.class,f.store::promotedSuccessor);
            }
        }
    }
}
