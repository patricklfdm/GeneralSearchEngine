package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestInfo;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Original files and real typed decoding; the underlying voter history is a
 * conditional fixture. Native revision advancement remains a separate gate. */
class V53LearnerSlotTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerSlotCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerMaterializationTest.Fixture fixture(int size,String kind)throws Exception {
        var h=new V53LearnerSuccessorTest();h.temp=temp;var f=h.fixture(size,kind);
        var retirement=new V53LearnerRetirementTest();retirement.temp=temp;retirement.head(f,e->{}).retirePredecessor();return f;
    }
    MembershipLearnerMaterialization<io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc> current(V53LearnerMaterializationTest.Fixture f)throws Exception {
        return MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.promotedSuccessor(),1),f.captured,f.config,e->{});
    }
    MembershipLearnerSlot.View install(V53LearnerMaterializationTest.Fixture f,MembershipLearnerMaterialization.CurrentHead current,
            MembershipBallotAllocator.Cut cut)throws Exception {
        try(var prefix=f.source.pull();var generation=f.source.pull()) {
            prefix.fetchPrefix(f.base.resolve("next-source-"+UUID.randomUUID()));var copy=generation.fetchGeneration(prefix);
            return MembershipLearnerSlot.install(current,prefix.completeLearnerSource(copy,e->{}),copy,cut);
        }
    }
    @Test void tcpInstallationAndColdTypedReopenKeepTwoOriginalGenerationsWithoutSelectingTheCandidate()throws Exception {
        try(var f=fixture(3,"ADD");var server=new MembershipTransport(f.source.owner,f.config.bounds(),f.source.server,
                (sender,frame)->frame.kind().equals("STATUS_PROBE")?f.source.owner.discoveryStatus(sender,frame):f.source.service.handle(sender,frame),MembershipTransport.Events.NONE)) {
            var before=V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary));byte[] receipt;
            try(var old=current(f)) {
                var head=old.currentHead();
                try(var refresh=MembershipLearnerSource.refresh(head,f.source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                        System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(300))) {
                    var copy=refresh.fetch(f.base.resolve("third-source"));var slot=refresh.installSlot(e->{});
                    assertArrayEquals(copy.capsule.packet.bytes(),slot.source().packet.bytes());head.check();
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
                    assertEquals("learner inactive slot requires original resume or selection",assertThrows(IllegalArgumentException.class,()->
                        MembershipLearnerSource.refresh(head,f.source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                                System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(300))).getMessage());
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(slot,1),f.captured,f.config,e->{})) {
                        assertEquals(f.original,typed.state());receipt=typed.receipt().bytes();
                        assertEquals("learner inactive slot is not the current head",assertThrows(IllegalArgumentException.class,typed::currentHead).getMessage());
                        assertThrows(IllegalArgumentException.class,typed::retainGeneration);assertThrows(IllegalArgumentException.class,typed::promoteSuccessor);
                    }
                    assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
                    assertFalse(slot.source().context.voters().contains(f.summary.request().identity().nodeId().value()));
                    assertEquals(before,V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary)));
                }
            }
            var slotFiles=V53ReplayFilesTest.files(MembershipLearnerSlot.directory(f.summary));
            var typedFiles=V53ReplayFilesTest.files(MembershipLearnerSlot.typedDirectory(f.summary));
            f.reopen();assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
            MembershipLearnerSlot.View retained;
            try(var old=current(f)) {
                retained=f.store.resumeSlot(old.currentHead());
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(retained,1),f.captured,f.config,e->{})) {
                    assertArrayEquals(receipt,typed.receipt().bytes());assertEquals(f.original,typed.state());
                }
            }
            assertEquals(slotFiles,V53ReplayFilesTest.files(MembershipLearnerSlot.directory(f.summary)));
            assertEquals(typedFiles,V53ReplayFilesTest.files(MembershipLearnerSlot.typedDirectory(f.summary)));
            assertEquals(before,V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary)));
            // The validated current binding cannot mask a later original change.
            Path originalReceipt=MembershipLearnerSuccessor.typedDirectory(f.summary).resolve("learner.gsr");
            Files.write(originalReceipt,new byte[]{0});
            assertEquals("learner handoff original typed members changed",assertThrows(IllegalArgumentException.class,retained::source).getMessage());
            f.store.close();assertEquals(0,f.source.client.usage().leases());assertThrows(IllegalArgumentException.class,retained::source);
            assertTrue(MembershipLearnerSlot.METADATA_MAXIMUM<=Unit.MISC.bytes);
        }
    }
    @Test void originalCompletePlanResumesAfterTheMoveWithoutASecondTransfer()throws Exception {
        try(var f=fixture(4,"REPLACE")) {
            var reached=new AtomicBoolean();
            try(var old=current(f)) {
                assertThrows(IOException.class,()->install(f,old.currentHead(),e->{if(e.equals("LEARNER_SLOT_SOURCE_MOVED")){reached.set(true);throw new IOException(e);}}));
                assertTrue(reached.get());old.currentHead().check();
            }
            Path source=MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.SOURCE);
            var bytes=V53ReplayFilesTest.files(source);Object original=MembershipBasisSources.key(source);
            f.reopen();
            try(var old=current(f)) {
                var slot=f.store.resumeSlot(old.currentHead());
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(slot,1),f.captured,f.config,e->{})) {
                    assertEquals(f.original,typed.state());assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                }
            }
            assertEquals(original,MembershipBasisSources.key(source));assertEquals(bytes,V53ReplayFilesTest.files(source));
        }
    }
    @Test void incompleteOriginalPlanRefusesWithoutRepairOrRecoveryForces()throws Exception {
        try(var f=fixture(5,"REPLACE")) {
            var reached=new AtomicBoolean();
            try(var old=current(f)) {
                assertThrows(IOException.class,()->install(f,old.currentHead(),e->{if(e.equals("LEARNER_SLOT_PLAN_PREFIX_WRITTEN")){reached.set(true);throw new IOException(e);}}));
                assertTrue(reached.get());old.currentHead().check();
            }
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,e->{if(!e.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("invalid slot must not force originals: "+e);}));
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void replacedSourceInodeRefusesWithoutChangingOrForcingTheCurrentHead()throws Exception {
        try(var f=fixture(3,"ADD")) {
            try(var old=current(f)) {
                var slot=install(f,old.currentHead(),e->{});
                Path path=MembershipLearnerSlot.directory(f.summary).resolve("source-b/generation.gsr"),kept=f.base.resolve("replaced-generation.gsr");
                byte[] bytes=Files.readAllBytes(path);Files.move(path,kept);Files.write(path,bytes);
                assertEquals("learner slot original source changed",assertThrows(IllegalArgumentException.class,slot::source).getMessage());old.currentHead().check();
            }
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            assertEquals("learner slot original source changed",assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,
                    e->{if(!e.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("changed slot must not force originals: "+e);})).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
}
