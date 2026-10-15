package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.NOT_APPLICABLE;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Started public handles only; no reflection or internal read/capture port. */
class V52PublicReadTest {
    @TempDir Path root;
    static final ReplicaReadOptions STRONG=new ReplicaReadOptions(ReplicaReadPolicy.LEADER_STRONG,Optional.empty(),0);
    static final ReplicaReadOptions STALE=new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,Optional.empty(),0);
    V51PublicRuntimeTest fixture() {var fixture=new V51PublicRuntimeTest();fixture.root=root;return fixture;}
    static ReplicaReadOptions minimum(ReplicaReadToken token,int wait) {return new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.of(token),wait);}
    static ReplicaReadToken index(ReplicaReadToken token,long index) {return new ReplicaReadToken(1,token.groupId(),token.historyId(),token.manifestDigest(),index);}
    static Throwable cause(CompletableFuture<?> future) {return assertThrows(CompletionException.class,future::join).getCause();}
    static void readReason(ReplicaReadException.Reason reason,CompletableFuture<?> result) {
        assertEquals(reason,assertInstanceOf(ReplicaReadException.class,cause(result)).reason());
    }
    static void await(CountDownLatch latch) {
        try {assertTrue(latch.await(5,TimeUnit.SECONDS));}catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError(error);}
    }
    static void idle(AutomaticReplicatedSearchEngine<?,?> engine) {
        long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
        while(engine.leadershipStatus().pendingOperations()!=0&&System.nanoTime()<until)
            java.util.concurrent.locks.LockSupport.parkNanos(100_000);
        assertEquals(0,engine.leadershipStatus().pendingOperations());
    }

    @Test void stoppedAndClosedAdmissionRejectsPromptlyWithoutInvokingCallbackOrCreatingFiles() throws Exception {
        var config=configs(root).getFirst();var engine=AutomaticReplicatedSearchEngines.builder(rich(),config).build();
        var token=new ReplicaReadToken(1,config.groupId(),UUID.randomUUID(),"ab".repeat(32),0);
        try {
            assertThrows(NullPointerException.class,()->engine.read(null,v->null));assertThrows(NullPointerException.class,()->engine.read(STALE,null));
            for(var options:List.of(STRONG,STALE,minimum(token,0)))
                rejected(NOT_READY,NOT_APPLICABLE,()->engine.read(options,v->fail("stopped callback")).join());
            try(var paths=Files.list(root)){assertEquals(0,paths.count());}
        } finally {engine.close();}
        rejected(CLOSED,NOT_APPLICABLE,()->engine.read(STALE,v->fail("closed callback")).join());
    }

    @Test void strongReadDelegatesAllSevenQueriesAtOneNoOpCutAndScopesTheView() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();leader.addAll(List.of(new Doc(1,"shared alpha"),new Doc(2,"shared beta"))).join();
            long before=leader.leadershipStatus().provenIndex();var escaped=new AtomicReference<ReplicaReadView<Integer,Doc>>();
            var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(10).build();
            var result=leader.read(STRONG,view->{
                escaped.set(view);assertEquals(new Doc(1,"shared alpha"),view.get(1));
                assertEquals(2,view.search(Query.matchAll()).size());
                assertEquals(2,view.searchTopK(RankedSearchRequest.of(TextScoringQuery.of(TEXT,"shared"),10)).size());
                assertEquals(2,view.search(request).hits().size());
                assertEquals(2,view.search(HighlightedSearchRequest.builder(request).field(TEXT).build()).hits().size());
                assertTrue(view.explain(request,1).isPresent());
                assertSame(TEXT,leader.textField("value"));assertNotNull(leader.leadershipStatus());return view.currentSequence();
            }).get(10,TimeUnit.SECONDS);
            assertEquals(before+1,result.progress().index());assertEquals(1,result.value());assertEquals(1,result.applicationSequence());
            assertEquals(ReplicaReadPolicy.LEADER_STRONG,result.policy());
            assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,assertThrows(ReplicaReadException.class,escaped.get()::currentSequence).reason());
            assertEquals(2,leader.read(STALE,v->v.search(Query.matchAll()).size()).get(5,TimeUnit.SECONDS).value());
            assertEquals(before+1,leader.leadershipStatus().provenIndex(),"local policy cannot append another barrier");
        }
    }

    @Test void confirmedWriteTokenCanBeUsedAfterFollowerPublicationWithoutAnEpochBinding() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();leader.add(new Doc(1,"confirmed")).join();
            var issued=leader.read(STRONG,v->v.get(1)).get(10,TimeUnit.SECONDS);
            // This case tests the carried token against a published follower. A still-lagging
            // voter can legitimately enter snapshot recovery and reject its uncaptured waiter;
            // deterministic recovery/state-transition cases check that rejection separately.
            AutomaticReplicatedSearchEngine<Integer,Doc> follower=null;
            long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(15);
            while(follower==null&&System.nanoTime()<until) {
                follower=group.engines.stream().filter(e->e!=leader&&
                        e.leadershipStatus().state()==AutomaticReplicationState.FOLLOWER&&
                        e.leadershipStatus().appliedIndex()>=issued.progress().index()).findFirst().orElse(null);
                if(follower==null)java.util.concurrent.locks.LockSupport.parkNanos(1_000_000);
            }
            assertNotNull(follower,"no follower published the confirmed prefix");var publishedFollower=follower;
            var caughtUp=follower.read(minimum(issued.progress(),60000),v->v.get(1)).get(15,TimeUnit.SECONDS);
            assertEquals(issued.value(),caughtUp.value());assertTrue(caughtUp.progress().index()>=issued.progress().index());
            assertEquals(issued.applicationSequence(),caughtUp.applicationSequence());assertEquals(ReplicaReadPolicy.AT_LEAST_INDEX,caughtUp.policy());
            rejected(NOT_LEADER,NOT_APPLICABLE,()->publishedFollower.read(STRONG,v->fail("strong follower callback")).join());
            assertEquals(issued.value(),follower.read(STALE,v->v.get(1)).get(5,TimeUnit.SECONDS).value());
        }
    }

    @Test void waitersLeaveWriterCapacityAndIdentityRejectionPrecedesCapacity() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();var token=leader.read(STRONG,v->null).get(10,TimeUnit.SECONDS).progress();idle(leader);
            var waits=new ArrayList<CompletableFuture<?>>();
            try {
                for(int i=0;i<BOUNDS.maxPendingClientOperations()-1;i++)
                    waits.add(leader.read(minimum(index(token,Long.MAX_VALUE),60000),v->fail("impossible lower bound")));
                assertEquals(BOUNDS.maxPendingClientOperations()-1,leader.leadershipStatus().pendingOperations());
                var foreign=new ReplicaReadToken(1,token.groupId(),UUID.randomUUID(),token.manifestDigest(),0);
                readReason(ReplicaReadException.Reason.INCOMPATIBLE_HISTORY,leader.read(minimum(foreign,0),v->0));
                rejected(CAPACITY_EXCEEDED,NOT_APPLICABLE,()->leader.read(STALE,v->0).join());
                leader.add(new Doc(2,"writer-slot")).get(10,TimeUnit.SECONDS);
                assertTrue(waits.stream().noneMatch(CompletableFuture::isDone));
            } finally {waits.forEach(future->future.cancel(false));}
            idle(leader);assertEquals("writer-slot",leader.get(2).value());
        }
    }

    @Test void queuedWritesDoNotOvertakeFreshStrongCapture() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();
            var reads=new ArrayList<CompletableFuture<ReplicaReadResult<Long>>>();
            var writes=new ArrayList<CompletableFuture<Void>>();
            for(int i=0;i<3;i++) {
                reads.add(leader.read(STRONG,ReplicaReadView::currentSequence));
                writes.add(leader.add(new Doc(i,"ordered-"+i)));
            }
            for(int i=0;i<reads.size();i++) {
                var result=reads.get(i).get(10,TimeUnit.SECONDS);
                assertEquals(i,result.applicationSequence());assertEquals(i,result.value());
                writes.get(i).get(10,TimeUnit.SECONDS);
            }
        }
    }

    @Test void progressDeadlineAndCancellationAreServicedWhileAnotherCallbackIsActive() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();var token=leader.read(STALE,v->null).get(5,TimeUnit.SECONDS).progress();
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            var active=leader.read(STALE,v->{entered.countDown();await(release);return v.currentSequence();});
            try {
                await(entered);
                var waiting=leader.read(minimum(index(token,Long.MAX_VALUE),25),v->fail("expired callback"));
                var failed=assertThrows(ExecutionException.class,()->waiting.get(5,TimeUnit.SECONDS));
                assertEquals(DEADLINE_EXCEEDED,assertInstanceOf(AutomaticReplicationException.class,failed.getCause()).reason());
                var cancelled=leader.read(minimum(index(token,Long.MAX_VALUE),60000),v->fail("cancelled callback"));
                assertTrue(cancelled.cancel(true));assertFalse(active.isDone());
            } finally {release.countDown();}
            assertEquals(0,active.get(5,TimeUnit.SECONDS).value());idle(leader);
            readReason(ReplicaReadException.Reason.PROGRESS_NOT_REACHED,leader.read(minimum(index(token,Long.MAX_VALUE),0),v->fail("zero wait")));
        }
    }

    @Test void sameHandleReentryRejectsAndOriginalQueryAndCallbackErrorsSurvive() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();leader.add(new Doc(1,"query")).join();
            leader.read(STALE,v->{
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.get(1));
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.read(STALE,w->0).join());
                rejected(REENTRANT_CALL,AutomaticReplicationException.Outcome.NOT_SUBMITTED,()->leader.add(new Doc(2,"nested")).join());
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.checkpoint().join());
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.start().join());
                rejected(REENTRANT_CALL,NOT_APPLICABLE,leader::close);return null;
            }).get(5,TimeUnit.SECONDS);
            var error=new IllegalArgumentException("original predicate");
            assertSame(error,cause(leader.read(STALE,v->v.search(d->{throw error;}))));
            var fatal=new AssertionError("callback error");var escaped=new AtomicReference<ReplicaReadView<Integer,Doc>>();
            assertSame(fatal,cause(leader.read(STALE,v->{escaped.set(v);throw fatal;})));
            assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,assertThrows(ReplicaReadException.class,escaped.get()::currentSequence).reason());
            assertNull(leader.read(STALE,v->v.get(999)).get(5,TimeUnit.SECONDS).value());
        }
    }

    @Test void aSinglePendingSlotRemainsAvailableForLegacyMaintenance() throws Exception {
        var bounds=ReplicaLeaderTestSupport.bounds(1200,1);
        var configs=configs(root).stream().map(c->new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),
                c.members(),c.replicaDirectory(),c.materialization(),bounds,c.leadershipPolicy())).toList();
        var app=rich();var request=new AutomaticReplicationBootstrapRequest<Integer,Doc>(ReplicationBootstrapSource.EMPTY,null,
                configs,root.resolve("operation"),1L<<30,1L<<30);
        AutomaticReplicationStorageOperations.applyBootstrap(app,request,AutomaticReplicationStorageOperations.planBootstrap(app,request));
        try(var handle=AutomaticReplicatedSearchEngines.builder(app,configs.getFirst()).build()) {
            handle.start().get(5,TimeUnit.SECONDS);
            rejected(CAPACITY_EXCEEDED,NOT_APPLICABLE,()->handle.read(STALE,v->fail("P=1 explicit callback")).join());
            handle.checkpoint().get(5,TimeUnit.SECONDS);assertEquals(0,handle.durabilityMetrics().checkpointSequence());
        }
    }

    @Test void cancelledPublicCallbackKeepsItsViewUntilCooperativeCloseCanFinish() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var returned=new CountDownLatch(1);
            var escaped=new AtomicReference<ReplicaReadView<Integer,Doc>>();
            var result=leader.read(STALE,v->{
                escaped.set(v);entered.countDown();await(release);assertEquals(0,v.currentSequence());returned.countDown();return null;
            });
            try {
                await(entered);assertTrue(result.cancel(true));
                assertEquals(DEADLINE_EXCEEDED,assertThrows(AutomaticReplicationException.class,leader::close).reason());
                assertTrue(leader.leadershipStatus().pendingOperations()>0);
            } finally {release.countDown();}
            await(returned);leader.close();assertTrue(result.isCancelled());
            assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,
                    assertThrows(ReplicaReadException.class,escaped.get()::currentSequence).reason());
        }
    }
}
