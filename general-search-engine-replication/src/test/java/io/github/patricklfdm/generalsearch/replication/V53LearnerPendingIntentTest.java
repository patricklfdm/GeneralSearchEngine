package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual local locks, typed image, TCP, retained files and new-side force.
 * Old voting history/certificates are conditional fixtures. Injected IOException
 * is not fresh-process death or native minimum-quorum qualification. */
class V53LearnerPendingIntentTest {
    @TempDir Path temp;
    final class Fixture implements AutoCloseable {
        final V53LearnerCancellationTest.Fixture f;
        final MembershipTransport server;
        final byte[] metadata;
        Fixture()throws Exception {
            var helper=new V53LearnerCancellationTest();helper.temp=temp;f=helper.new Fixture("SEALED");f.server.close();
            metadata=canonical(V53JoiningIntentPullTest.body(f.peer.owner.activationCapsule(),f.local.source.fixture.fixture.source,
                    f.peer.owner.activationIdentity(),f.head.request().identity()),MembershipJoiningIntentMetadata.MAXIMUM);
            var traces=ConcurrentHashMap.<String>newKeySet();
            server=new MembershipTransport(f.peer.owner,f.local.config.bounds(),f.peer.server,(sender,request)->{
                if(request.kind().equals("STATUS_PROBE"))return MembershipDiscovery.answer(f.peer.owner.activationContext(),f.peer.owner.activationIdentity(),sender,request);
                var payload=object(request.value().get("payload"));String trace=(String)request.value().get("trace");
                if(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                        && MembershipJoiningIntentExport.reference(f.peer.owner.activationContext(),sender,(String)payload.get("digest")))traces.add(trace);
                return traces.contains(trace)?V53JoiningIntentPullTest.answer(request,metadata):f.peer.service.handle(sender,request);
            },MembershipTransport.Events.NONE);
        }
        Path directory(){return MembershipLearnerPendingIntent.directory(f.local.summary);}
        MembershipLearnerPendingIntent retain(MembershipBallotAllocator.Cut cut)throws Exception {
            try(var progress=f.progress()) {
                progress.fetch(f.local.base.resolve("progress"));progress.joiningMetadata().fetch();
                return progress.retainPendingIntent(cut);
            }
        }
        @Override public void close()throws Exception{server.close();f.close();}
    }
    @Test void originalSourceAndTypedImageAreForcedBeforeTheNewSideAckAndSurviveReopen()throws Exception {
        try(var fixture=new Fixture()) {
            var f=fixture.f;var events=new ArrayList<String>();var replica=V53ReplayFilesTest.files(f.local.source.request.replicaDirectory());
            var typed=V53ReplayFilesTest.files(f.local.typed());var usage=f.local.source.client.usage();
            MembershipAppliedEndFiles.Endorsement acknowledgement;
            try(var pending=fixture.retain(events::add)) {
                assertArrayEquals(fixture.metadata,pending.originals().bytes());
                assertEquals("SEALED",MembershipLearnerProgressAccess.operation(pending.source().context,f.head.request().identity()).get("phase"));
                assertFalse(Files.exists(fixture.directory().resolve(MembershipLearnerDisposition.PENDING_ACK)));
                acknowledgement=pending.endorse();var statement=pending.originals().record("CHECKPOINT");
                assertEquals(statement.digest(),acknowledgement.acknowledgement().value().get("statement"));
                assertEquals(f.head.request().identity().nodeId().value(),acknowledgement.owned().voter());
                assertTrue(events.indexOf("LEARNER_JOINING_SOURCE_PARENTS_FORCED")<events.indexOf("LEARNER_JOINING_ACK_CREATED"));
                assertTrue(events.indexOf("LEARNER_JOINING_ACK_FORCED")<events.indexOf("LEARNER_JOINING_ACK_PARENT_FORCED"));
                assertTrue(events.indexOf("LEARNER_JOINING_ACK_PARENT_FORCED")<events.indexOf("LEARNER_JOINING_ACK_BEFORE_RETURN"));
                assertArrayEquals(acknowledgement.acknowledgement().bytes(),Files.readAllBytes(fixture.directory().resolve(MembershipLearnerDisposition.PENDING_ACK)));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.JOURNAL));
                assertThrows(IllegalArgumentException.class,f.local.store::requireActive);
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerPendingIntent.resume(f.head,e->fail("duplicate owner must not force")));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resume(f.head,e->fail("pending source is not JOINT")));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerCancellation.resume(f.head,e->fail("pending source is not CANCEL")));
            }
            assertEquals(usage,f.local.source.client.usage());var retained=V53ReplayFilesTest.files(fixture.directory());f.reopen();
            try(var pending=MembershipLearnerPendingIntent.resume(f.head,e->{})) {
                assertArrayEquals(acknowledgement.acknowledgement().bytes(),pending.endorse().acknowledgement().bytes());
                assertEquals(retained,V53ReplayFilesTest.files(fixture.directory()));pending.close();assertThrows(IllegalArgumentException.class,pending::endorse);
            }
            assertEquals(replica,V53ReplayFilesTest.files(f.local.source.request.replicaDirectory()));
            assertEquals(typed,V53ReplayFilesTest.files(f.local.typed()));assertFalse(Files.exists(f.local.config.materialization().directory()));
        }
    }
    @Test void decodedOrIncompleteExchangeAndExpiredSourceCannotStartRetention()throws Exception {
        try(var fixture=new Fixture();var progress=fixture.f.progress()) {
            var f=fixture.f;progress.fetch(f.local.base.resolve("progress"));
            assertThrows(IllegalArgumentException.class,()->progress.retainPendingIntent(e->fail("incomplete exchange must not write")));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerDisposition.install(f.head,null,null,e->fail("bare call must not write"),MembershipLearnerDisposition.Kind.PENDING_INTENT));
            progress.joiningMetadata().fetch();f.progressClock.addAndGet(TimeUnit.SECONDS.toNanos(60));
            assertThrows(IllegalArgumentException.class,()->progress.retainPendingIntent(e->fail("expired exchange must not write")));
            assertFalse(Files.exists(fixture.directory()));f.local.store.requireActive();
        }
    }
    @Test void occupiedJournalRefusesBeforeRetainedDecisionAndReleasesScratch()throws Exception {
        try(var fixture=new Fixture();var occupied=fixture.f.local.source.client.reserve(MembershipResources.Unit.JOURNAL,"other-owner",1)) {
            var usage=fixture.f.local.source.client.usage();assertThrows(IllegalArgumentException.class,()->fixture.retain(e->{}));
            assertEquals(usage,fixture.f.local.source.client.usage());assertFalse(Files.exists(fixture.directory()));fixture.f.local.store.requireActive();
        }
    }
    @ParameterizedTest @ValueSource(strings={"DIRECTORY_FORCED","PLAN_CREATED","PLAN_PREFIX_WRITTEN","PLAN_WRITTEN","PLAN_FORCED",
            "PLAN_PARENT_FORCED","RESEAL_FORCED","PLAN_RENAMED","ACTIVE_PLAN_FORCED","SOURCE_MOVED","SOURCE_MEMBER_FORCED",
            "SOURCE_PARENTS_FORCED","BEFORE_RETURN","ACK_CREATED","ACK_PREFIX_WRITTEN","ACK_WRITTEN","ACK_FORCED","ACK_PARENT_FORCED","ACK_BEFORE_RETURN"})
    void interruptedRetentionAndAckEitherPreserveIncompleteProofOrResealTheOriginal(String cut)throws Exception {
        try(var fixture=new Fixture()) {
            var f=fixture.f;var reached=new AtomicBoolean();String event="LEARNER_JOINING_"+cut;
            var failure=assertThrows(IOException.class,()->{try(var pending=fixture.retain(point->{
                if(point.equals(event) && reached.compareAndSet(false,true))throw new IOException(event);
            })){pending.endorse();}});
            assertEquals(event,failure.getMessage());assertTrue(reached.get());assertThrows(IllegalArgumentException.class,f.local.store::requireActive);
            f.reopen();var files=V53ReplayFilesTest.files(fixture.directory());var usage=f.local.source.client.usage();
            if(Set.of("DIRECTORY_FORCED","PLAN_CREATED","PLAN_PREFIX_WRITTEN").contains(cut)) {
                assertThrows(Exception.class,()->MembershipLearnerPendingIntent.resume(f.head,e->fail("incomplete original must not mutate")));
                assertEquals(files,V53ReplayFilesTest.files(fixture.directory()));assertEquals(usage,f.local.source.client.usage());
            }else try(var pending=MembershipLearnerPendingIntent.resume(f.head,e->{})) {
                var ack=pending.endorse();assertEquals(pending.originals().record("CHECKPOINT").digest(),ack.acknowledgement().value().get("statement"));
                assertFalse(Files.exists(f.local.base.resolve("progress")));assertFalse(Files.exists(fixture.directory().resolve("pending-intent.next.json")));
            }
        }
    }
    @Test void alteredOriginalPlanSourceOrAckRefusesBeforeRecoveryWrites()throws Exception {
        try(var fixture=new Fixture()) {
            try(var pending=fixture.retain(e->{})){pending.endorse();}
            var f=fixture.f;var usage=f.local.source.client.usage();var members=new ArrayList<Path>();
            members.add(fixture.directory().resolve("pending-intent.json"));members.add(fixture.directory().resolve(MembershipLearnerDisposition.PENDING_ACK));
            try(var paths=Files.list(fixture.directory().resolve("source"))){members.addAll(paths.sorted().toList());}
            for(var member:members) {
                byte[] original=Files.readAllBytes(member),damaged=original.clone();damaged[damaged.length/2]^=1;Files.write(member,damaged);
                var before=V53ReplayFilesTest.files(fixture.directory());
                assertThrows(Exception.class,()->MembershipLearnerPendingIntent.resume(f.head,e->fail("changed original must not force")),member.toString());
                assertEquals(before,V53ReplayFilesTest.files(fixture.directory()));assertEquals(usage,f.local.source.client.usage());Files.write(member,original);
            }
            Path extra=fixture.directory().resolve("foreign.gsr");Files.write(extra,new byte[]{1});
            assertThrows(Exception.class,()->MembershipLearnerPendingIntent.resume(f.head,e->fail("foreign inventory must not force")));
            assertEquals(usage,f.local.source.client.usage());
        }
    }
}
