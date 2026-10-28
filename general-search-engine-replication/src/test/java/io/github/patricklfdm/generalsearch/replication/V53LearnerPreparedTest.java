package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerMaterialization.*;

/** Real original files and reservations; conditional source history, not a
 * native successor/INTENT or process-death qualification. */
class V53LearnerPreparedTest {
    @TempDir Path temp;
    V53LearnerMaterializationTest.Fixture fixture(int size,String kind)throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;return helper.new Fixture(size,kind);
    }
    @Test void fiveJoiningShapesSelectOriginalGenerationsBeforeReceivingAnotherSource()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            try(var f=fixture(size,kind)) {
                var original=V53ReplayFilesTest.files(f.source.request.replicaDirectory());
                try(var typed=f.prepare(e->{})) {
                    var token=typed.retainGeneration();token.check();assertEquals(f.source.request,token.request());
                    assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
                    assertArrayEquals(typed.receipt().bytes(),token.receipt().bytes());
                    try(var prefix=f.source.pull();var generation=f.source.pull()) {
                        prefix.fetchPrefix(f.base.resolve("fresh-source"));var copy=generation.fetchGeneration(prefix);
                        MembershipLearnerSource.successor(token.source(),copy);
                        assertEquals(1,f.source.client.usage().counts().get(Unit.LEARNER));assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
                    }
                    assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
                }
                assertEquals(original,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));
                var selected=V53ReplayFilesTest.files(f.typed());f.reopen();
                try(var typed=f.prepare(e->{})){typed.retainGeneration().check();assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));}
                assertEquals(selected,V53ReplayFilesTest.files(f.typed()));
            }
        }
    }
    @Test void selectionCutsKeepOriginalBytesAndOnlyFreeTheReceivingSlotAfterForce()throws Exception {
        for(String cut:List.of("LEARNER_PREPARED_CREATED","LEARNER_PREPARED_PREFIX_WRITTEN","LEARNER_PREPARED_WRITTEN",
                "LEARNER_PREPARED_FORCED","LEARNER_PREPARED_PARENT_FORCED","LEARNER_PREPARED_BEFORE_SELECT","LEARNER_PREPARED_BEFORE_RETURN")) {
            try(var f=fixture(3,"ADD")) {
                var reached=new AtomicBoolean();
                try(var typed=f.prepare(event->{if(event.equals(cut)){reached.set(true);throw new IOException(cut);}})) {
                    assertThrows(IOException.class,typed::retainGeneration);assertTrue(reached.get());
                    assertEquals(cut.endsWith("BEFORE_RETURN")?Unit.GENERATION:Unit.LEARNER,
                            f.source.client.usage().counts().containsKey(Unit.LEARNER)?Unit.LEARNER:Unit.GENERATION);
                    assertEquals(4,f.source.client.usage().leases()); // one metadata, two images, one MISC; no leaked claim
                }
                f.reopen();try(var typed=f.prepare(e->{})){typed.retainGeneration().check();}
                assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
            }
        }
    }
    @Test void generationCapacityRefusesBeforeCreatingTheSelection()throws Exception {
        try(var f=fixture(3,"ADD");var a=f.source.client.reserve(Unit.GENERATION,"a",1);var b=f.source.client.reserve(Unit.GENERATION,"b",1);
                var typed=f.prepare(e->{})) {
            var before=V53ReplayFilesTest.files(f.typed());var usage=f.source.client.usage();
            assertThrows(IllegalArgumentException.class,typed::retainGeneration);
            assertEquals(before,V53ReplayFilesTest.files(f.typed()));assertEquals(usage,f.source.client.usage());
        }
    }
    @Test void aForcedMarkerCannotConsumeAnotherStoresGenerationClaim()throws Exception {
        try(var f=fixture(3,"ADD")) {
            for(int reopen=0;reopen<2;reopen++) {
                if(reopen>0)f.reopen();
                var foreign=new MembershipResources(512*MIB);
                var current=new java.util.concurrent.atomic.AtomicReference<MembershipLearnerMaterialization<?>>();
                var checked=new AtomicBoolean();
                try(var other=foreign.reserve(Unit.LEARNER,"foreign",10);var claim=other.prepareGeneration("foreign");
                        var typed=f.prepare(event->{if(event.equals("LEARNER_PREPARED_BEFORE_SELECT")) {
                            var before=foreign.usage();
                            var error=assertThrows(IllegalArgumentException.class,()->f.store.selectedGeneration(current.get(),claim));
                            assertEquals("generation claim foreign source",error.getMessage());
                            assertEquals(before,foreign.usage());assertFalse(f.store.preparedGeneration());checked.set(true);
                        }})) {
                    current.set(typed);typed.retainGeneration().check();assertTrue(checked.get());
                }
                assertEquals(0,foreign.usage().leases());
            }
        }
    }
    @Test void originalSelectionTamperingAndClosedOwnersNeverAuthorizeRefresh()throws Exception {
        try(var f=fixture(3,"ADD")) {
            MembershipLearnerMaterialization.PreparedGeneration token;
            try(var typed=f.prepare(e->{})) {token=typed.retainGeneration();token.check();}
            assertThrows(IllegalArgumentException.class,token::check);
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerSource.refresh(token,f.source.owner.activationIdentity(),f.config.bounds(),
                    MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),1_000_000));
            Files.write(f.typed().resolve(PREPARED),new byte[]{1,2,3});var before=V53ReplayFilesTest.files(f.typed());
            assertThrows(IllegalArgumentException.class,()->f.prepare(e->{throw new AssertionError("foreign selection wrote files");}));
            assertEquals(before,V53ReplayFilesTest.files(f.typed()));
        }
    }
    @Test void higherCheckpointWithoutOriginalParentProofIsNotAValidSuccessor()throws Exception {
        var helper=new V53LearnerSourceTest();helper.temp=temp;
        try(var prior=helper.new Fixture(3,"ADD",3);var lower=helper.new Fixture(3,"ADD",2);var higher=helper.new Fixture(3,"ADD",4)) {
            var original=prior.owner.floorCopyCurrent().capsule;
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerSource.successor(original,lower.owner.floorCopyCurrent()));
            var error=assertThrows(IllegalArgumentException.class,()->MembershipLearnerSource.successor(original,higher.owner.floorCopyCurrent()));
            assertEquals("generation did not preserve original proven parent",error.getMessage());
        }
    }
}
