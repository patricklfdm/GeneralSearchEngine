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
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import io.github.patricklfdm.generalsearch.replication.MembershipResources.Lease;

/** Actual typed owner, original files and accounting. The old history is a
 * conditional fixture; this is not published JOINT acquisition or process death. */
class V53LearnerPendingRetentionTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53PendingRetentionCase="+info.getDisplayName());}
    V53LearnerPendingIntentTest.Fixture fixture()throws Exception {
        var helper=new V53LearnerPendingIntentTest();helper.temp=temp;return helper.new Fixture();
    }
    @Test void originalForcedMarkerMovesOnlyTheReceivingCategoryAndSurvivesColdReopen()throws Exception {
        try(var f=fixture()) {
            var pool=f.f.local.source.client;var baseline=pool.usage();var events=new ArrayList<String>();
            var typed=V53ReplayFilesTest.files(f.f.local.typed());var replica=V53ReplayFilesTest.files(f.f.local.source.request.replicaDirectory());
            MembershipLearnerDisposition.RetainedSource retained;
            try(var pending=f.retain(event->{
                events.add(event);
                if(event.equals("LEARNER_JOINING_RETAIN_BEFORE_TRANSFER")) {
                    assertEquals(1,pool.usage().counts().get(Unit.LEARNER));assertEquals(1,pool.usage().counts().get(Unit.SOURCE));
                }
            })) {
                pending.endorse();var before=pool.usage();retained=pending.retainSource();retained.check();
                assertEquals(before.metadata(),pool.usage().metadata());assertEquals(before.staging(),pool.usage().staging());assertEquals(before.leases(),pool.usage().leases());
                assertEquals(1,pool.usage().counts().get(Unit.SOURCE));assertEquals(1,pool.usage().counts().get(Unit.GENERATION));
                assertFalse(pool.usage().counts().containsKey(Unit.LEARNER));
                assertTrue(events.indexOf("LEARNER_JOINING_RETAIN_PARENT_FORCED")<events.indexOf("LEARNER_JOINING_RETAIN_TRANSFERRED"));
                assertEquals(pending.source().context.cut,retained.source().context.cut);
                assertThrows(IllegalArgumentException.class,f.f.local.store::requireActive);
                // The old typed generation and retained source leave real room
                // for both the next receive and the existing voter-stage slot.
                try(var receiving=pool.reserve(Unit.LEARNER,"next-progress",1);var staging=pool.reserve(Unit.GENERATION,"voter-stage",1)) {
                    assertEquals(2,pool.usage().counts().get(Unit.GENERATION));pending.retainSource().check();
                }
            }
            assertThrows(IllegalArgumentException.class,retained::check);assertEquals(baseline,pool.usage());
            var originals=V53ReplayFilesTest.files(f.directory());f.f.reopen();
            try(var pending=MembershipLearnerPendingIntent.resume(f.f.head,e->{})) {
                assertEquals(1,pool.usage().counts().get(Unit.LEARNER));pending.retainSource().check();
                assertFalse(pool.usage().counts().containsKey(Unit.LEARNER));assertEquals(originals,V53ReplayFilesTest.files(f.directory()));
            }
            assertEquals(typed,V53ReplayFilesTest.files(f.f.local.typed()));assertEquals(replica,V53ReplayFilesTest.files(f.f.local.source.request.replicaDirectory()));
            assertFalse(Files.exists(f.f.local.config.materialization().directory()));
        }
    }
    @Test void missingAckAndFullSourceCapacityRefuseBeforeMarkerAndLeaveOwnerUsable()throws Exception {
        try(var f=fixture();var pending=f.retain(e->{})) {
            var before=V53ReplayFilesTest.files(f.directory());var pool=f.f.local.source.client;
            assertThrows(IllegalArgumentException.class,pending::retainSource);assertEquals(before,V53ReplayFilesTest.files(f.directory()));
            pending.endorse();before=V53ReplayFilesTest.files(f.directory());var occupied=new ArrayList<Lease>();
            try {
                for(int i=0;i<6;i++)occupied.add(pool.reserve(Unit.SOURCE,"occupied-"+i,1));var usage=pool.usage();
                assertThrows(IllegalArgumentException.class,pending::retainSource);assertEquals(usage,pool.usage());
                assertEquals(before,V53ReplayFilesTest.files(f.directory()));pending.source();
            }finally{occupied.forEach(Lease::close);}
            pending.retainSource().check();
        }
    }
    @ParameterizedTest @ValueSource(strings={"CREATED","PREFIX_WRITTEN","WRITTEN","FORCED","PARENT_FORCED","BEFORE_TRANSFER","TRANSFERRED"})
    void interruptedForceOrTransferResumesOnlyItsOriginalMarker(String at)throws Exception {
        try(var f=fixture()) {
            var hit=new AtomicBoolean();String event="LEARNER_JOINING_RETAIN_"+at;
            assertThrows(IOException.class,()->{try(var pending=f.retain(e->{if(e.equals(event)&&hit.compareAndSet(false,true))throw new IOException(event);})) {
                pending.endorse();pending.retainSource();
            }});assertTrue(hit.get());var marker=f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE);
            Object inode=MembershipBasisSources.key(marker);f.f.reopen();
            try(var pending=MembershipLearnerPendingIntent.resume(f.f.head,e->{})) {
                pending.retainSource().check();assertEquals(inode,MembershipBasisSources.key(marker));
                assertEquals(1,f.f.local.source.client.usage().counts().get(Unit.SOURCE));
                assertFalse(f.f.local.source.client.usage().counts().containsKey(Unit.LEARNER));
            }
        }
    }
    @Test void alteredOrCopiedMarkerAndOriginalSourceRefuseBeforeRecoveryMutation()throws Exception {
        try(var f=fixture()) {
            try(var pending=f.retain(e->{})){pending.endorse();pending.retainSource();}
            var pool=f.f.local.source.client;var usage=pool.usage();Path marker=f.directory().resolve(MembershipLearnerDisposition.PENDING_SOURCE);
            for(Path path:List.of(marker,f.directory().resolve(MembershipLearnerDisposition.PENDING_ACK),f.directory().resolve("source/source.gscp"))) {
                byte[] original=Files.readAllBytes(path),bad=original.clone();bad[bad.length/2]^=1;Files.write(path,bad);
                var before=V53ReplayFilesTest.files(f.directory());
                assertThrows(Exception.class,()->MembershipLearnerPendingIntent.resume(f.f.head,e->fail("damaged original must not force")));
                assertEquals(before,V53ReplayFilesTest.files(f.directory()));assertEquals(usage,pool.usage());Files.write(path,original);
            }
            Path saved=marker.resolveSibling("marker.saved");Files.move(marker,saved);Files.copy(saved,marker);Files.move(saved,temp.resolve("original-marker"));
            var before=V53ReplayFilesTest.files(f.directory());
            assertThrows(Exception.class,()->MembershipLearnerPendingIntent.resume(f.f.head,e->fail("copied marker must not force")));
            assertEquals(before,V53ReplayFilesTest.files(f.directory()));assertEquals(usage,pool.usage());
        }
    }
}
