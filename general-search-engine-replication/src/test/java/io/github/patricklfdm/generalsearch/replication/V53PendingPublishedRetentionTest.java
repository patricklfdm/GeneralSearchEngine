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

/** Actual linked source force; conditional old-voter history. Pair cold recovery,
 * custody, process death and native voter installation are separate gates. */
class V53PendingPublishedRetentionTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53PublishedRetentionCase="+info.getDisplayName());}
    V53PendingPublishedProgressTest.Fixture fixture(int through)throws Exception {
        var helper=new V53PendingPublishedProgressTest();helper.temp=temp;return helper.new Fixture(through);
    }
    @ParameterizedTest @ValueSource(ints={6,7})
    void publishedHistoryForcesWithExactPendingLinkAndRetainsBothOwners(int through)throws Exception {
        try(var f=fixture(through);var progress=f.progress(MembershipTransport.Events.NONE)) {
            var pool=f.f.f.local.source.client;var original=V53ReplayFilesTest.files(f.f.directory());
            var typed=V53ReplayFilesTest.files(f.f.f.local.typed());var replica=V53ReplayFilesTest.files(f.f.f.local.source.request.replicaDirectory());
            var copy=progress.fetch(f.scratch());var events=new ArrayList<String>();
            try(var intent=progress.retainPublishedIntent(events::add)) {
                assertEquals(through==6?"JOINT":"COMPLETED",intent.result().get("phase"));
                Path directory=MembershipLearnerIntent.directory(f.f.f.local.summary);
                assertFalse(Files.exists(f.scratch()));
                var plan=object(parse(Files.readAllBytes(directory.resolve(MembershipLearnerIntent.PLAN)),MembershipLearnerDisposition.MAXIMUM));
                var link=object(plan.get("pendingSource"));
                assertEquals(f.f.directory().toString(),link.get("directory"));
                assertEquals(MembershipBasisSources.key(f.f.directory()).toString(),link.get("directoryKey"));
                assertEquals(hash(Files.readAllBytes(f.f.directory().resolve("pending-intent.json"))),link.get("plan"));
                assertEquals(hash(Files.readAllBytes(f.f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE))),link.get("marker"));
                assertEquals(hash(Files.readAllBytes(f.f.directory().resolve(MembershipLearnerDisposition.PENDING_ACK))),link.get("ack"));
                for(String name:copy.fileNames())assertArrayEquals(copy.fileBytes(name),Files.readAllBytes(directory.resolve("source").resolve(name)));
                assertTrue(events.contains("LEARNER_INTENT_PLAN_FORCED"));assertTrue(events.contains("LEARNER_INTENT_SOURCE_PARENTS_FORCED"));
                assertEquals("LEARNER_INTENT_BEFORE_RETURN",events.getLast());
                progress.close();assertEquals(1,pool.usage().counts().get(Unit.GENERATION));
                assertEquals(1,pool.usage().counts().get(Unit.SOURCE));assertEquals(1,pool.usage().counts().get(Unit.LEARNER));
                assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));assertEquals(typed,V53ReplayFilesTest.files(f.f.f.local.typed()));
                assertEquals(replica,V53ReplayFilesTest.files(f.f.f.local.source.request.replicaDirectory()));
                assertFalse(Files.exists(f.f.f.local.config.materialization().directory()));
                intent.forced().check();
                var files=V53ReplayFilesTest.files(directory);
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.f.f.head,e->fail("unlinked resume")));
                assertEquals(files,V53ReplayFilesTest.files(directory));
                f.pending.close();assertThrows(IllegalArgumentException.class,intent::result);
                assertEquals(files,V53ReplayFilesTest.files(directory));assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));
            }
            assertEquals(0,pool.usage().counts().getOrDefault(Unit.SOURCE,0));assertEquals(0,pool.usage().counts().getOrDefault(Unit.LEARNER,0));
        }
    }
    @ParameterizedTest @ValueSource(strings={"LEARNER_INTENT_PLAN_FORCED","LEARNER_INTENT_SOURCE_MOVED","LEARNER_INTENT_BEFORE_RETURN"})
    void interruptedLinkedForcePreservesBothOriginalsAndRejectsUnlinkedRecovery(String cut)throws Exception {
        try(var f=fixture(6);var progress=f.progress(MembershipTransport.Events.NONE)) {
            var original=V53ReplayFilesTest.files(f.f.directory());progress.fetch(f.scratch());var reached=new AtomicBoolean();
            var failure=assertThrows(IOException.class,()->progress.retainPublishedIntent(event->{if(event.equals(cut)){reached.set(true);throw new IOException("injected "+cut);}}));
            assertTrue(reached.get());assertEquals("injected "+cut,failure.getMessage());progress.close();f.retained.check();
            Path intent=MembershipLearnerIntent.directory(f.f.f.local.summary);
            Path source=Files.exists(f.scratch())?f.scratch():intent.resolve("source");
            assertTrue(Files.exists(source.resolve("source.gscp")));var pending=V53ReplayFilesTest.files(f.f.directory());
            var files=V53ReplayFilesTest.files(intent);var sourceFiles=V53ReplayFilesTest.files(source);
            assertEquals(original,pending);
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.f.f.head,e->fail("unlinked resume")));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerPendingIntent.resume(f.f.f.head,e->fail("unlinked pending resume")));
            assertThrows(IllegalArgumentException.class,()->f.progress(MembershipTransport.Events.NONE));
            assertEquals(files,V53ReplayFilesTest.files(intent));assertEquals(sourceFiles,V53ReplayFilesTest.files(source));
            assertEquals(pending,V53ReplayFilesTest.files(f.f.directory()));
        }
    }
    @Test void pendingMutationAtForceBoundaryRevokesChildWithoutDeletingEvidence()throws Exception {
        try(var f=fixture(6);var progress=f.progress(MembershipTransport.Events.NONE)) {
            progress.fetch(f.scratch());Path marker=f.f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE);
            byte[] original=Files.readAllBytes(marker);var reached=new AtomicBoolean();
            assertThrows(Exception.class,()->progress.retainPublishedIntent(event->{
                if(event.equals("LEARNER_INTENT_PLAN_FORCED")) {reached.set(true);byte[] bad=original.clone();bad[bad.length/2]^=1;Files.write(marker,bad);}
            }));
            assertTrue(reached.get());progress.close();Path directory=MembershipLearnerIntent.directory(f.f.f.local.summary);
            assertTrue(Files.exists(directory.resolve(MembershipLearnerIntent.NEXT)));
            assertTrue(Files.exists(f.scratch().resolve("source.gscp")));
            assertFalse(Files.exists(MembershipLearnerVoterStage.directory(f.f.f.local.summary)));
            Files.write(marker,original);f.retained.check();
        }
    }
    @Test void incompleteOrExpiredAcquisitionCannotWriteLinkedPlan()throws Exception {
        try(var f=fixture(6);var progress=f.progress(MembershipTransport.Events.NONE)) {
            var original=V53ReplayFilesTest.files(f.f.directory());
            assertThrows(IllegalArgumentException.class,()->progress.retainPublishedIntent(e->fail("incomplete acquisition")));
            progress.fetch(f.scratch());progress.close();
            assertThrows(IllegalArgumentException.class,()->progress.retainPublishedIntent(e->fail("closed acquisition")));
            assertFalse(Files.exists(MembershipLearnerIntent.directory(f.f.f.local.summary)));
            assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));
        }
    }
}
