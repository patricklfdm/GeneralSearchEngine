package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Real files, core decoding and shared reservations over conditional histories.
 * The separate TCP test certifies two distinct PREPARE revisions. */
class V53SuccessorTypedTest {
    @TempDir Path temp;
    V53LearnerSuccessorTest helper(){var h=new V53LearnerSuccessorTest();h.temp=temp;return h;}
    @Test void fiveShapesDecodeAndReopenTheSelectedOriginalWithoutReplacingItsPredecessor()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;var h=helper();
            try(var f=h.fixture(size,kind)) {
                byte[] receipt;Path path=MembershipLearnerSuccessor.typedDirectory(f.summary);
                try(var prior=f.prepare(e->{})) {
                    var view=h.install(f,prior.retainGeneration(),e->{});var original=V53ReplayFilesTest.files(f.typed());
                    var input=MembershipLearnerPreparation.from(view,1);var events=new ArrayList<String>();
                    try(var typed=MembershipLearnerMaterialization.prepare(input,f.captured,f.config,events::add)) {
                        assertEquals(f.original,typed.state());receipt=typed.receipt().bytes();
                        assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
                        assertTrue(events.indexOf("LEARNER_TYPED_SEMANTICS_VERIFIED")<events.indexOf("LEARNER_TYPED_RECEIPT_CREATED"));
                        assertThrows(IllegalArgumentException.class,typed::retainGeneration);
                        assertFalse(Files.exists(path.resolve("prepared.json")));typed.receipt();
                        assertThrows(ReplicationException.class,()->MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{}));
                    }
                    assertEquals(original,V53ReplayFilesTest.files(f.typed()));
                    var plan=object(parse(Files.readAllBytes(path.resolve("preparation.json")),16384));
                    assertEquals("gse-v53-successor-typed/1.3",plan.get("schema"));assertEquals(hash(receipt),plan.get("receipt"));
                    assertTrue(((String)plan.get("configuration")).matches("[0-9a-f]{64}"));
                }
                var before=V53ReplayFilesTest.files(path);f.reopen();assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
                try(var prior=f.prepare(e->{});var typed=MembershipLearnerMaterialization.prepare(
                        MembershipLearnerPreparation.from(prior.retainGeneration().successor(),1),f.captured,f.config,e->{})) {
                    assertArrayEquals(receipt,typed.receipt().bytes());assertEquals(f.original,typed.state());
                }
                assertEquals(before,V53ReplayFilesTest.files(path));assertFalse(Files.exists(f.config.materialization().directory()));
            }
        }
    }
    @Test void originalPlansAndPrefixWritesResumeWithoutMintingReadinessOnFailure()throws Exception {
        var cuts=List.of("LEARNER_TYPED_DIRECTORY_FORCED","LEARNER_TYPED_PLAN_PREFIX_WRITTEN","LEARNER_TYPED_PLAN_WRITTEN",
                "LEARNER_TYPED_MEMBER_PREFIX_WRITTEN","LEARNER_TYPED_SEMANTICS_VERIFIED","LEARNER_TYPED_RECEIPT_PREFIX_WRITTEN","LEARNER_TYPED_BEFORE_RETURN");
        for(String cut:cuts){var h=helper();try(var f=h.fixture(3,"ADD")) {
            var reached=new AtomicBoolean();Path path=MembershipLearnerSuccessor.typedDirectory(f.summary);
            try(var prior=f.prepare(e->{})) {
                var view=h.install(f,prior.retainGeneration(),e->{});
                assertThrows(IOException.class,()->MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(view,1),f.captured,f.config,
                        e->{if(e.equals(cut)){reached.set(true);throw new IOException(cut);}}));assertTrue(reached.get());
            }
            var before=V53ReplayFilesTest.files(path);f.reopen();assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
            try(var prior=f.prepare(e->{})) {
                var input=MembershipLearnerPreparation.from(prior.retainGeneration().successor(),1);
                if(cuts.indexOf(cut)<2) {
                    assertThrows(IllegalArgumentException.class,()->MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{throw new AssertionError("refusal wrote bytes");}));
                    assertEquals(before,V53ReplayFilesTest.files(path));
                }else try(var typed=MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{})){assertEquals(f.original,typed.state());}
            }
        }}
    }
    @Test void successorBackupRemainsChargedAfterChildCloseAndAcrossParentReopen()throws Exception {
        var h=helper();try(var f=h.fixture(3,"ADD");var prior=f.prepare(e->{})) {
            var input=MembershipLearnerPreparation.from(h.install(f,prior.retainGeneration(),e->{}),1);var busy=new ArrayList<MembershipResources.Lease>();
            try {
                for(int i=0;i<4;i++)busy.add(f.source.client.reserve(Unit.APPLICATION,"busy-"+i,1));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{}));
                assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.summary)));busy.removeLast().close();
                try(var typed=MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{})){typed.receipt();}
                assertEquals(7,f.source.client.usage().counts().get(Unit.APPLICATION));
            }finally{busy.forEach(MembershipResources.Lease::close);}
            f.reopen();assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
        }
    }
    @Test void closingEitherPredecessorOrParentRevokesTheSuccessorReceipt()throws Exception {
        for(boolean closeParent:List.of(false,true)){var h=helper();try(var f=h.fixture(3,"ADD");var prior=f.prepare(e->{})) {
            var input=MembershipLearnerPreparation.from(h.install(f,prior.retainGeneration(),e->{}),1);
            try(var typed=MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{})) {
                if(closeParent)f.store.close();else prior.close();
                assertThrows(IllegalArgumentException.class,typed::receipt);assertThrows(IllegalArgumentException.class,typed::state);
                assertEquals(closeParent?0:4,f.source.client.usage().counts().getOrDefault(Unit.APPLICATION,0));
                if(closeParent)assertTrue(typed.closed());
            }
        }}
    }
    @Test void changedBackupOrCompactPlanIsPreservedAndRefused()throws Exception {
        for(String mode:List.of("backup","plan","receipt","extra","prepared")){var h=helper();try(var f=h.fixture(3,"ADD")) {
            Path path=MembershipLearnerSuccessor.typedDirectory(f.summary);
            try(var prior=f.prepare(e->{});var typed=MembershipLearnerMaterialization.prepare(
                    MembershipLearnerPreparation.from(h.install(f,prior.retainGeneration(),e->{}),1),f.captured,f.config,e->{})){typed.receipt();}
            Path changed=switch(mode){case "backup"->path.resolve("backup").resolve(MembershipApplicationImage.MEMBERS.getFirst());
                case "plan"->path.resolve("preparation.json");case "receipt"->path.resolve("learner.gsr");case "prepared"->path.resolve("prepared.json");default->path.resolve("foreign");};
            Files.write(changed,new byte[]{0});var before=V53ReplayFilesTest.files(path);f.reopen();
            try(var prior=f.prepare(e->{})) {
                var input=MembershipLearnerPreparation.from(prior.retainGeneration().successor(),1);
                var error=assertThrows(RuntimeException.class,()->MembershipLearnerMaterialization.prepare(input,f.captured,f.config,e->{throw new AssertionError("changed original forced");}));
                assertTrue(error instanceof IllegalArgumentException || error instanceof ReplicationException);
            }
            assertEquals(before,V53ReplayFilesTest.files(path));
        }}
    }
    @Test void changedReservedCorePathIsRejectedBeforeNewTypedWrites()throws Exception {
        var h=helper();try(var f=h.fixture(3,"ADD");var prior=f.prepare(e->{})) {
            var input=MembershipLearnerPreparation.from(h.install(f,prior.retainGeneration(),e->{}),1);
            var config=new MembershipReplicaConfig<>(f.config.root(),f.config.localIdentity(),List.of(),f.config.replicaDirectory(),
                    io.github.patricklfdm.generalsearch.admission.OfflineApplication.storage(f.base.resolve("other-core"),2),f.config.bounds(),f.config.leadershipPolicy());
            assertEquals("learner successor changed reserved core path",assertThrows(IllegalArgumentException.class,
                    ()->MembershipLearnerMaterialization.prepare(input,f.captured,config,e->{})).getMessage());
            assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.summary)));
        }
    }
}
