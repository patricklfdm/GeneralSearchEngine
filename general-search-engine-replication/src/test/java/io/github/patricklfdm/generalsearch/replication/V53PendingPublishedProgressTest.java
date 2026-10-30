package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.Unit;

/** Real typed/pending owner and TCP history; old quorum history is conditional.
 * This does not install a joined voter or qualify autonomous publication. */
class V53PendingPublishedProgressTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.MINUTES.toNanos(2);
    @BeforeEach void announce(TestInfo info){System.out.println("v53PendingPublishedCase="+info.getDisplayName());}
    final class Fixture implements AutoCloseable {
        final V53LearnerPendingIntentTest.Fixture f;
        final MembershipLearnerPendingIntent pending;
        final MembershipLearnerDisposition.RetainedSource retained;
        final V53LearnerProgressNetworkTest.Peer peer;
        final MembershipTransport server;
        Fixture(int through)throws Exception {
            var helper=new V53LearnerPendingIntentTest();helper.temp=temp;f=helper.new Fixture();pending=f.retain(e->{});
            pending.endorse();retained=pending.retainSource();f.server.close();
            var network=new V53LearnerProgressNetworkTest();network.temp=temp;
            peer=network.new Peer(V53CapsuleFixture.fromHistory(f.f.local.source.fixture.fixture.source,through),true);
            server=new MembershipTransport(peer.owner,f.f.local.config.bounds(),peer.server,(sender,request)->
                    request.kind().equals("STATUS_PROBE")?MembershipDiscovery.answer(peer.owner.activationContext(),peer.owner.activationIdentity(),sender,request):
                            peer.service.handle(sender,request),MembershipTransport.Events.NONE);
        }
        MembershipLearnerProgress progress(MembershipTransport.Events events)throws Exception {
            return new MembershipLearnerProgress(retained,peer.owner.activationIdentity(),f.f.local.config.bounds(),events,System::nanoTime,System.nanoTime(),BUDGET);
        }
        Path scratch(){return f.f.local.base.resolve("published");}
        @Override public void close()throws Exception{server.close();peer.close();pending.close();f.close();}
    }
    @ParameterizedTest @ValueSource(ints={6,7})
    void exactOriginalIntentCanBeReadFromPublishedJointOrCompletedHistory(int through)throws Exception {
        try(var f=new Fixture(through);var progress=f.progress(MembershipTransport.Events.NONE)) {
            var pool=f.f.f.local.source.client;var usage=pool.usage();var original=V53ReplayFilesTest.files(f.f.directory());
            var typed=V53ReplayFilesTest.files(f.f.f.local.typed());var replica=V53ReplayFilesTest.files(f.f.f.local.source.request.replicaDirectory());
            assertThrows(IllegalArgumentException.class,f.f.f::progress);
            var copy=progress.fetch(f.scratch());assertSame(copy,progress.source());
            assertEquals(through==6?"JOINT":"COMPLETED",MembershipLearnerProgressAccess.operation(copy.capsule.context,f.f.f.head.request().identity()).get("phase"));
            assertEquals(1,pool.usage().counts().get(Unit.GENERATION));assertEquals(1,pool.usage().counts().get(Unit.SOURCE));assertEquals(1,pool.usage().counts().get(Unit.LEARNER));
            assertThrows(IllegalArgumentException.class,()->progress.retainIntent(e->fail("unlinked retention must not write")));
            assertThrows(IllegalArgumentException.class,()->progress.retainCancellation(e->fail("pending cannot cancel")));
            assertThrows(IllegalArgumentException.class,()->progress.retainPendingIntent(e->fail("pending cannot be recreated")));
            assertThrows(IllegalArgumentException.class,progress::joiningMetadata);
            progress.close();assertEquals(usage,pool.usage());assertFalse(Files.exists(f.scratch()));
            assertFalse(Files.exists(MembershipLearnerIntent.directory(f.f.f.local.summary)));
            assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));assertEquals(typed,V53ReplayFilesTest.files(f.f.f.local.typed()));
            assertEquals(replica,V53ReplayFilesTest.files(f.f.f.local.source.request.replicaDirectory()));assertFalse(Files.exists(f.f.f.local.config.materialization().directory()));
        }
    }
    @Test void stillSealedHistoryCannotSatisfyPublishedAcquisition()throws Exception {
        try(var f=new Fixture(5);var progress=f.progress(MembershipTransport.Events.NONE)) {
            var original=V53ReplayFilesTest.files(f.f.directory());var usage=f.f.f.local.source.client.usage();
            assertThrows(IllegalArgumentException.class,()->progress.fetch(f.scratch()));
            assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));assertEquals(usage,f.f.f.local.source.client.usage());
            assertFalse(Files.exists(f.scratch()));f.retained.check();
        }
    }
    @Test void parentCloseAtTheActualReplyRevokesAcquisitionAndPreservesEvidence()throws Exception {
        try(var f=new Fixture(6)) {
            var original=V53ReplayFilesTest.files(f.f.directory());var reached=new AtomicBoolean();
            try(var progress=f.progress((event,request,response)->{
                if(event.equals("AFTER_RESPONSE_READ")&&reached.compareAndSet(false,true))f.pending.close();
            })) {
                assertThrows(Exception.class,()->progress.fetch(f.scratch()));assertTrue(reached.get());
                assertThrows(IllegalArgumentException.class,progress::source);assertFalse(Files.exists(f.scratch()));
            }
            assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));assertThrows(IllegalArgumentException.class,f.retained::check);
        }
    }
    @Test void originalDeadlineAndChangedMarkerRefuseBeforeAnyContact()throws Exception {
        try(var f=new Fixture(6)) {
            var before=V53ReplayFilesTest.files(f.f.directory());var reached=new AtomicBoolean();
            assertThrows(IllegalArgumentException.class,()->new MembershipLearnerProgress(f.retained,f.peer.owner.activationIdentity(),f.f.f.local.config.bounds(),
                    (event,request,response)->reached.set(true),()->10L,0,10));assertFalse(reached.get());
            assertEquals(before,V53ReplayFilesTest.files(f.f.directory()));
            for(Path scratch:List.of(f.f.directory(),f.f.directory().resolve("source"),f.f.directory().resolveSibling(".").normalize())) {
                try(var progress=f.progress((e,q,a)->reached.set(true))) {
                    var rejected=assertThrows(ReplicationException.class,()->progress.fetch(scratch));
                    assertEquals(ReplicationException.Reason.STORAGE_FAILURE,rejected.reason());assertFalse(reached.get());
                    assertEquals(before,V53ReplayFilesTest.files(f.f.directory()));
                }
            }
            Path marker=f.f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE);byte[] bytes=Files.readAllBytes(marker),bad=bytes.clone();bad[bad.length/2]^=1;
            Files.write(marker,bad);var changed=V53ReplayFilesTest.files(f.f.directory());
            assertThrows(Exception.class,()->f.progress((e,q,a)->reached.set(true)));assertFalse(reached.get());
            assertEquals(changed,V53ReplayFilesTest.files(f.f.directory()));Files.write(marker,bytes);
        }
    }
}
