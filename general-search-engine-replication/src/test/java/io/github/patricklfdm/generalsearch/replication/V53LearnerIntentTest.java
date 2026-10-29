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
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed owners, TCP transfer and filesystem force/recovery. Historical
 * checkpoint voters are conditional fixtures, not native joint-vote evidence. */
class V53LearnerIntentTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo test){System.out.println("v53LearnerIntentCase="+test.getTestMethod().orElseThrow().getName());}
    V53LearnerCancellationTest.Fixture fixture(String phase,int size,String kind,boolean promoted)throws Exception {
        var helper=new V53LearnerCancellationTest();helper.temp=temp;return helper.new Fixture(phase,size,kind,promoted);
    }
    V53LearnerCancellationTest.Fixture fixture(String phase)throws Exception{return fixture(phase,3,"ADD",false);}
    static Path directory(V53LearnerCancellationTest.Fixture f){return MembershipLearnerIntent.directory(f.local.summary);}
    static MembershipLearnerIntent retain(V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws IOException {
        try(var progress=f.progress()){progress.fetch(f.local.base.resolve("progress"));return progress.retainIntent(cut);}
    }
    @Test void allJoiningShapesRequireTheirActualTypedReceiptAtJointAndFinal()throws Exception {
        for(String phase:List.of("JOINT","COMPLETED"))for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            System.out.println("v53LearnerIntentProfile="+phase+":"+size+":"+kind);
            try(var f=fixture(phase,size,kind,false);var intent=retain(f,e->{})) {
                assertEquals(phase,intent.result().get("phase"));
                assertEquals(object(f.head.receipt().value().get("receipt")),intent.result().get("receipt"));
                assertEquals(intent.result(),MembershipLearnerProgressAccess.operation(intent.forced().source().context,f.head.request().identity()));
                assertFalse(Files.exists(f.local.config.materialization().directory()));
            }
        }
    }
    @Test void forcePrecedesCapabilityAndRestartKeepsOriginalsWithoutInstallingAVoter()throws Exception {
        try(var f=fixture("JOINT");var pending=MembershipLearnerSource.refresh(f.head,f.peer.owner.activationIdentity(),f.local.config.bounds(),
                MembershipTransport.Events.NONE,()->0L,0L,TimeUnit.SECONDS.toNanos(60));
                var stale=new MembershipLearnerProgress(f.head,f.peer.owner.activationIdentity(),f.local.config.bounds(),MembershipTransport.Events.NONE,
                        ()->0L,0L,TimeUnit.SECONDS.toNanos(60))) {
            var replica=V53ReplayFilesTest.files(f.local.source.request.replicaDirectory());var typed=V53ReplayFilesTest.files(f.local.typed());
            var usage=f.local.source.client.usage();var events=new ArrayList<String>();MembershipLearnerIntent.Forced capability;
            try(var intent=retain(f,events::add)) {
                capability=intent.forced();capability.check();
                assertTrue(events.indexOf("LEARNER_INTENT_ACTIVE_PLAN_FORCED")<events.indexOf("LEARNER_INTENT_SOURCE_MOVED"));
                assertTrue(events.indexOf("LEARNER_INTENT_SOURCE_PARENTS_FORCED")<events.indexOf("LEARNER_INTENT_BEFORE_RETURN"));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                assertThrows(IllegalArgumentException.class,f::progress);
                assertThrows(IllegalArgumentException.class,()->pending.fetch(f.local.base.resolve("stale-refresh")));
                assertThrows(IllegalArgumentException.class,()->stale.fetch(f.local.base.resolve("stale-progress")));
                assertFalse(Files.exists(f.local.base.resolve("stale-refresh")));assertFalse(Files.exists(f.local.base.resolve("stale-progress")));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.head,e->fail("duplicate owner must not force")));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("INTENT cannot become CANCEL")));
            }
            assertThrows(IllegalArgumentException.class,capability::check);assertEquals(usage,f.local.source.client.usage());
            var originals=V53ReplayFilesTest.files(directory(f));f.reopen();
            try(var restored=MembershipLearnerIntent.resume(f.head,e->{})) {
                assertEquals("JOINT",restored.result().get("phase"));restored.forced().check();
                assertEquals(originals,V53ReplayFilesTest.files(directory(f)));assertEquals(replica,V53ReplayFilesTest.files(f.local.source.request.replicaDirectory()));
                assertEquals(typed,V53ReplayFilesTest.files(f.local.typed()));assertFalse(Files.exists(f.local.config.materialization().directory()));
                assertThrows(IllegalArgumentException.class,f.local.store::requireNewSlot);assertThrows(IllegalArgumentException.class,f.local.store::requireNewSuccessor);
            }
        }
    }
    @Test void promotedHeadReopensTheSameIntentAndCloseRevokesItsCapability()throws Exception {
        try(var f=fixture("COMPLETED",3,"REPLACE",true)) {
            try(var intent=retain(f,e->{})){intent.forced().check();}
            f.typed.close();f.local.reopen();
            f.typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.local.store.currentSource(),1),f.local.captured,f.local.config,e->{});
            f.head=f.typed.currentHead();
            try(var intent=MembershipLearnerIntent.resume(f.head,e->{})) {
                var capability=intent.forced();assertEquals("COMPLETED",intent.result().get("phase"));
                f.local.store.close();assertThrows(IllegalArgumentException.class,capability::check);assertEquals(0,f.local.source.client.usage().leases());
            }
        }
    }
    @Test void everyTransactionCutPreservesIncompleteBytesOrResealsTheExactOriginal()throws Exception {
        var early=Set.of("DIRECTORY_FORCED","PLAN_CREATED","PLAN_PREFIX_WRITTEN");
        for(String cut:List.of("DIRECTORY_FORCED","PLAN_CREATED","PLAN_PREFIX_WRITTEN","PLAN_WRITTEN","PLAN_FORCED",
                "PLAN_PARENT_FORCED","RESEAL_FORCED","PLAN_RENAMED","ACTIVE_PLAN_FORCED","SOURCE_MOVED",
                "SOURCE_MEMBER_FORCED","SOURCE_PARENTS_FORCED","BEFORE_RETURN"))try(var f=fixture("JOINT")) {
            String event="LEARNER_INTENT_"+cut;System.out.println("v53LearnerIntentCut="+event);var reached=new AtomicBoolean();
            var error=assertThrows(IOException.class,()->retain(f,point->{if(point.equals(event)&&reached.compareAndSet(false,true))throw new IOException(event);}));
            assertTrue(reached.get());assertEquals(event,error.getMessage());assertThrows(IllegalArgumentException.class,f.local.store::requireActive);
            f.reopen();var before=V53ReplayFilesTest.files(directory(f));var usage=f.local.source.client.usage();
            if(early.contains(cut)) {
                assertThrows(Exception.class,()->MembershipLearnerIntent.resume(f.head,e->fail("incomplete plan must not write")));
                assertEquals(before,V53ReplayFilesTest.files(directory(f)));assertEquals(usage,f.local.source.client.usage());
            }else try(var restored=MembershipLearnerIntent.resume(f.head,e->{})) {
                restored.forced().check();assertFalse(Files.exists(directory(f).resolve(MembershipLearnerIntent.NEXT)));
                assertFalse(Files.exists(f.local.base.resolve("progress")));
            }
        }
    }
    @Test void preparationSealAndCancellationAreNotIntentAuthority()throws Exception {
        for(String phase:List.of("PREPARING","READY","SEALED","CANCELLED"))try(var f=fixture(phase);var progress=f.progress()) {
            progress.fetch(f.local.base.resolve("progress"));
            assertThrows(IllegalArgumentException.class,()->progress.retainIntent(e->fail("no INTENT must not write")));
            assertFalse(Files.exists(directory(f)));f.local.store.requireActive();
        }
        try(var f=fixture("CANCELLED");var cancel=f.retain(e->{})) {
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.head,e->fail("CANCEL cannot become INTENT")));
        }
    }
    @Test void expiryBeforeOrDuringForceNeverGrantsIntentAndReleasesReceivingReservations()throws Exception {
        for(boolean during:List.of(false,true))try(var f=fixture("JOINT")) {
            var usage=f.local.source.client.usage();
            try(var progress=f.progress()) {
                progress.fetch(f.local.base.resolve("progress"));
                if(!during)f.progressClock.addAndGet(TimeUnit.SECONDS.toNanos(60));
                var hit=new AtomicBoolean();
                assertThrows(IllegalArgumentException.class,()->progress.retainIntent(event->{
                    if(during && event.equals("LEARNER_SOURCE_MEMBER_FORCED")){hit.set(true);f.progressClock.addAndGet(TimeUnit.SECONDS.toNanos(60));}
                }));
                assertEquals(during,hit.get());assertFalse(Files.exists(directory(f)));
            }
            assertEquals(usage,f.local.source.client.usage());f.local.store.requireActive();
        }
    }
    @Test void aCertifiedLaterRevisionCannotAdmitTheOldTypedReceipt()throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var local=helper.new Fixture();var typed=local.prepare(e->{})) {
            var head=typed.retainGeneration();var history=local.source.fixture.fixture.source;
            var original=V53CapsuleFixture.fromHistory(history,3);
            history.state=object(V53ContextFixture.mutable(original.state(3)));history.steps.subList(3,history.steps.size()).clear();
            var prepared=Map.of("application",history.state.get("application"),"catalog",history.catalog().digest(),
                    "cut",V53ContextFixture.mutable(history.state.get("cut")),"revision",2L);
            history.commit("PREPARE",Map.of("number",1L,"revision",2L),()->{
                history.operation().put("revision",2L);history.operation().put("prepared",prepared);
            });
            var request=history.operation().get("request");var receipt=Map.of("identity",V53ContextFixture.member(6),"image",history.state.get("application"),
                    "number",1L,"prepared",prepared,"request",hash(canonical(request,8192)),"root",history.rootHash);
            history.commit("READY",Map.of("number",1L,"receipt",receipt),()->{history.operation().put("phase","READY");history.operation().put("receipt",receipt);});
            var descriptor=Map.of("request",request,"prepared",prepared,"receipt",receipt);String binding=hash(canonical(descriptor,8192));history.put(canonical(descriptor,8192));
            history.commit("SEAL",Map.of("number",1L),()->{history.operation().put("phase","SEALED");history.operation().put("binding",binding);});
            history.commit("INTENT",Map.of("sealed",descriptor),()->{
                history.operation().put("phase","JOINT");var view=object(object(history.state.get("cut")).get("view"));
                view.put("new",V53ContextFixture.names(history.target));view.put("operation",binding);
            });
            var fixture=V53CapsuleFixture.fromHistory(history,7);var bridge=V53LearnerProgressNetworkTest.bridge(fixture,3,6);
            var source=fixture.verify().retainingVerifiedAncestry(List.of(bridge));var before=V53ReplayFilesTest.files(local.typed());
            var error=assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.match(head,source,
                    source.context.identities.get("node-1"),MembershipGenerationPlan.ancestry(List.of(bridge))));
            assertEquals("learner INTENT differs from forced typed receipt",error.getMessage());
            assertEquals(before,V53ReplayFilesTest.files(local.typed()));assertFalse(Files.exists(MembershipLearnerIntent.directory(local.summary)));
        }
    }
    @Test void originalInventoryReceiptAndInodeChangesRefuseBeforeRecoveryWrites()throws Exception {
        try(var f=fixture("JOINT")) {
            try(var intent=retain(f,e->{})){intent.forced().check();}
            var usage=f.local.source.client.usage();Path source=directory(f).resolve("source"),plan=directory(f).resolve(MembershipLearnerIntent.PLAN);
            var members=new ArrayList<Path>();members.add(plan);try(var files=Files.list(source)){members.addAll(files.sorted().toList());}
            for(Path member:members) {
                byte[] bytes=Files.readAllBytes(member),broken=bytes.clone();broken[broken.length/2]^=1;Files.write(member,broken);
                var before=V53ReplayFilesTest.files(directory(f));
                assertThrows(Exception.class,()->MembershipLearnerIntent.resume(f.head,e->fail("damaged original must not write")));
                assertEquals(before,V53ReplayFilesTest.files(directory(f)));assertEquals(usage,f.local.source.client.usage());Files.write(member,bytes);
            }
            byte[] bytes=Files.readAllBytes(plan);var value=new TreeMap<>(object(parse(bytes,MembershipLearnerDisposition.MAXIMUM)));value.put("receipt","ab".repeat(32));
            Files.write(plan,canonical(value,MembershipLearnerDisposition.MAXIMUM));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.head,e->fail("different typed receipt must not write")));Files.write(plan,bytes);
            for(Path parent:List.of(directory(f),source)) {
                Path extra=parent.resolve("foreign.gsr");Files.write(extra,new byte[]{1});var before=V53ReplayFilesTest.files(directory(f));
                assertThrows(Exception.class,()->MembershipLearnerIntent.resume(f.head,e->fail("unknown original must not write")));
                assertEquals(before,V53ReplayFilesTest.files(directory(f)));assertEquals(usage,f.local.source.client.usage());Files.delete(extra);
            }
            Path member=source.resolve("source.gscp"),aside=f.local.base.resolve("original-source");Files.move(member,aside);Files.copy(aside,member);
            assertThrows(Exception.class,()->MembershipLearnerIntent.resume(f.head,e->fail("copied inode must not write")));
            Files.delete(member);Files.move(aside,member);
            try(var restored=MembershipLearnerIntent.resume(f.head,e->{})){restored.forced().check();}assertEquals(usage,f.local.source.client.usage());
        }
    }
    @Test void retainedIntentCannotRepairItsMissingTypedReceiptOrPreparedMarker()throws Exception {
        try(var f=fixture("JOINT")) {
            try(var intent=retain(f,e->{})){intent.forced().check();}f.typed.close();
            for(String name:List.of(MembershipLearnerMaterialization.PREPARED,MembershipLearnerMaterialization.RECEIPT)) {
                Path path=f.local.typed().resolve(name),aside=f.local.base.resolve("saved-"+name);Files.move(path,aside);
                var before=V53ReplayFilesTest.files(f.local.typed());
                assertThrows(Exception.class,()->f.local.prepare(e->fail("missing original must not be reconstructed")));
                assertEquals(before,V53ReplayFilesTest.files(f.local.typed()));Files.move(aside,path);
            }
            f.typed=f.local.prepare(e->{});f.head=f.typed.retainGeneration();
            try(var restored=MembershipLearnerIntent.resume(f.head,e->{})){restored.forced().check();}
        }
    }
    @Test void receivingBudgetStillAppliesOnColdRecoveryAndNoExtraVotingGenerationIsReserved()throws Exception {
        try(var f=fixture("JOINT")) {
            try(var intent=retain(f,e->{})){intent.forced().check();}var before=V53ReplayFilesTest.files(directory(f));var usage=f.local.source.client.usage();
            try(var busy=f.local.source.client.reserve(MembershipResources.Unit.LEARNER,"occupied",1)) {
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.head,e->fail("capacity refusal must not write")));
                assertEquals(before,V53ReplayFilesTest.files(directory(f)));
            }
            assertEquals(usage,f.local.source.client.usage());
            try(var second=f.local.source.client.reserve(MembershipResources.Unit.GENERATION,"second",1);var restored=MembershipLearnerIntent.resume(f.head,e->{})) {
                restored.forced().check();assertEquals(2,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
            }
            assertEquals(usage,f.local.source.client.usage());
        }
    }
}
