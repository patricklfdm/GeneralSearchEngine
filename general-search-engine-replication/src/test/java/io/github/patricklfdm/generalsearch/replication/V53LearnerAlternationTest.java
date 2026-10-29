package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Continuous fixed-path component histories with real transfers and typed
 * applications. Conditional voter fixtures are not autonomous qualification. */
class V53LearnerAlternationTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerAlternationCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerReuseTest helper(){var h=new V53LearnerReuseTest();h.temp=temp;return h;}
    void selectA(V53LearnerMaterializationTest.Fixture f)throws Exception {
        var rotation=new V53LearnerRotationTest();rotation.temp=temp;rotation.rotate(f,e->{}).retirePredecessor();
    }
    MembershipLearnerSlot.View selectNext(V53LearnerMaterializationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        try(var current=helper().current(f)) {
            var pending=helper().helper().install(f,current.currentHead(),cut);
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                var selected=typed.promoteSlot(current.currentHead());assertThrows(IllegalArgumentException.class,current::currentHead);
                assertThrows(IllegalArgumentException.class,pending::source);return selected;
            }
        }
    }
    void cold(V53LearnerMaterializationTest.Fixture f)throws Exception {
        f.store.close();assertEquals(0,f.source.client.usage().leases());
        f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{});
        try(var typed=helper().current(f)){typed.currentHead().check();assertEquals(f.original,typed.state());}
    }
    @Test void sameTwoPathsAlternateThroughSequenceFourWithColdOwnershipAndNoExtraGeneration()throws Exception {
        try(var f=helper().helper().fixture(3,"ADD")) {
            selectA(f);Path root=MembershipLearnerSlot.directory(f.summary);Object rootKey=MembershipBasisSources.key(root);
            var seed=new TreeMap<>(V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary)));seed.keySet().removeIf(p->p.startsWith("source/"));
            for(long sequence=3;sequence<=4;sequence++) {
                System.out.println("v53LearnerAlternationSequence="+sequence);
                String slot=sequence%2==0?"a":"b";Path plan=root.resolve(slot+".json"),installed=root.resolve(slot+".installed.json");
                Object oldPlan=MembershipBasisSources.key(plan);
                var selected=selectNext(f,e->{
                    if(e.equals("LEARNER_SLOT_CLEAR_ACTIVE_PARENT_FORCED"))assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                });
                assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));selected.retirePredecessor();
                assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
                assertNotEquals(oldPlan,MembershipBasisSources.key(plan));
                assertEquals(hash(Files.readAllBytes(plan)),object(parse(Files.readAllBytes(installed),MembershipLearnerSlot.RECORD_MAXIMUM)).get("plan"));
                var head=object(parse(Files.readAllBytes(root.resolve("head.json")),MembershipLearnerSlot.HEAD_MAXIMUM));
                assertEquals(sequence,number(head.get("sequence")));assertEquals(slot,head.get("slot"));
                assertEquals(rootKey,MembershipBasisSources.key(root));assertFalse(Files.exists(root.resolve("a.next.json")));assertFalse(Files.exists(root.resolve("b.next.json")));
                var before=V53ReplayFilesTest.files(f.base);cold(f);assertEquals(before,V53ReplayFilesTest.files(f.base));
                var original=V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary));
                for(var entry:seed.entrySet())assertEquals(entry.getValue(),original.get(entry.getKey()));
                assertEquals(sequence%2==0?MembershipLearnerSuccessor.typedDirectory(f.summary):MembershipLearnerSlot.typedDirectory(f.summary),f.store.currentSource().typedDirectory());
            }
        }
    }
    @Test void replacementPlanAndDeletedOldMarkerRecoverWithoutRetransferOrEarlySelection()throws Exception {
        try(var f=helper().helper().fixture(4,"REPLACE")) {
            selectA(f);Path root=MembershipLearnerSlot.directory(f.summary);byte[] selectedHead=Files.readAllBytes(root.resolve("head.json"));
            var stopped=new AtomicBoolean();
            try(var current=helper().current(f)) {
                assertThrows(IOException.class,()->helper().helper().install(f,current.currentHead(),e->{if(e.equals("LEARNER_SLOT_REUSE_PLAN_WRITTEN")){stopped.set(true);throw new IOException(e);}}));
            }
            assertTrue(stopped.get());Path next=root.resolve("b.next.json");byte[] plan=Files.readAllBytes(next);Object inode=MembershipBasisSources.key(next);
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            for(String variant:List.of("partial","copied","foreign-replacement","missing-old-marker")) {
                Path keptCandidate=f.base.resolve("kept-candidate"),keptMarker=f.base.resolve("kept-marker");
                if(variant.equals("partial"))Files.write(next,Arrays.copyOf(plan,plan.length/2));
                if(variant.equals("copied")){Files.move(next,keptCandidate);Files.copy(keptCandidate,next);}
                if(variant.equals("foreign-replacement")) {
                    var value=new TreeMap<>(object(parse(plan,MembershipLearnerSlot.MAXIMUM)));var rows=new ArrayList<Object>(list(value.get("replaces")));
                    rows.set(1,Map.of("path",object(rows.get(1)).get("path"),"sha256","0".repeat(64)));value.put("replaces",rows);
                    Files.write(next,canonical(value,MembershipLearnerSlot.MAXIMUM));
                }
                if(variant.equals("missing-old-marker"))Files.move(root.resolve("b.installed.json"),keptMarker);
                var damaged=V53ReplayFilesTest.files(f.base);
                assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly),variant);
                assertEquals(damaged,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
                if(variant.equals("copied")){Files.delete(next);Files.move(keptCandidate,next);}else Files.write(next,plan);
                if(variant.equals("missing-old-marker"))Files.move(keptMarker,root.resolve("b.installed.json"));
                assertEquals(inode,MembershipBasisSources.key(next));assertEquals(before,V53ReplayFilesTest.files(f.base));
            }
            // The candidate cannot authorize replacing a copied old metadata file.
            Path old=root.resolve("b.installed.json"),kept=f.base.resolve("kept-old-installed");Files.move(old,kept);Files.copy(kept,old);
            var changed=V53ReplayFilesTest.files(f.base);
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly));
            assertEquals(changed,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());Files.delete(old);Files.move(kept,old);
            stopped.set(false);f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{if(e.equals("LEARNER_SLOT_OLD_INSTALL_DELETED")){stopped.set(true);throw new IOException(e);}});
            assertEquals(before,V53ReplayFilesTest.files(f.base));
            try(var current=helper().current(f)){assertThrows(IOException.class,()->f.store.resumeSlot(current.currentHead()));}
            assertTrue(stopped.get());assertFalse(Files.exists(old));assertEquals(inode,MembershipBasisSources.key(root.resolve("b.json")));
            assertArrayEquals(plan,Files.readAllBytes(root.resolve("b.json")));assertArrayEquals(selectedHead,Files.readAllBytes(root.resolve("head.json")));
            cold(f);
            try(var current=helper().current(f)) {
                var pending=f.store.resumeSlot(current.currentHead());
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    typed.promoteSlot(current.currentHead()).retirePredecessor();
                }
            }
            assertEquals(inode,MembershipBasisSources.key(root.resolve("b.json")));assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));cold(f);
        }
    }
    @Test void originalClearCandidateAndRenamedClearRecoverAcrossOppositeSlots()throws Exception {
        try(var f=helper().helper().fixture(5,"REPLACE")) {
            selectA(f);long sequence=3;
            for(String event:List.of("LEARNER_SLOT_CLEAR_CANDIDATE_WRITTEN","LEARNER_SLOT_CLEAR_RENAMED")) {
                var stopped=new AtomicBoolean();var selected=selectNext(f,e->{if(e.equals(event)){stopped.set(true);throw new IOException(e);}});
                assertThrows(IOException.class,selected::retirePredecessor);assertTrue(stopped.get());
                Path root=MembershipLearnerSlot.directory(f.summary),original=root.resolve(event.endsWith("WRITTEN")?"cleared.next.json":"cleared.json");
                byte[] bytes=Files.readAllBytes(original);Object key=MembershipBasisSources.key(original);cold(f);
                assertArrayEquals(bytes,Files.readAllBytes(root.resolve("cleared.json")));assertEquals(key,MembershipBasisSources.key(root.resolve("cleared.json")));
                assertFalse(Files.exists(root.resolve("cleared.next.json")));assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));
                assertEquals(sequence++,number(object(parse(Files.readAllBytes(root.resolve("head.json")),MembershipLearnerSlot.HEAD_MAXIMUM)).get("sequence")));
            }
        }
    }
    @Test void sequenceExhaustionFailsWithoutWrapping(){assertEquals(Long.MAX_VALUE,MembershipLearnerSlot.nextSequence(Long.MAX_VALUE-1));assertThrows(IllegalArgumentException.class,()->MembershipLearnerSlot.nextSequence(Long.MAX_VALUE));}
    private void readOnly(String event){if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("invalid alternation forced originals: "+event);}
}
