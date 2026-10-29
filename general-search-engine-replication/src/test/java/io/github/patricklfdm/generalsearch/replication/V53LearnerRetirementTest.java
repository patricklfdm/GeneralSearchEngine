package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Original conditional histories, real typed decoding and synchronous I/O cuts.
 * Separate native and process-death qualification remains mandatory. */
class V53LearnerRetirementTest {
    @TempDir Path temp;
    V53LearnerSuccessorTest helper(){var h=new V53LearnerSuccessorTest();h.temp=temp;return h;}
    MembershipLearnerSuccessor.View head(V53LearnerMaterializationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        try(var prior=f.prepare(e->{})) {
            var installed=helper().install(f,prior.retainGeneration(),cut);
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,1),f.captured,f.config,e->{})) {
                return typed.promoteSuccessor();
            }
        }
    }
    Path source(V53LearnerMaterializationTest.Fixture f){return f.summary.request().replicaDirectory().resolve("learner");}
    Path marker(V53LearnerMaterializationTest.Fixture f){return MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerRetirement.FILE);}
    void released(V53LearnerMaterializationTest.Fixture f) {
        assertFalse(Files.exists(source(f)));assertFalse(Files.exists(f.typed()));
        assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(2,f.source.client.usage().counts().get(Unit.APPLICATION));
        assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
    }
    @Test void removesOnlyCoveredOriginalsThenReleasesAndReopensTypedSuccessor()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            var events=new ArrayList<String>();var view=head(f,events::add);byte[] packet=view.source().packet.bytes();
            Path current=MembershipLearnerSuccessor.directory(f.summary).resolve("source"),typed=MembershipLearnerSuccessor.typedDirectory(f.summary);
            var originals=V53ReplayFilesTest.files(current);var backup=V53ReplayFilesTest.files(typed);
            view.retirePredecessor();released(f);assertArrayEquals(packet,view.source().packet.bytes());
            assertEquals(originals,V53ReplayFilesTest.files(current));assertEquals(backup,V53ReplayFilesTest.files(typed));
            assertTrue(events.indexOf("LEARNER_RETIRE_DECISION_PARENT_FORCED")<events.indexOf("LEARNER_RETIRE_MEMBER_DELETED"));
            assertTrue(events.indexOf("LEARNER_RETIRE_PARENTS_FORCED")<events.indexOf("LEARNER_RETIRE_RELEASED"));
            assertThrows(IllegalArgumentException.class,f.store::capsule);
            f.reopen();released(f);var reopened=f.store.promotedSuccessor();assertArrayEquals(packet,reopened.source().packet.bytes());
            try(var decoded=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(reopened,1),f.captured,f.config,e->{})) {
                assertEquals(f.original,decoded.state());
            }
            var unchanged=V53ReplayFilesTest.files(f.base);reopened.retirePredecessor();assertEquals(unchanged,V53ReplayFilesTest.files(f.base));
            f.reopen();released(f);assertArrayEquals(packet,f.store.promotedSuccessor().source().packet.bytes());
        }
    }
    @Test void incompleteRetirementIsPreservedWithoutDeletingAnything()throws Exception {
        for(String cut:List.of("LEARNER_RETIRE_DECISION_CREATED","LEARNER_RETIRE_DECISION_PREFIX_WRITTEN"))try(var f=helper().fixture(3,"ADD")) {
            var hit=new AtomicBoolean();var view=head(f,e->{if(e.equals(cut)){hit.set(true);throw new IOException(e);}});
            var old=V53ReplayFilesTest.files(source(f));var backup=V53ReplayFilesTest.files(f.typed());
            assertThrows(IOException.class,view::retirePredecessor);assertTrue(hit.get());
            assertEquals(old,V53ReplayFilesTest.files(source(f)));assertEquals(backup,V53ReplayFilesTest.files(f.typed()));
            var all=V53ReplayFilesTest.files(f.base);assertThrows(IllegalArgumentException.class,f::reopen);
            assertEquals(all,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void completeDecisionRecoversAfterInterruptedDeletionWithoutEarlyRelease()throws Exception {
        for(String cut:List.of("LEARNER_RETIRE_DECISION_WRITTEN","LEARNER_RETIRE_MEMBER_DELETED","LEARNER_RETIRE_PARENTS_FORCED"))try(var f=helper().fixture(3,"ADD")) {
            var hit=new AtomicBoolean();var view=head(f,e->{if(e.equals(cut)) {
                assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
                hit.set(true);throw new IOException(e);
            }});
            assertThrows(IOException.class,view::retirePredecessor);assertTrue(hit.get());
            assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
            f.reopen();released(f);f.store.promotedSuccessor().source();
        }
    }
    @Test void unknownOrReplacedRemainingMembersRefuseBeforeAnyFurtherRemoval()throws Exception {
        for(String kind:List.of("source-extra","typed-extra","source-replaced","typed-replaced","current-changed"))try(var f=helper().fixture(3,"ADD")) {
            var hit=new AtomicBoolean();var view=head(f,e->{if(e.equals("LEARNER_RETIRE_DECISION_PARENT_FORCED")){hit.set(true);throw new IOException(e);}});
            assertThrows(IOException.class,view::retirePredecessor);assertTrue(hit.get());
            switch(kind) {
                case "source-extra"->Files.write(source(f).resolve("unknown"),new byte[]{1});
                case "typed-extra"->Files.write(f.typed().resolve("unknown"),new byte[]{1});
                case "source-replaced"->replace(source(f).resolve("generation.gsr"));
                case "typed-replaced"->replace(f.typed().resolve("prepared.json"));
                case "current-changed"->Files.write(MembershipLearnerSuccessor.directory(f.summary).resolve("source/generation.gsr"),new byte[]{1});
            }
            var before=V53ReplayFilesTest.files(f.base);assertThrows(Exception.class,f::reopen);
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    private void replace(Path path)throws IOException {
        Path foreign=path.resolveSibling("replacement");Files.write(foreign,Files.readAllBytes(path));Files.move(foreign,path,StandardCopyOption.REPLACE_EXISTING);
    }
    @Test void missingDecisionCannotAuthorizeMissingOldSource()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            var view=head(f,e->{});view.retirePredecessor();Files.delete(marker(f));
            var before=V53ReplayFilesTest.files(f.base);assertThrows(IllegalArgumentException.class,f::reopen);assertEquals(before,V53ReplayFilesTest.files(f.base));
            assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void deletionCutRechecksCurrentSourceAndPreservesOldReservations()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            var hit=new AtomicBoolean();var view=head(f,e->{if(e.equals("LEARNER_RETIRE_BEFORE_DELETE") && hit.compareAndSet(false,true))
                Files.write(MembershipLearnerSuccessor.directory(f.summary).resolve("source/generation.gsr"),new byte[]{1});});
            var original=V53ReplayFilesTest.files(source(f));var backup=V53ReplayFilesTest.files(f.typed());
            assertThrows(IllegalArgumentException.class,view::retirePredecessor);assertTrue(hit.get());
            assertEquals(original,V53ReplayFilesTest.files(source(f)));assertEquals(backup,V53ReplayFilesTest.files(f.typed()));
            assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
        }
    }
}
