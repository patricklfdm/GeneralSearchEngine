package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Conditional source histories test actual file ownership. Native revision
 * advancement and process-death qualification are distinct histories. */
class V53LearnerSuccessorTest {
    @TempDir Path temp;
    V53LearnerMaterializationTest.Fixture fixture(int size,String kind)throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;return helper.new Fixture(size,kind);
    }
    MembershipLearnerSuccessor.View install(V53LearnerMaterializationTest.Fixture f,
            MembershipLearnerMaterialization.PreparedGeneration prepared,MembershipBallotAllocator.Cut cut)throws Exception {
        try(var prefix=f.source.pull();var generation=f.source.pull()) {
            prefix.fetchPrefix(f.base.resolve("refresh-"+UUID.randomUUID()));var copy=generation.fetchGeneration(prefix);
            var received=prefix.completeLearnerSource(copy,e->{});
            return MembershipLearnerSuccessor.install(prepared,received,copy,cut).open(prepared);
        }
    }
    @Test void fiveJoiningShapesRetainAndReopenExactlySelectedSourceBytes()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            try(var f=fixture(size,kind)) {
                var original=V53ReplayFilesTest.files(f.source.request.replicaDirectory());
                try(var typed=f.prepare(e->{})) {
                    var prepared=typed.retainGeneration();var successor=install(f,prepared,e->{});
                    assertArrayEquals(prepared.source().packet.bytes(),successor.source().packet.bytes());
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
                    assertFalse(successor.source().context.voters().contains(f.source.request.identity().nodeId().value()));
                }
                var path=MembershipLearnerSuccessor.directory(f.summary);var retained=V53ReplayFilesTest.files(path);f.reopen();
                assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(1,f.source.client.usage().counts().get(Unit.LEARNER));
                try(var typed=f.prepare(e->{})) {
                    var prepared=typed.retainGeneration();assertArrayEquals(prepared.source().packet.bytes(),prepared.successor().source().packet.bytes());
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                }
                assertEquals(original,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));assertEquals(retained,V53ReplayFilesTest.files(path));
            }
        }
    }
    @Test void interruptedPlansRefuseIncompleteDecisionsAndResumeOnlyCompleteOriginals()throws Exception {
        for(String cut:List.of("LEARNER_SUCCESSOR_DIRECTORY_FORCED","LEARNER_SUCCESSOR_PLAN_CREATED","LEARNER_SUCCESSOR_PLAN_PREFIX_WRITTEN",
                "LEARNER_SUCCESSOR_PLAN_WRITTEN","LEARNER_SUCCESSOR_PLAN_RENAMED","LEARNER_SUCCESSOR_SOURCE_MOVED",
                "LEARNER_SUCCESSOR_SELECT_PREFIX_WRITTEN","LEARNER_SUCCESSOR_SELECT_FORCED","LEARNER_SUCCESSOR_BEFORE_RETURN")) {
            try(var f=fixture(3,"ADD")) {
                var reached=new AtomicBoolean();
                try(var typed=f.prepare(e->{})) {
                    var prepared=typed.retainGeneration();
                    assertThrows(IOException.class,()->install(f,prepared,event->{if(event.equals(cut)){reached.set(true);throw new IOException(cut);}}));assertTrue(reached.get());
                }
                Path path=MembershipLearnerSuccessor.directory(f.summary);
                if(Set.of("LEARNER_SUCCESSOR_DIRECTORY_FORCED","LEARNER_SUCCESSOR_PLAN_CREATED","LEARNER_SUCCESSOR_PLAN_PREFIX_WRITTEN").contains(cut)) {
                    var before=V53ReplayFilesTest.files(path);
                    if(cut.equals("LEARNER_SUCCESSOR_DIRECTORY_FORCED"))assertThrows(IllegalArgumentException.class,f::reopen);
                    else {
                        var error=assertThrows(RuntimeException.class,f::reopen);
                        assertTrue(error instanceof ReplicationException || error instanceof IllegalArgumentException);
                        assertTrue(error.getMessage().contains("JSON"));
                    }
                    assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(0,f.source.client.usage().leases());
                }else {
                    f.reopen();try(var typed=f.prepare(e->{})){typed.retainGeneration().successor().source();}
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                    assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
                }
            }
        }
    }
    @Test void unknownOrChangedOriginalMetadataRefusesWithoutRepair()throws Exception {
        for(String name:List.of("selected.json","install.json","unknown")) {
            try(var f=fixture(3,"ADD")) {
                try(var typed=f.prepare(e->{})){install(f,typed.retainGeneration(),e->{});}
                Path path=MembershipLearnerSuccessor.directory(f.summary);Files.write(path.resolve(name),new byte[]{1,2,3});
                var before=V53ReplayFilesTest.files(path);
                if(name.equals("install.json"))assertEquals("invalid JSON number",assertThrows(ReplicationException.class,f::reopen).getMessage());
                else assertThrows(IllegalArgumentException.class,f::reopen);
                assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(0,f.source.client.usage().leases());
            }
        }
    }
    @Test void repeatedInstallAndClosedTypedOwnersCannotReplaceTheCurrentSource()throws Exception {
        try(var f=fixture(3,"ADD")) {
            MembershipLearnerSuccessor.View view;
            try(var typed=f.prepare(e->{})) {
                var prepared=typed.retainGeneration();view=install(f,prepared,e->{});
                var before=V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary));var usage=f.source.client.usage();
                assertThrows(IllegalArgumentException.class,()->install(f,prepared,e->{}));
                assertEquals(before,V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary)));assertEquals(usage,f.source.client.usage());
            }
            assertThrows(IllegalArgumentException.class,view::source);
            assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
            f.store.close();assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void preparedRefreshCannotOccupyItsReservedCoreOrTypedDirectories()throws Exception {
        try(var f=fixture(3,"ADD")) {
            Path successor=MembershipLearnerSuccessor.directory(f.summary);
            var config=new MembershipReplicaConfig<>(f.config.root(),f.config.localIdentity(),List.of(),f.config.replicaDirectory(),
                    io.github.patricklfdm.generalsearch.admission.OfflineApplication.storage(successor,2),f.config.bounds(),AutomaticLeadershipPolicy.forBounds(f.config.bounds()));
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store,1),f.captured,config,e->{})) {
                var prepared=typed.retainGeneration();var usage=f.source.client.usage();
                assertEquals("overlapping authority/source paths",assertThrows(ReplicationException.class,()->install(f,prepared,e->{})).getMessage());
                assertFalse(Files.exists(successor));assertEquals(usage,f.source.client.usage());
                try(var refresh=MembershipLearnerSource.refresh(prepared,f.source.owner.activationIdentity(),config.bounds(),
                        MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),1_000_000_000)) {
                    assertEquals("overlapping authority/source paths",assertThrows(ReplicationException.class,()->refresh.fetch(successor)).getMessage());
                    assertFalse(Files.exists(successor));
                }
            }
        }
    }
    @Test void replacingAnOriginalSourceInodeIsRefusedAndPreserved()throws Exception {
        try(var f=fixture(3,"ADD")) {
            try(var typed=f.prepare(e->{})) {
                var view=install(f,typed.retainGeneration(),e->{});
                Path path=MembershipLearnerSuccessor.directory(f.summary).resolve("source/generation.gsr");
                byte[] bytes=Files.readAllBytes(path);Files.delete(path);Files.write(path,bytes);
                assertEquals("learner successor original source changed",assertThrows(IllegalArgumentException.class,view::source).getMessage());
            }
            var path=MembershipLearnerSuccessor.directory(f.summary);var before=V53ReplayFilesTest.files(path);
            assertEquals("learner successor original source changed",assertThrows(IllegalArgumentException.class,f::reopen).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void capacityRefusalRetainsTheCompleteCandidateForExplicitResume()throws Exception {
        try(var f=fixture(3,"ADD")) {
            try(var typed=f.prepare(e->{})) {
                var prepared=typed.retainGeneration();
                try(var busy=f.source.client.reserve(Unit.GENERATION,"busy",1)) {
                    assertEquals("generation reservation capacity",assertThrows(IllegalArgumentException.class,()->install(f,prepared,e->{})).getMessage());
                    assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(1,f.source.client.usage().counts().get(Unit.LEARNER));
                    assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve("selected.json")));
                }
            }
            f.reopen();try(var typed=f.prepare(e->{})){typed.retainGeneration().successor().source();}
            assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
        }
    }
}
