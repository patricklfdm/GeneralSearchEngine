package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestInfo;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed preparation/TCP/durable originals; historical source quorums are
 * conditional fixtures. Injected IOException is not halt/SIGKILL qualification. */
class V53LearnerCancellationTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerCancellationCase="+info.getTestMethod().orElseThrow().getName());}
    final class Fixture implements AutoCloseable {
        final V53LearnerMaterializationTest.Fixture local;
        final V53LearnerProgressNetworkTest.Peer peer;
        final MembershipTransport server;
        // This fixture qualifies storage transitions, not a wall-clock SLA.
        // A controlled receive clock permits deterministic expiry injection;
        // real transport/exchange deadlines and production budgets are unchanged.
        final AtomicLong progressClock=new AtomicLong();
        MembershipLearnerMaterialization<?> typed;
        MembershipLearnerHead head;
        Fixture(String phase)throws Exception {this(phase,3,"ADD");}
        Fixture(String phase,int size,String kind)throws Exception {this(phase,size,kind,false);}
        Fixture(String phase,int size,String kind,boolean promoted)throws Exception {
            var helper=new V53LearnerMaterializationTest();helper.temp=temp;local=helper.new Fixture(size,kind);typed=local.prepare(e->{});head=typed.retainGeneration();
            if(promoted) {
                var successor=new V53LearnerSuccessorTest();successor.temp=temp;
                var installed=successor.install(local,(MembershipLearnerMaterialization.PreparedGeneration)head,e->{});
                var next=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,1),local.captured,local.config,e->{});
                var current=next.promoteSuccessor();current.retirePredecessor();
                typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(current,1),local.captured,local.config,e->{});head=typed.currentHead();
            }
            // Begin the source export lifetime after local preparation, so this
            // test measures cancellation rather than consuming its transfer
            // budget on unrelated setup. The production deadline stays unchanged.
            var initial=local.source.fixture.fixture;
            var next=phase.equals("CANCELLED")?V53LearnerProgressTest.cancelled(initial,3):
                    V53CapsuleFixture.fromHistory(initial.source,Map.of("PREPARING",3,"READY",4,"SEALED",5,"JOINT",6,"COMPLETED",7).get(phase));
            var network=new V53LearnerProgressNetworkTest();network.temp=temp;peer=network.new Peer(next,!phase.equals("PREPARING"));
            server=new MembershipTransport(peer.owner,local.config.bounds(),peer.server,(sender,request)->
                    request.kind().equals("STATUS_PROBE")?MembershipDiscovery.answer(peer.owner.activationContext(),peer.owner.activationIdentity(),sender,request):
                            peer.service.handle(sender,request),MembershipTransport.Events.NONE);
        }
        MembershipLearnerProgress progress()throws IOException {
            long started=System.nanoTime();progressClock.set(started);
            return new MembershipLearnerProgress(head,peer.owner.activationIdentity(),local.config.bounds(),MembershipTransport.Events.NONE,
                    progressClock::get,started,TimeUnit.SECONDS.toNanos(60));
        }
        Path directory(){return MembershipLearnerCancellation.directory(local.summary);}
        MembershipLearnerCancellation retain(MembershipBallotAllocator.Cut cut)throws IOException {
            try(var progress=progress()){progress.fetch(local.base.resolve("progress"));return progress.retainCancellation(cut);}
        }
        void reopen()throws Exception {typed.close();local.reopen();typed=local.prepare(e->{});head=typed.retainGeneration();}
        @Override public void close()throws Exception {typed.close();server.close();peer.close();local.close();}
    }
    @Test void allFiveJoiningShapesRetainTheSameOriginalCancellation()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            try(var f=new Fixture("CANCELLED",size,kind);var cancellation=f.retain(e->{})) {
                assertEquals("CANCELLED",cancellation.result().get("phase"));
                assertEquals(MembershipLearnerDiscovery.request(f.local.source.request.change()),cancellation.result().get("request"));
                assertFalse(Files.exists(f.local.config.materialization().directory()));
            }
        }
    }
    @Test void forcedCancellationSurvivesOwnerRestartAndStopsOldPreparationWithoutVotingOrDeleting()throws Exception {
        try(var f=new Fixture("CANCELLED");var pending=MembershipLearnerSource.refresh(f.head,f.peer.owner.activationIdentity(),f.local.config.bounds(),
                    MembershipTransport.Events.NONE,()->0L,0L,TimeUnit.SECONDS.toNanos(60));
                var stale=new MembershipLearnerProgress(f.head,f.peer.owner.activationIdentity(),f.local.config.bounds(),MembershipTransport.Events.NONE,
                        ()->0L,0L,TimeUnit.SECONDS.toNanos(60))) {
            var old=V53ReplayFilesTest.files(f.local.source.request.replicaDirectory());var typed=V53ReplayFilesTest.files(f.local.typed());
            var usage=f.local.source.client.usage();var events=new ArrayList<String>();
            try(var cancellation=f.retain(events::add)) {
                assertEquals("CANCELLED",cancellation.result().get("phase"));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                assertTrue(events.indexOf("LEARNER_CANCEL_ACTIVE_PLAN_FORCED")<events.indexOf("LEARNER_CANCEL_SOURCE_MOVED"));
                assertTrue(events.indexOf("LEARNER_CANCEL_SOURCE_PARENTS_FORCED")<events.indexOf("LEARNER_CANCEL_BEFORE_RETURN"));
                assertThrows(IllegalArgumentException.class,f::progress);
                assertEquals("learner cancellation requires original recovery; preparation stopped",assertThrows(IllegalArgumentException.class,
                        ()->pending.fetch(f.local.base.resolve("stale-refresh"))).getMessage());
                assertEquals("learner cancellation requires original recovery; preparation stopped",assertThrows(IllegalArgumentException.class,
                        ()->stale.fetch(f.local.base.resolve("stale-progress"))).getMessage());
                assertFalse(Files.exists(f.local.base.resolve("stale-refresh")));assertFalse(Files.exists(f.local.base.resolve("stale-progress")));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerSource.refresh(f.head,f.peer.owner.activationIdentity(),f.local.config.bounds(),
                        MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60)));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerCancellation.resume(f.head,e->{}));
            }
            assertEquals(usage,f.local.source.client.usage());assertTrue(Files.isDirectory(f.directory().resolve("source")));
            assertEquals(old,V53ReplayFilesTest.files(f.local.source.request.replicaDirectory()));assertEquals(typed,V53ReplayFilesTest.files(f.local.typed()));
            var originals=V53ReplayFilesTest.files(f.directory());f.reopen();
            try(var restored=MembershipLearnerCancellation.resume(f.head,e->{})) {
                assertEquals("CANCELLED",restored.result().get("phase"));assertEquals(originals,V53ReplayFilesTest.files(f.directory()));
                assertThrows(IllegalArgumentException.class,f.local.store::requireActive);
                assertThrows(IllegalArgumentException.class,f.local.store::requireNewSuccessor);
                assertFalse(Files.exists(f.local.config.materialization().directory()));
            }
        }
    }
    @Test void promotedCurrentHeadAlsoRetainsAndReopensCancellationWithoutAnotherGeneration()throws Exception {
        try(var f=new Fixture("CANCELLED",3,"ADD",true)) {
            try(var cancellation=f.retain(e->{})) {
                assertEquals("CANCELLED",cancellation.result().get("phase"));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertThrows(IllegalArgumentException.class,()->f.typed.promoteSuccessor());
            }
            f.typed.close();f.local.reopen();
            f.typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.local.store.currentSource(),1),f.local.captured,f.local.config,e->{});
            f.head=f.typed.currentHead();
            try(var cancellation=MembershipLearnerCancellation.resume(f.head,e->{})) {
                assertEquals("CANCELLED",cancellation.result().get("phase"));assertThrows(IllegalArgumentException.class,f.local.store::requireNewSlot);
            }
        }
    }
    @Test void everyOriginalTransactionCutEitherResealsExactProofOrPreservesIncompleteOriginals()throws Exception {
        var early=Set.of("LEARNER_CANCEL_DIRECTORY_FORCED","LEARNER_CANCEL_PLAN_CREATED","LEARNER_CANCEL_PLAN_PREFIX_WRITTEN");
        for(String event:List.of("LEARNER_CANCEL_DIRECTORY_FORCED","LEARNER_CANCEL_PLAN_CREATED","LEARNER_CANCEL_PLAN_PREFIX_WRITTEN",
                "LEARNER_CANCEL_PLAN_WRITTEN","LEARNER_CANCEL_PLAN_FORCED","LEARNER_CANCEL_PLAN_PARENT_FORCED","LEARNER_CANCEL_RESEAL_FORCED",
                "LEARNER_CANCEL_PLAN_RENAMED","LEARNER_CANCEL_ACTIVE_PLAN_FORCED","LEARNER_CANCEL_SOURCE_MOVED",
                "LEARNER_CANCEL_SOURCE_MEMBER_FORCED","LEARNER_CANCEL_SOURCE_PARENTS_FORCED","LEARNER_CANCEL_BEFORE_RETURN")) {
            System.out.println("v53LearnerCancellationCut="+event);
            try(var f=new Fixture("CANCELLED")) {
                var hit=new AtomicBoolean();var error=assertThrows(IOException.class,()->f.retain(cut->{if(cut.equals(event)&&hit.compareAndSet(false,true))throw new IOException(event);}));
                assertEquals(event,error.getMessage());assertTrue(hit.get());assertThrows(IllegalArgumentException.class,f.local.store::requireActive);
                f.reopen();var before=V53ReplayFilesTest.files(f.directory());var usage=f.local.source.client.usage();
                if(early.contains(event)) {
                    assertThrows(Exception.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("invalid original must not write")));
                    assertEquals(before,V53ReplayFilesTest.files(f.directory()));assertEquals(usage,f.local.source.client.usage());
                }else try(var recovered=MembershipLearnerCancellation.resume(f.head,e->{})) {
                    assertEquals("CANCELLED",recovered.result().get("phase"));assertFalse(Files.exists(f.directory().resolve(MembershipLearnerCancellation.NEXT)));
                    assertFalse(Files.exists(f.local.base.resolve("progress")));
                }
            }
        }
    }
    @Test void otherCertifiedPhasesCannotBeRetainedAsCancellation()throws Exception {
        for(String phase:List.of("READY","SEALED","JOINT","COMPLETED"))try(var f=new Fixture(phase);var progress=f.progress()) {
            progress.fetch(f.local.base.resolve("progress"));
            assertThrows(IllegalArgumentException.class,()->progress.retainCancellation(e->fail("noncancelled source must not write")));
            assertFalse(Files.exists(f.directory()));f.local.store.requireActive();
        }
    }
    @Test void damagedOriginalsAndForeignMembersFailBeforeRecoveryWritesAndReleaseAllReservations()throws Exception {
        try(var f=new Fixture("CANCELLED")) {
            try(var cancellation=f.retain(e->{})){cancellation.result();}
            var usage=f.local.source.client.usage();Path source=f.directory().resolve("source");
            var members=new ArrayList<Path>();members.add(f.directory().resolve(MembershipLearnerCancellation.PLAN));
            try(var files=Files.list(source)){members.addAll(files.sorted().toList());}
            for(Path member:members) {
                byte[] bytes=Files.readAllBytes(member);byte[] broken=bytes.clone();broken[broken.length/2]^=1;Files.write(member,broken);
                var invalid=V53ReplayFilesTest.files(f.directory());
                assertThrows(Exception.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("damaged original must not write")));
                assertEquals(invalid,V53ReplayFilesTest.files(f.directory()));assertEquals(usage,f.local.source.client.usage());Files.write(member,bytes);
            }
            for(Path parent:List.of(f.directory(),source)) {
                Path extra=parent.resolve("foreign.gsr");Files.write(extra,new byte[]{1});
                var invalid=V53ReplayFilesTest.files(f.directory());
                assertThrows(Exception.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("unknown original must not write")));
                assertEquals(invalid,V53ReplayFilesTest.files(f.directory()));assertEquals(usage,f.local.source.client.usage());Files.delete(extra);
            }
            Path member=source.resolve("source.gscp"),aside=f.local.base.resolve("original-source");Files.move(member,aside);
            assertThrows(Exception.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("missing original must not write")));
            Files.copy(aside,member);assertThrows(Exception.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("copied inode must not write")));
            Files.delete(member);Files.move(aside,member);
            try(var recovered=MembershipLearnerCancellation.resume(f.head,e->{})){assertEquals("CANCELLED",recovered.result().get("phase"));}
            assertEquals(usage,f.local.source.client.usage());
        }
    }
    @Test void cancellationDoesNotRepairMissingOriginalPreparedMarkerOrTypedReceipt()throws Exception {
        try(var f=new Fixture("CANCELLED")) {
            try(var cancellation=f.retain(e->{})){cancellation.result();}f.typed.close();
            for(String name:List.of(MembershipLearnerMaterialization.PREPARED,MembershipLearnerMaterialization.RECEIPT)) {
                Path path=f.local.typed().resolve(name),aside=f.local.base.resolve("saved-"+name);Files.move(path,aside);
                var before=V53ReplayFilesTest.files(f.local.typed());
                assertThrows(IllegalArgumentException.class,()->f.local.prepare(e->fail("cancelled typed recovery must validate before writes")));
                assertEquals(before,V53ReplayFilesTest.files(f.local.typed()));Files.move(aside,path);
            }
            f.typed=f.local.prepare(e->{});f.head=f.typed.retainGeneration();
            try(var cancellation=MembershipLearnerCancellation.resume(f.head,e->{})){assertEquals("CANCELLED",cancellation.result().get("phase"));}
        }
    }
    @Test void receivingCapacityAndHistoricalDataAreNotCancellationCapabilities()throws Exception {
        try(var f=new Fixture("CANCELLED")) {
            try(var cancellation=f.retain(e->{})){cancellation.result();}
            var usage=f.local.source.client.usage();var before=V53ReplayFilesTest.files(f.directory());
            try(var other=f.local.source.client.reserve(MembershipResources.Unit.LEARNER,"occupied",1)) {
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("capacity refusal must not write")));
                assertEquals(before,V53ReplayFilesTest.files(f.directory()));
            }
            assertEquals(usage,f.local.source.client.usage());
            try(var second=f.local.source.client.reserve(MembershipResources.Unit.GENERATION,"second-generation",1);
                    var cancellation=MembershipLearnerCancellation.resume(f.head,e->{})) {
                assertEquals(2,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertEquals("CANCELLED",cancellation.result().get("phase"));cancellation.close();assertThrows(IllegalArgumentException.class,cancellation::result);
            }
            f.typed.close();assertThrows(IllegalArgumentException.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("closed head must not write")));
        }
    }
}
