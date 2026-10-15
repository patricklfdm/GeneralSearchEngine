package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.*;
import static io.github.patricklfdm.generalsearch.replication.V52PublicReadTest.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.NOT_APPLICABLE;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Public, real TCP lifecycle checks. Process-death schedules have a separate retained harness. */
class V52PublicReadLifecycleTest {
    @TempDir Path root;
    V51PublicRuntimeTest fixture(){var f=new V51PublicRuntimeTest();f.root=root;return f;}

    @Test void threeBehindReadsLeaveTheFourthSlotForTheirSatisfyingWrite() throws Exception {
        var bounds=ReplicaLeaderTestSupport.bounds(1200,4);var configs=configs(root).stream().map(c->
                new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),c.members(),
                        c.replicaDirectory(),c.materialization(),bounds,c.leadershipPolicy())).toList();
        var app=rich();var request=new AutomaticReplicationBootstrapRequest<Integer,Doc>(ReplicationBootstrapSource.EMPTY,null,
                configs,root.resolve("operation"),1L<<30,1L<<30);
        AutomaticReplicationStorageOperations.applyBootstrap(app,request,AutomaticReplicationStorageOperations.planBootstrap(app,request));
        var engines=new ArrayList<AutomaticReplicatedSearchEngine<Integer,Doc>>();var waits=new ArrayList<CompletableFuture<ReplicaReadResult<Doc>>>();
        try {
            for(var config:configs){var e=AutomaticReplicatedSearchEngines.builder(app,config).build();engines.add(e);e.start().get(10,TimeUnit.SECONDS);}
            AutomaticReplicatedSearchEngine<Integer,Doc> active=null;long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
            while(active==null&&System.nanoTime()<until){active=engines.stream().filter(e->e.leadershipStatus().state()==AutomaticReplicationState.LEADER_READY).findFirst().orElse(null);Thread.sleep(10);}
            assertNotNull(active);var leader=active;var token=leader.read(STALE,v->null).get(5,TimeUnit.SECONDS).progress();idle(leader);
            for(int i=0;i<3;i++)waits.add(leader.read(minimum(index(token,token.index()+1),60000),v->v.get(7)));
            assertEquals(3,leader.leadershipStatus().pendingOperations());
            rejected(CAPACITY_EXCEEDED,NOT_APPLICABLE,()->leader.read(STALE,v->fail("fourth explicit read")).join());
            leader.add(new Doc(7,"writer-satisfies-all")).get(10,TimeUnit.SECONDS);
            for(var read:waits){var result=read.get(10,TimeUnit.SECONDS);assertEquals(new Doc(7,"writer-satisfies-all"),result.value());assertTrue(result.progress().index()>token.index());}
            idle(leader);
        } finally {waits.forEach(f->f.cancel(false));for(var e:engines)e.close();}
    }

    @Test void aCapturedViewSurvivesQueuedMutationAndIndexLifecycleButNeverEscapes() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();leader.addAll(List.of(new Doc(1,"shared alpha"),new Doc(2,"shared beta"))).join();
            var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(10).build();
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var escaped=new AtomicReference<ReplicaReadView<Integer,Doc>>();
            var result=leader.read(STALE,v->{
                escaped.set(v);long sequence=v.currentSequence();var before=v.search(request).hits();entered.countDown();await(release);
                assertEquals(sequence,v.currentSequence());assertEquals(before,v.search(request).hits());assertEquals("shared alpha",v.get(1).value());return v;
            });
            CompletableFuture<Void> mutation,create,drop;
            try {
                await(entered);assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,assertThrows(ReplicaReadException.class,()->escaped.get().get(1)).reason());
                mutation=leader.update(new Doc(1,"changed"));create=leader.createIndex(IndexDefinition.equality(ID));drop=leader.dropIndex("id");
                assertFalse(mutation.isDone());assertFalse(create.isDone());assertFalse(drop.isDone());
            } finally {release.countDown();}
            var response=result.get(10,TimeUnit.SECONDS);CompletableFuture.allOf(mutation,create,drop).get(15,TimeUnit.SECONDS);
            assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,assertThrows(ReplicaReadException.class,response.value()::currentSequence).reason());
            var later=leader.read(STALE,v->v.get(1)).get(5,TimeUnit.SECONDS);assertEquals("changed",later.value().value());
            assertEquals(response.applicationSequence()+3,later.applicationSequence());assertTrue(later.progress().index()>response.progress().index());
        }
    }

    @Test void aMinimumIsHistoryCoverageNotAReceiptForTheOldDocumentContents() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();leader.addAll(List.of(new Doc(1,"before"),new Doc(2,"removed"))).join();
            var old=leader.read(STRONG,v->v.get(1)).get(10,TimeUnit.SECONDS);
            leader.update(new Doc(1,"after")).join();leader.remove(2).join();
            var later=leader.read(minimum(old.progress(),0),v->{assertNull(v.get(2));return v.get(1);}).get(5,TimeUnit.SECONDS);
            assertEquals(new Doc(1,"after"),later.value());assertTrue(later.progress().index()>old.progress().index());
            assertEquals(old.applicationSequence()+2,later.applicationSequence());
        }
    }

    @Test void explicitCallbackCannotInvokeLegacyPagingBackupOrMaintenance() throws Exception {
        try(var group=fixture().new Group(rich(),null,true)) {
            var leader=group.leader();var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(1).build();
            leader.read(STALE,v->{
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.search(SearchPageRequest.builder(request).build()));
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.backup(null).join());
                assertNotNull(leader.durabilityMetrics()); // cached diagnostics are intentionally pure
                assertSame(ID,leader.field("id"));assertSame(TEXT,leader.textField("value"));assertNotNull(leader.leadershipStatus());return null;
            }).get(5,TimeUnit.SECONDS);
        }
    }
}
