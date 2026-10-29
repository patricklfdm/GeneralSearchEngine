package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Exact original files and real core decode, with conditional voter histories.
 * Native revision progression and process death require separate qualification. */
class V53LearnerSlotHeadTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerSlotHeadCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerSlotTest helper(){var value=new V53LearnerSlotTest();value.temp=temp;return value;}
    @Test void selectedTypedSlotRetiresSeedAndColdReopensWithoutRecreatingIt()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(3,"ADD")) {
            var events=new ArrayList<String>();byte[] receipt;var oldView=f.store.promotedSuccessor();MembershipLearnerSlot.View current;
            try(var old=helper.current(f)) {
                var oldHead=old.currentHead();
                MembershipBallotAllocator.Cut cut=event->{
                    events.add(event);
                    if(event.equals("LEARNER_SLOT_RETIRE_PARENTS_FORCED"))assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                    if(event.equals("LEARNER_SLOT_RETIRE_RELEASED"))assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
                };
                MembershipLearnerSlot.View pending;
                try(var server=new MembershipTransport(f.source.owner,f.config.bounds(),f.source.server,
                        (sender,frame)->frame.kind().equals("STATUS_PROBE")?f.source.owner.discoveryStatus(sender,frame):f.source.service.handle(sender,frame),MembershipTransport.Events.NONE);
                    var transfer=MembershipLearnerSource.refresh(oldHead,f.source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                            System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(300))) {
                    transfer.fetch(f.base.resolve("slot-head-network"));pending=transfer.installSlot(cut);
                }
                // Later durable operations cannot depend on the closed transfer.
                try(var next=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,events::add)) {
                    receipt=next.receipt().bytes();current=next.promoteSlot(oldHead);
                    assertThrows(IllegalArgumentException.class,oldHead::check);assertThrows(IllegalArgumentException.class,oldView::source);
                    assertThrows(IllegalArgumentException.class,pending::source);assertThrows(IllegalArgumentException.class,next::receipt);
                    assertThrows(IllegalArgumentException.class,f.store::promotedSuccessor);
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                }
            }
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(current,1),f.captured,f.config,events::add)) {
                assertEquals("learner current slot requires forced seed retirement",assertThrows(IllegalArgumentException.class,typed::currentHead).getMessage());
                current.retirePredecessor();assertArrayEquals(receipt,typed.receipt().bytes());typed.currentHead().check();
                assertEquals(f.original,typed.state());assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
                assertEquals(2,f.source.client.usage().counts().get(Unit.APPLICATION));
            }
            assertTrue(events.indexOf("LEARNER_SLOT_HEAD_ACTIVE_PARENT_FORCED")<events.indexOf("LEARNER_SLOT_RETIRE_BEFORE_DELETE"));
            assertTrue(events.indexOf("LEARNER_SLOT_RETIRE_PARENTS_FORCED")<events.indexOf("LEARNER_SLOT_RETIRE_RELEASED"));
            Path seed=MembershipLearnerSuccessor.directory(f.summary);
            assertFalse(Files.exists(seed.resolve("source")));assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.summary)));
            assertTrue(Files.isRegularFile(seed.resolve("head.json")));assertTrue(Files.isRegularFile(seed.resolve("retire.json")));
            var before=V53ReplayFilesTest.files(f.base);f.reopen();
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{})) {
                assertArrayEquals(receipt,typed.receipt().bytes());assertEquals(f.original,typed.state());typed.currentHead().check();
            }
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertFalse(Files.exists(f.config.materialization().directory()));
            assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(2,f.source.client.usage().counts().get(Unit.APPLICATION));
            f.store.close();assertEquals(0,f.source.client.usage().leases());assertThrows(IllegalArgumentException.class,current::source);
        }
    }
    @Test void interruptedCoveredDeletionResumesAfterIndependentCurrentValidation()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(4,"REPLACE")) {
            var armed=new AtomicBoolean();var reached=new AtomicBoolean();MembershipLearnerSlot.View current;
            try(var old=helper.current(f)) {
                var pending=helper.install(f,old.currentHead(),event->{if(armed.get() && event.equals("LEARNER_SLOT_RETIRE_MEMBER_DELETED")) {
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));reached.set(true);throw new IOException(event);
                }});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    current=typed.promoteSlot(old.currentHead());
                }
            }
            Path source=MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.SOURCE);
            var originals=V53ReplayFilesTest.files(source);Object inode=MembershipBasisSources.key(source);
            armed.set(true);assertThrows(IOException.class,current::retirePredecessor);assertTrue(reached.get());f.reopen();
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{})) {
                typed.currentHead().check();assertEquals(f.original,typed.state());
            }
            assertEquals(originals,V53ReplayFilesTest.files(source));assertEquals(inode,MembershipBasisSources.key(source));
            assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve("source")));
            assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.summary)));
            assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
        }
    }
    @Test void partialHeadIsPreservedAndCannotRevokeOrDeleteTheOldCurrentSource()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(5,"REPLACE")) {
            var reached=new AtomicBoolean();
            try(var old=helper.current(f)) {
                var pending=helper.install(f,old.currentHead(),event->{if(event.equals("LEARNER_SLOT_HEAD_CANDIDATE_PREFIX_WRITTEN")){reached.set(true);throw new IOException(event);}});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    var oldHead=old.currentHead();assertThrows(IOException.class,()->typed.promoteSlot(oldHead));assertTrue(reached.get());oldHead.check();
                }
            }
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,event->{
                if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("invalid head recovery wrote: "+event);
            }));
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void unknownOldMemberRejectsCleanupAndColdRecoveryWithoutChangingAnyOriginal()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(3,"ADD")) {
            MembershipLearnerSlot.View current;
            try(var old=helper.current(f)) {
                var pending=helper.install(f,old.currentHead(),e->{});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    current=typed.promoteSlot(old.currentHead());
                }
            }
            Files.write(MembershipLearnerSuccessor.directory(f.summary).resolve("source/unknown"),new byte[]{1});
            var before=V53ReplayFilesTest.files(f.base);assertThrows(IllegalArgumentException.class,current::retirePredecessor);
            assertEquals(before,V53ReplayFilesTest.files(f.base));f.store.close();
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,event->{
                if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("unknown member recovery wrote: "+event);
            }));
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void originalCompleteCandidateResumesWithTheSameInodeAndActualTypedOwners()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(4,"REPLACE")) {
            var reached=new AtomicBoolean();
            try(var old=helper.current(f)) {
                var pending=helper.install(f,old.currentHead(),event->{if(event.equals("LEARNER_SLOT_HEAD_CANDIDATE_WRITTEN")){reached.set(true);throw new IOException(event);}});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    var oldHead=old.currentHead();assertThrows(IOException.class,()->typed.promoteSlot(oldHead));assertTrue(reached.get());oldHead.check();
                }
            }
            Path directory=MembershipLearnerSlot.directory(f.summary),candidate=directory.resolve(MembershipLearnerSlot.HEAD_NEXT);
            byte[] original=Files.readAllBytes(candidate);Object inode=MembershipBasisSources.key(candidate);
            var before=V53ReplayFilesTest.files(f.base);f.reopen();assertEquals(before,V53ReplayFilesTest.files(f.base));
            try(var old=helper.current(f)) {
                var pending=f.store.resumeSlot(old.currentHead());
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    var selected=typed.promoteSlot(old.currentHead());
                    assertEquals(inode,MembershipBasisSources.key(directory.resolve(MembershipLearnerSlot.HEAD)));
                    assertArrayEquals(original,Files.readAllBytes(directory.resolve(MembershipLearnerSlot.HEAD)));
                    assertFalse(Files.exists(candidate));selected.retirePredecessor();
                }
            }
            f.reopen();
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{})) {
                assertEquals(f.original,typed.state());typed.currentHead().check();
            }
            assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
        }
    }
    @Test void sameBytesReplacementOfTheSelectingHeadCannotAuthorizeColdDeletion()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(3,"ADD")) {
            MembershipLearnerSlot.View selected;
            try(var old=helper.current(f)) {
                var pending=helper.install(f,old.currentHead(),e->{});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    selected=typed.promoteSlot(old.currentHead());
                }
            }
            Path head=MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.HEAD),kept=f.base.resolve("original-slot-head.json");
            byte[] bytes=Files.readAllBytes(head);Object inode=MembershipBasisSources.key(head);
            Files.move(head,kept);Files.write(head,bytes);assertNotEquals(inode,MembershipBasisSources.key(head));
            var before=V53ReplayFilesTest.files(f.base);assertThrows(IllegalArgumentException.class,selected::retirePredecessor);
            assertEquals(before,V53ReplayFilesTest.files(f.base));f.store.close();
            assertEquals("learner slot original head inode changed",assertThrows(IllegalArgumentException.class,()->
                    MembershipLearnerStore.resume(f.summary,f.source.client,event->{
                        if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("replaced head recovery wrote: "+event);
                    })).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void acquisitionGuardStillAppliesThroughTheLastInstallationCut()throws Exception {
        var helper=helper();
        try(var f=helper.fixture(3,"ADD")) {
            try(var old=helper.current(f);var prefix=f.source.pull();var generation=f.source.pull()) {
                prefix.fetchPrefix(f.base.resolve("guarded-slot-source"));var copy=generation.fetchGeneration(prefix);
                var expired=new AtomicBoolean();var reached=new AtomicBoolean();
                var error=assertThrows(IOException.class,()->MembershipLearnerSlot.install(old.currentHead(),prefix.completeLearnerSource(copy,e->{}),copy,
                        event->{if(event.equals("LEARNER_SLOT_BEFORE_RETURN")){reached.set(true);expired.set(true);}},
                        ()->{if(expired.get())throw new IOException("original acquisition deadline");}));
                assertEquals("original acquisition deadline",error.getMessage());assertTrue(reached.get());old.currentHead().check();
                assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                assertTrue(Files.isRegularFile(MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.INSTALLED)));
            }
            f.reopen();
            try(var reopened=helper.current(f)) {
                var pending=f.store.resumeSlot(reopened.currentHead());
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    assertEquals(f.original,typed.state());
                }
            }
        }
    }
}
