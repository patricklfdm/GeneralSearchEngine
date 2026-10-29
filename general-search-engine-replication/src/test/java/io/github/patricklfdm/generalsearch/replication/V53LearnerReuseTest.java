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

/** Real original transfer/typed decode; conditional voting fixture. The pending
 * reused image is deliberately not selected or made a voter by this batch. */
class V53LearnerReuseTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerReuseCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerSlotTest helper(){var h=new V53LearnerSlotTest();h.temp=temp;return h;}
    void select(V53LearnerMaterializationTest.Fixture f)throws Exception {
        var vacancy=new V53LearnerVacancyTest();vacancy.temp=temp;vacancy.selected(f,e->{}).retirePredecessor();
    }
    MembershipLearnerMaterialization<io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc> current(V53LearnerMaterializationTest.Fixture f)throws Exception {
        return MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{});
    }
    @Test void originalVacancyAllowsOneTcpReuseAndColdReopenWithoutDeletingTheNewImage()throws Exception {
        try(var f=helper().fixture(3,"ADD");var server=new MembershipTransport(f.source.owner,f.config.bounds(),f.source.server,
                (sender,frame)->frame.kind().equals("STATUS_PROBE")?f.source.owner.discoveryStatus(sender,frame):f.source.service.handle(sender,frame),MembershipTransport.Events.NONE)) {
            select(f);var seedBefore=V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary));
            Path root=MembershipLearnerSlot.directory(f.summary),head=root.resolve(MembershipLearnerSlot.HEAD),clear=root.resolve(MembershipLearnerSlot.CLEARED);
            byte[] headBytes=Files.readAllBytes(head),clearBytes=Files.readAllBytes(clear),receipt;
            Object clearKey=MembershipBasisSources.key(clear);MembershipLearnerSlot.View retained;
            try(var active=current(f)) {
                try(var refresh=MembershipLearnerSource.refresh(active.currentHead(),f.source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                        System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(300))) {
                    refresh.fetch(f.base.resolve("reused-source"));retained=refresh.installSlot(e->{});
                }
                // Acquisition has closed; retained checks must not retain its callback.
                active.currentHead().check();retained.source();
                assertEquals(MembershipLearnerSuccessor.typedDirectory(f.summary),retained.typedDirectory());
                assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
                assertFalse(f.source.client.usage().counts().containsKey(Unit.LEARNER));
                assertThrows(IllegalArgumentException.class,active.currentHead()::requireAvailable);
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(retained,1),f.captured,f.config,e->{})) {
                    assertEquals(f.original,typed.state());receipt=typed.receipt().bytes();
                    assertThrows(IllegalArgumentException.class,typed::currentHead);
                }
                assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
                ((MembershipLearnerSlot.View)f.store.currentSource()).retirePredecessor();
                assertTrue(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.SOURCE)));
                assertArrayEquals(headBytes,Files.readAllBytes(head));assertArrayEquals(clearBytes,Files.readAllBytes(clear));assertEquals(clearKey,MembershipBasisSources.key(clear));
            }
            // Old immutable seed metadata was not replaced by a second A plan.
            var seedAfter=V53ReplayFilesTest.files(MembershipLearnerSuccessor.directory(f.summary));
            for(var entry:seedBefore.entrySet())assertEquals(entry.getValue(),seedAfter.get(entry.getKey()));
            f.store.close();assertThrows(IllegalArgumentException.class,retained::source);assertEquals(0,f.source.client.usage().leases());
            var originals=V53ReplayFilesTest.files(f.base);f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{});
            assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(4,f.source.client.usage().counts().get(Unit.APPLICATION));
            try(var active=current(f)) {
                retained=f.store.resumeSlot(active.currentHead());
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(retained,1),f.captured,f.config,e->{})) {
                    assertArrayEquals(receipt,typed.receipt().bytes());assertEquals(f.original,typed.state());active.currentHead().check();
                }
            }
            assertEquals(originals,V53ReplayFilesTest.files(f.base));f.store.close();assertEquals(0,f.source.client.usage().leases());
            // Byte-identical replacement is not the original self-bound plan.
            Path plan=root.resolve("a.json"),kept=f.base.resolve("kept-a-plan");Files.move(plan,kept);Files.copy(kept,plan);
            var changed=V53ReplayFilesTest.files(f.base);
            assertEquals("learner reuse original plan inode changed",assertThrows(IllegalArgumentException.class,()->
                    MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly)).getMessage());
            assertEquals(changed,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
            Files.delete(plan);Files.move(kept,plan);byte[] originalPlan=Files.readAllBytes(plan);
            for(String changedField:List.of("vacancy","anchor","sequence")) {
                var value=new TreeMap<>(MembershipFormat.object(MembershipFormat.parse(originalPlan,MembershipLearnerSlot.MAXIMUM)));
                if(changedField.equals("sequence"))value.put("sequence",Long.MAX_VALUE);
                else {
                    var binding=new TreeMap<>(MembershipFormat.object(value.get(changedField)));binding.put("head","0".repeat(64));value.put(changedField,binding);
                }
                Files.write(plan,MembershipFormat.canonical(value,MembershipLearnerSlot.MAXIMUM));changed=V53ReplayFilesTest.files(f.base);
                String reason=changedField.equals("vacancy")?"learner reuse vacancy head binding":
                        changedField.equals("anchor")?"learner slot original current head changed":"learner slot original plan";
                assertEquals(reason,assertThrows(IllegalArgumentException.class,()->
                        MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly)).getMessage());
                assertEquals(changed,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());Files.write(plan,originalPlan);
            }
            // Even coherently rebound metadata cannot omit the old inventory
            // shape checks just because new A has occupied the cleared paths.
            var headValue=new TreeMap<>(MembershipFormat.object(MembershipFormat.parse(headBytes,MembershipLearnerSlot.HEAD_MAXIMUM)));
            headValue.put("previousTyped",List.of());byte[] alteredHead=MembershipFormat.canonical(headValue,MembershipLearnerSlot.HEAD_MAXIMUM);
            var clearValue=new TreeMap<>(MembershipFormat.object(MembershipFormat.parse(clearBytes,MembershipLearnerSlot.HEAD_MAXIMUM)));
            clearValue.put("head",MembershipFormat.hash(alteredHead));clearValue.put("previousTyped",MembershipFormat.hash(MembershipFormat.canonical(List.of(),MembershipLearnerSlot.HEAD_MAXIMUM)));
            byte[] alteredClear=MembershipFormat.canonical(clearValue,MembershipLearnerSlot.HEAD_MAXIMUM);
            var planValue=new TreeMap<>(MembershipFormat.object(MembershipFormat.parse(originalPlan,MembershipLearnerSlot.MAXIMUM)));
            var vacancy=new TreeMap<>(MembershipFormat.object(planValue.get("vacancy")));vacancy.put("head",MembershipFormat.hash(alteredHead));vacancy.put("cleared",MembershipFormat.hash(alteredClear));planValue.put("vacancy",vacancy);
            var anchor=new TreeMap<>(MembershipFormat.object(planValue.get("anchor")));anchor.put("head",MembershipFormat.hash(alteredHead));planValue.put("anchor",anchor);
            byte[] alteredPlan=MembershipFormat.canonical(planValue,MembershipLearnerSlot.MAXIMUM);
            Path installed=root.resolve("a.installed.json");byte[] originalInstalled=Files.readAllBytes(installed);
            var installedValue=new TreeMap<>(MembershipFormat.object(MembershipFormat.parse(originalInstalled,MembershipLearnerSlot.RECORD_MAXIMUM)));
            installedValue.put("plan",MembershipFormat.hash(alteredPlan));
            Files.write(head,alteredHead);Files.write(clear,alteredClear);Files.write(plan,alteredPlan);
            Files.write(installed,MembershipFormat.canonical(installedValue,MembershipLearnerSlot.RECORD_MAXIMUM));
            changed=V53ReplayFilesTest.files(f.base);
            assertEquals("learner slot fingerprint paths/fields",assertThrows(IllegalArgumentException.class,()->
                    MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly)).getMessage());
            assertEquals(changed,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
            Files.write(head,headBytes);Files.write(clear,clearBytes);Files.write(plan,originalPlan);Files.write(installed,originalInstalled);
            assertTrue(MembershipLearnerSlot.METADATA_MAXIMUM<=Unit.MISC.bytes);
        }
    }
    @Test void originalReusePlanAndMovedImageResumeWithoutRetransfer()throws Exception {
        for(String event:List.of("LEARNER_SLOT_REUSE_PLAN_WRITTEN","LEARNER_SLOT_SOURCE_MOVED")) {
            System.out.println("v53LearnerReuseCut="+event);
            try(var f=helper().fixture(4,"REPLACE")) {
                select(f);var reached=new AtomicBoolean();
                try(var active=current(f)) {
                    assertThrows(IOException.class,()->helper().install(f,active.currentHead(),e->{if(e.equals(event)){reached.set(true);throw new IOException(e);}}));
                    assertTrue(reached.get());assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION)+f.source.client.usage().counts().getOrDefault(Unit.LEARNER,0));
                }
                f.store.close();Path root=MembershipLearnerSlot.directory(f.summary),original=root.resolve(event.endsWith("WRITTEN")?"a.next.json":"a.json");
                byte[] plan=Files.readAllBytes(original);Object key=MembershipBasisSources.key(original);
                f.store=MembershipLearnerStore.resume(f.summary,f.source.client,e->{});
                try(var active=current(f)) {
                    var pending=f.store.resumeSlot(active.currentHead());
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                        assertEquals(f.original,typed.state());active.currentHead().check();
                    }
                }
                assertEquals(key,MembershipBasisSources.key(root.resolve("a.json")));assertArrayEquals(plan,Files.readAllBytes(root.resolve("a.json")));
                assertFalse(Files.exists(root.resolve("a.next.json")));assertEquals(2,f.source.client.usage().counts().get(Unit.GENERATION));
            }
        }
    }
    @Test void partialReusePlanIsPreservedAndCannotWaiveOldPathChecks()throws Exception {
        try(var f=helper().fixture(5,"REPLACE")) {
            select(f);var reached=new AtomicBoolean();
            try(var active=current(f)) {
                assertThrows(IOException.class,()->helper().install(f,active.currentHead(),e->{if(e.equals("LEARNER_SLOT_REUSE_PLAN_PREFIX_WRITTEN")){reached.set(true);throw new IOException(e);}}));
                assertTrue(reached.get());
            }
            f.store.close();var before=V53ReplayFilesTest.files(f.base);
            assertThrows(RuntimeException.class,()->MembershipLearnerStore.resume(f.summary,f.source.client,this::readOnly));
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(0,f.source.client.usage().leases());
        }
    }
    private void readOnly(String event){if(!event.equals("LEARNER_REPLICA_LOCKED"))throw new AssertionError("invalid reuse forced originals: "+event);}
}
