package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.Unit;

/** Original-owner close/reopen and injected I/O failures. No process-death or
 * native-voter qualification is claimed by these conditional-history tests. */
class V53PendingPublishedRecoveryTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53PublishedRecoveryCase="+info.getDisplayName());}
    V53PendingPublishedProgressTest.Fixture fixture(int through)throws Exception {
        var helper=new V53PendingPublishedProgressTest();helper.temp=temp;return helper.new Fixture(through);
    }
    MembershipLearnerIntent retain(V53PendingPublishedProgressTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        try(var progress=f.progress(MembershipTransport.Events.NONE)){progress.fetch(f.scratch());return progress.retainPublishedIntent(cut);}
    }
    Path intent(V53PendingPublishedProgressTest.Fixture f){return MembershipLearnerIntent.directory(f.f.f.local.summary);}
    void reopen(V53PendingPublishedProgressTest.Fixture f)throws Exception {f.pending.close();f.f.f.reopen();}
    MembershipLearnerIntent resume(V53PendingPublishedProgressTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipLearnerIntent.resumePublished(f.f.f.head,cut);
    }
    @ParameterizedTest @ValueSource(ints={6,7})
    void coldPairReforcesExactOriginalsWithoutASecondReceivingSlot(int through)throws Exception {
        try(var f=fixture(through)) {
            try(var live=retain(f,e->{})) {
                assertThrows(IllegalArgumentException.class,()->resume(f,e->fail("live pair must not be reopened")));
            }
            reopen(f);var pool=f.f.f.local.source.client;var usage=pool.usage();
            var pending=V53ReplayFilesTest.files(f.f.directory());var full=V53ReplayFilesTest.files(intent(f));var events=new ArrayList<String>();
            var typed=V53ReplayFilesTest.files(f.f.f.local.typed());var replica=V53ReplayFilesTest.files(f.f.f.local.source.request.replicaDirectory());
            try(var restored=resume(f,events::add)) {
                assertEquals(through==6?"JOINT":"COMPLETED",restored.result().get("phase"));
                assertEquals(1,pool.usage().counts().get(Unit.SOURCE));assertEquals(1,pool.usage().counts().get(Unit.LEARNER));
                assertEquals(1,pool.usage().counts().get(Unit.GENERATION));assertEquals(1,pool.usage().counts().get(Unit.JOURNAL));
                assertTrue(events.indexOf("LEARNER_JOINING_RETAIN_PARENT_REFORCED")>=0);
                assertTrue(events.indexOf("LEARNER_JOINING_RETAIN_PARENT_REFORCED")<events.indexOf("LEARNER_INTENT_ACTIVE_PLAN_FORCED"));
                assertEquals("LEARNER_INTENT_BEFORE_RETURN",events.getLast());
                assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));assertEquals(full,V53ReplayFilesTest.files(intent(f)));
                assertThrows(IllegalArgumentException.class,restored::forced,"linked custody still required");
                assertThrows(IllegalArgumentException.class,()->resume(f,e->fail("duplicate recovery")));
                assertFalse(Files.exists(MembershipLearnerVoterStage.directory(f.f.f.local.summary)));
            }
            assertEquals(usage,pool.usage());assertEquals(typed,V53ReplayFilesTest.files(f.f.f.local.typed()));
            assertEquals(replica,V53ReplayFilesTest.files(f.f.f.local.source.request.replicaDirectory()));
        }
    }
    @ParameterizedTest @ValueSource(strings={"LEARNER_INTENT_PLAN_FORCED","LEARNER_INTENT_SOURCE_MOVED"})
    void originalInterruptedChildIsCompletedAfterBothHistoriesAreValidated(String at)throws Exception {
        try(var f=fixture(6)) {
            var reached=new AtomicBoolean();assertThrows(IOException.class,()->retain(f,e->{if(e.equals(at)){reached.set(true);throw new IOException(at);}}));
            assertTrue(reached.get());reopen(f);var pending=V53ReplayFilesTest.files(f.f.directory());
            var events=new ArrayList<String>();try(var restored=resume(f,events::add)){assertEquals("JOINT",restored.result().get("phase"));}
            assertFalse(Files.exists(f.scratch()));assertFalse(Files.exists(intent(f).resolve(MembershipLearnerIntent.NEXT)));
            assertTrue(Files.exists(intent(f).resolve("source/source.gscp")));assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));
            assertTrue(events.indexOf("LEARNER_JOINING_RETAIN_RESTORED")<events.indexOf("LEARNER_INTENT_ACTIVE_PLAN_FORCED"));
        }
    }
    @Test void eitherOriginalOrCopiedLinkRefusesBeforeAnyRecoveryMutation()throws Exception {
        try(var f=fixture(6)) {
            try(var live=retain(f,e->{})){}reopen(f);var pool=f.f.f.local.source.client;var usage=pool.usage();
            var paths=List.of(f.f.directory().resolve("pending-intent.json"),f.f.directory().resolve(MembershipLearnerDisposition.PENDING_ACK),
                    f.f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE),f.f.directory().resolve("source/source.gscp"),
                    intent(f).resolve(MembershipLearnerIntent.PLAN),intent(f).resolve("source/source.gscp"));
            for(Path path:paths) {
                byte[] original=Files.readAllBytes(path),bad=original.clone();bad[bad.length/2]^=1;Files.write(path,bad);
                var pending=V53ReplayFilesTest.files(f.f.directory());var full=V53ReplayFilesTest.files(intent(f));
                assertThrows(Exception.class,()->resume(f,e->fail("original-first preflight")),path.toString());
                assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));assertEquals(full,V53ReplayFilesTest.files(intent(f)));
                assertEquals(usage,pool.usage());Files.write(path,original);
            }
            Path marker=f.f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE),saved=temp.resolve("saved-marker");
            Files.move(marker,saved);Files.copy(saved,marker);
            var pending=V53ReplayFilesTest.files(f.f.directory());var full=V53ReplayFilesTest.files(intent(f));
            assertThrows(Exception.class,()->resume(f,e->fail("copied inode")));
            assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));assertEquals(full,V53ReplayFilesTest.files(intent(f)));assertEquals(usage,pool.usage());
            Files.delete(marker);Files.move(saved,marker);
            Path plan=intent(f).resolve(MembershipLearnerIntent.PLAN);byte[] original=Files.readAllBytes(plan);
            var value=new TreeMap<>(object(parse(original,MembershipLearnerDisposition.MAXIMUM)));var link=new TreeMap<>(object(value.get("pendingSource")));
            link.put("marker","0".repeat(64));value.put("pendingSource",link);Files.write(plan,canonical(value,MembershipLearnerDisposition.MAXIMUM));
            pending=V53ReplayFilesTest.files(f.f.directory());full=V53ReplayFilesTest.files(intent(f));
            assertThrows(Exception.class,()->resume(f,e->fail("different valid-shaped link")));
            assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));assertEquals(full,V53ReplayFilesTest.files(intent(f)));assertEquals(usage,pool.usage());
            Files.write(plan,original);try(var restored=resume(f,e->{})){assertEquals("JOINT",restored.result().get("phase"));}
        }
    }
    @Test void capacityRefusalOnEitherSidePreservesBothOriginalsAndReleasesPartialReservations()throws Exception {
        try(var f=fixture(6)) {
            try(var live=retain(f,e->{})){}reopen(f);var pool=f.f.f.local.source.client;
            var pending=V53ReplayFilesTest.files(f.f.directory());var full=V53ReplayFilesTest.files(intent(f));
            for(Unit unit:List.of(Unit.SOURCE,Unit.LEARNER,Unit.JOURNAL)) {
                var occupied=new ArrayList<MembershipResources.Lease>();
                try {
                    for(int i=0;i<unit.count;i++)occupied.add(pool.reserve(unit,"occupied-"+i,1));var usage=pool.usage();
                    assertThrows(IllegalArgumentException.class,()->resume(f,e->fail("capacity preflight")));
                    assertEquals(usage,pool.usage());assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));assertEquals(full,V53ReplayFilesTest.files(intent(f)));
                }finally{occupied.forEach(MembershipResources.Lease::close);}
            }
            try(var restored=resume(f,e->{})){assertEquals("JOINT",restored.result().get("phase"));}
        }
    }
    @Test void failureDuringEitherReforceRevokesTheWholePairAndCanReopenTheSameFiles()throws Exception {
        try(var f=fixture(6)) {
            try(var live=retain(f,e->{})){}reopen(f);var pool=f.f.f.local.source.client;var usage=pool.usage();
            var pending=V53ReplayFilesTest.files(f.f.directory());var full=V53ReplayFilesTest.files(intent(f));
            for(String at:List.of("LEARNER_JOINING_RETAIN_ACK_REFORCED","LEARNER_INTENT_SOURCE_PARENTS_FORCED")) {
                var reached=new AtomicBoolean();assertThrows(IOException.class,()->resume(f,e->{if(e.equals(at)){reached.set(true);throw new IOException(at);}}));
                assertTrue(reached.get());assertEquals(usage,pool.usage());
                assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));assertEquals(full,V53ReplayFilesTest.files(intent(f)));
            }
            try(var restored=resume(f,e->{})){assertEquals("JOINT",restored.result().get("phase"));}
        }
    }
}
