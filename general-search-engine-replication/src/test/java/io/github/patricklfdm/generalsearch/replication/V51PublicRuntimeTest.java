package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.*;
import io.github.patricklfdm.generalsearch.index.text.*;
import io.github.patricklfdm.generalsearch.query.*;
import io.github.patricklfdm.generalsearch.ranking.*;
import io.github.patricklfdm.generalsearch.schema.*;
import io.github.patricklfdm.generalsearch.search.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

/** All voter creation/start/election/application admission uses the shipped public API. */
class V51PublicRuntimeTest {
    @TempDir Path root;
    @AfterEach void reset() {AutomaticRuntimeHooks.CURRENT.remove();}
    static final ReplicationBounds BOUNDS=ReplicaLeaderTestSupport.bounds(1200,8);
    static final AutomaticLeadershipPolicy POLICY=new AutomaticLeadershipPolicy(1200,3600,6000,9600);
    static final TextField<Doc> TEXT=TextField.of(VALUE,io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer.INSTANCE);
    static SearchEngineBuilder<Integer,Doc> rich() {return SearchEngine.builder(Doc.class,ID).index(IndexDefinition.text(TEXT));}
    static List<AutomaticReplicationGroupConfig<Integer,Doc>> configs(Path root) throws Exception {
        var ports=ReplicaLeaderTestSupport.ports();
        var members=java.util.stream.IntStream.range(0,3).mapToObj(i->new ReplicationMember(new ReplicationNodeId("node-"+(i+1)),new ReplicationEndpoint("127.0.0.1",ports.get(i)))).toList();
        return members.stream().map(m->new AutomaticReplicationGroupConfig<>(new ReplicationGroupId(GROUP),"public-fixture",m.nodeId(),members,
                root.resolve(m.nodeId().value()),storage(root.resolve("app-"+m.nodeId().value()),2),BOUNDS,POLICY)).toList();
    }
    final class Group implements AutoCloseable {
        final List<AutomaticReplicationGroupConfig<Integer,Doc>> configs;
        final List<AutomaticReplicatedSearchEngine<Integer,Doc>> engines=new ArrayList<>();
        final SearchEngineBuilder<Integer,Doc> app;
        Group(SearchEngineBuilder<Integer,Doc> app,Path source,boolean start) throws Exception {
            this.app=app;configs=configs(root);
            var request=new AutomaticReplicationBootstrapRequest<>(source==null?ReplicationBootstrapSource.EMPTY:ReplicationBootstrapSource.VERIFIED_V44_BACKUP,source,configs,root.resolve("operation"),1L<<30,1L<<30);
            AutomaticReplicationStorageOperations.applyBootstrap(app,request,AutomaticReplicationStorageOperations.planBootstrap(app,request));
            for(var c:configs)engines.add(AutomaticReplicatedSearchEngines.builder(app,c).build());
            if(start)CompletableFuture.allOf(engines.stream().map(e->e.start().thenAccept(s->assertEquals(AutomaticReplicationState.FOLLOWER,s.state()))).toArray(CompletableFuture[]::new)).get(15,TimeUnit.SECONDS);
        }
        AutomaticReplicatedSearchEngine<Integer,Doc> leader() throws Exception {
            long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
            while(System.nanoTime()<until){for(var e:engines)if(e.leadershipStatus().state()==AutomaticReplicationState.LEADER_READY)return e;Thread.sleep(20);}
            throw new AssertionError(engines.stream().map(e->e.leadershipStatus().toString()).toList());
        }
        @Override public void close(){for(var e:engines)e.close();}
    }
    static AutomaticReplicationException rejected(AutomaticReplicationException.Reason reason,AutomaticReplicationException.Outcome outcome,Runnable call) {
        Throwable failure=assertThrows(RuntimeException.class,call::run);
        while(failure instanceof CompletionException)failure=failure.getCause();
        var error=assertInstanceOf(AutomaticReplicationException.class,failure);assertEquals(reason,error.reason());assertEquals(outcome,error.outcome());return error;
    }
    static void latch(CountDownLatch latch) {
        try {assertTrue(latch.await(30,TimeUnit.SECONDS));}catch(InterruptedException e){throw new AssertionError(e);}
    }
    @Test void buildIsPureAndAllStoppedOperationsRejectBeforeArguments() throws Exception {
        var app=builder();try(var engine=AutomaticReplicatedSearchEngines.builder(app,configs(root).getFirst()).build()) {
            assertEquals(AutomaticReplicationState.STOPPED,engine.leadershipStatus().state());
            assertEquals(0,engine.leadershipStatus().promisedEpoch());assertSame(ID,engine.field("id"));
            rejected(NOT_READY,NOT_SUBMITTED,()->engine.add(null).join());
            rejected(NOT_READY,NOT_APPLICABLE,()->engine.get(null));
            rejected(NOT_READY,NOT_APPLICABLE,engine::durabilityMetrics);
            try(var files=Files.list(root)){assertEquals(0,files.count());}
        }
    }
    @Test void missingAuthorityFailsWithoutCreatingVotersAndRequiresNewHandle() throws Exception {
        try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),configs(root).getFirst()).build()) {
            assertThrows(CompletionException.class,()->engine.start().join());
            assertEquals(AutomaticReplicationState.FAILED,engine.leadershipStatus().state());
            assertThrows(CompletionException.class,()->engine.start().join());assertFalse(Files.exists(root.resolve("node-1")));
        }
    }
    @Test void cancelledStartCopyAndLocalRecoveryNeedNeitherCoordinatorNorQuorum() throws Exception {
        Path source=root.resolve("source");
        builder().writeDurableBackup(new DurableApplicationState<>(UUID.randomUUID(),41,List.of(new Doc(1,"shared")),List.of(IndexDefinition.equality(VALUE))),
                storage(root.resolve("anchor"),2),new DurableBackupRequest(source,1<<20));
        try(var group=new Group(builder(),source,false)) {
            Files.move(root.resolve("operation"),root.resolve("unmounted-coordinator"));Files.move(source,root.resolve("unmounted-source"));
            var first=group.engines.getFirst();var copy=first.start();copy.cancel(true);
            var status=first.start().get(15,TimeUnit.SECONDS);assertEquals(AutomaticReplicationState.FOLLOWER,status.state());
            assertEquals(41,status.applicationSequence());assertEquals(0,status.appliedIndex());
            assertEquals(41,first.durabilityMetrics().currentSequence());assertTrue(first.lastReopenReport().isEmpty());
            first.checkpoint().get(15,TimeUnit.SECONDS);assertEquals(41,first.durabilityMetrics().checkpointSequence());
            rejected(NOT_LEADER,NOT_APPLICABLE,()->first.get(1));
            try(var duplicate=AutomaticReplicatedSearchEngines.builder(builder(),group.configs.getFirst()).build()) {assertThrows(CompletionException.class,()->duplicate.start().join());}
        }
    }
    @Test void changedLocalAndApplicationConfigurationsReleaseFailedStartupOwner() throws Exception {
        try(var group=new Group(builder(),null,false)) {
            try(var invalid=AutomaticReplicatedSearchEngines.builder(builder().plannerConfig(PlannerConfig.DEFAULT),group.configs.getFirst()).build()) {
                rejected(INTEGRITY_FAILURE,NOT_APPLICABLE,()->invalid.start().join());
            }
            assertEquals(AutomaticReplicationState.FOLLOWER,group.engines.getFirst().start().get(15,TimeUnit.SECONDS).state());
        }
    }
    private void barrier(AutomaticReplicatedSearchEngine<Integer,Doc> leader,Runnable read) {
        long before=leader.leadershipStatus().provenIndex(),sequence=leader.leadershipStatus().applicationSequence();read.run();
        assertEquals(before+1,leader.leadershipStatus().provenIndex());assertEquals(sequence,leader.leadershipStatus().applicationSequence());
    }
    @Test void completeFacadeUsesOneEntryPerCallAndNoOpKeepsPageCursor() throws Exception {
        try(var group=new Group(rich(),null,true)) {
            var leader=group.leader();
            leader.add(new Doc(1,"shared alpha")).join();leader.addAll(List.of(new Doc(2,"shared beta"),new Doc(3,"other"))).join();
            leader.update(new Doc(3,"shared gamma")).join();leader.updateAll(List.of(new Doc(1,"shared delta"))).join();
            leader.remove(3).join();leader.removeAll(List.of(1)).join();
            leader.createIndex(IndexDefinition.equality(ID)).join();leader.dropIndex("id").join();
            assertEquals(8,leader.currentSequence());
            assertEquals(0,leader.durabilityMetrics().replayedRecords());assertEquals(0,leader.durabilityMetrics().walGeneration());
            assertFalse(leader.durabilityMetrics().recoveryDuration().isZero());
            leader.add(new Doc(4,"shared epsilon")).join();
            barrier(leader,()->assertEquals(2,leader.get(2).id()));
            barrier(leader,()->assertEquals(2,leader.search(Query.matchAll()).size()));
            barrier(leader,()->assertEquals(2,leader.searchTopK(RankedSearchRequest.of(TextScoringQuery.of(TEXT,"shared"),10)).size()));
            var request=SearchRequest.<Doc>builder().query(SearchQueries.text(TEXT,"shared")).limit(1).build();
            barrier(leader,()->assertEquals(1,leader.search(request).hits().size()));
            var page=new AtomicReference<SearchPageResult<Doc>>();barrier(leader,()->page.set(leader.search(SearchPageRequest.builder(request).build())));
            barrier(leader,()->assertEquals(1,leader.search(SearchPageRequest.builder(request).after(page.get().nextCursor().orElseThrow()).build()).hits().size()));
            barrier(leader,()->assertEquals(1,leader.search(HighlightedSearchRequest.builder(request).field(TEXT).build()).hits().size()));
            barrier(leader,()->assertTrue(leader.explain(request,2).isPresent()));barrier(leader,leader::metrics);barrier(leader,()->assertEquals(9,leader.currentSequence()));
            assertSame(TEXT,leader.textField("value"));assertSame(ID,leader.field("id",Integer.class));
            var business=new IllegalArgumentException("query sentinel");assertSame(business,assertThrows(IllegalArgumentException.class,()->leader.search(d->{throw business;})));
            Path target=root.resolve("backup");leader.checkpoint().join();assertEquals(9,leader.durabilityMetrics().checkpointSequence());
            leader.backup(new DurableBackupRequest(target,1<<20)).join();
            var state=rich().readDurableBackup(target,new DurableVerificationConfig<>("fixture-store","fixture-schema",new Codec(),1,1024,65536,10000),1<<20);
            assertEquals(9,state.sequence());assertEquals(List.of(2,4),state.documents().stream().map(Doc::id).toList());
            assertThrows(CompletionException.class,()->leader.backup(new DurableBackupRequest(target,1<<20)).join());
            for(var e:group.engines)if(e!=leader) {
                rejected(NOT_LEADER,NOT_SUBMITTED,()->e.addAll(null).join());rejected(NOT_LEADER,NOT_APPLICABLE,()->e.search(request));
                assertTrue(e.leadershipStatus().activeEpoch()==0);
            }
        }
    }
    @Test void queryReentryFailsButStatusAndNormalCompletionCallbacksRemainUsable() throws Exception {
        try(var group=new Group(builder(),null,true)) {
            var leader=group.leader();leader.add(new Doc(1,"shared")).join();
            assertEquals(1,leader.search(doc->{
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.get(1));rejected(REENTRANT_CALL,NOT_SUBMITTED,()->leader.add(doc).join());
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.start().join());rejected(REENTRANT_CALL,NOT_APPLICABLE,leader::close);
                rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.checkpoint().join());rejected(REENTRANT_CALL,NOT_APPLICABLE,()->leader.backup(null).join());
                assertNotNull(leader.leadershipStatus());assertSame(ID,leader.field("id"));return true;
            }).size());
            leader.update(new Doc(1,"changed")).thenRun(()->assertEquals("changed",leader.get(1).value())).get(15,TimeUnit.SECONDS);
            var both=new CountDownLatch(2);
            var first=leader.add(new Doc(2,"shared")).thenRun(()->{both.countDown();latch(both);assertNotNull(leader.get(1));});
            var second=leader.add(new Doc(3,"shared")).thenRun(()->{both.countDown();latch(both);assertNotNull(leader.get(2));});
            CompletableFuture.allOf(first,second).get(15,TimeUnit.SECONDS);
        }
    }
    @Test void closeRetainsOwnershipWhileReadViewIsActiveAndRetryReleasesIt() throws Exception {
        var release=new CountDownLatch(1);var entered=new CountDownLatch(1);
        try(var group=new Group(builder(),null,true)) {
            var leader=group.leader();leader.add(new Doc(1,"shared")).join();
            var reading=CompletableFuture.supplyAsync(()->leader.search(d->{entered.countDown();latch(release);return true;}));
            assertTrue(entered.await(15,TimeUnit.SECONDS));
            try {
                rejected(DEADLINE_EXCEEDED,NOT_APPLICABLE,leader::close);
                var c=group.configs.stream().filter(v->v.localNodeId().equals(leader.leadershipStatus().localNodeId())).findFirst().orElseThrow();
                try(var duplicate=AutomaticReplicatedSearchEngines.builder(builder(),c).build()){assertThrows(CompletionException.class,()->duplicate.start().join());}
            } finally {release.countDown();}
            assertEquals(1,reading.get(15,TimeUnit.SECONDS).size());leader.close();leader.close();
            assertEquals(AutomaticReplicationState.CLOSED,leader.leadershipStatus().state());assertEquals(DurabilityStatus.CLOSED,leader.durabilityMetrics().status());
        } finally {release.countDown();}
    }
    @Test void missingQuorumCannotReturnAStaleRead() throws Exception {
        try(var group=new Group(builder(),null,true)) {
            var leader=group.leader();leader.add(new Doc(1,"shared")).join();
            for(var e:group.engines)if(e!=leader)e.close();
            var error=assertThrows(AutomaticReplicationException.class,()->leader.get(1));
            assertEquals(NOT_APPLICABLE,error.outcome());assertTrue(Set.of(QUORUM_UNAVAILABLE,DEADLINE_EXCEEDED,NOT_READY).contains(error.reason()));
        }
    }
    @Test void queuedDeadlinesAndCancellationDoNotInvokeInvalidArgumentsOrAppend() throws Exception {
        var release=new CountDownLatch(1);var entered=new CountDownLatch(1);
        try(var group=new Group(builder(),null,true)) {
            var leader=group.leader();leader.add(new Doc(1,"shared")).join();
            var reading=CompletableFuture.supplyAsync(()->leader.search(d->{entered.countDown();latch(release);return true;}));
            assertTrue(entered.await(15,TimeUnit.SECONDS));long cut=leader.leadershipStatus().provenIndex();
            try {
                var cancelled=leader.add(null);assertTrue(cancelled.cancel(true));
                // Account for completion callbacks retaining their bounded permit until they return.
                long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);
                while(leader.leadershipStatus().pendingOperations()>1&&System.nanoTime()<until)Thread.sleep(2);
                var queued=new ArrayList<CompletableFuture<Void>>();
                for(int i=1;i<BOUNDS.maxPendingClientOperations();i++)queued.add(leader.add(null));
                rejected(CAPACITY_EXCEEDED,NOT_SUBMITTED,()->leader.add(null).join());
                for(var q:queued)rejected(DEADLINE_EXCEEDED,NOT_SUBMITTED,q::join);
                assertEquals(cut,leader.leadershipStatus().provenIndex());
            } finally {release.countDown();}
            assertEquals(1,reading.get(15,TimeUnit.SECONDS).size());
        } finally {release.countDown();}
    }
    @Test void oversizedEncodingIsNotSubmittedButFirstAuthorityIoIsIndeterminate() throws Exception {
        var armed=new AtomicBoolean();var target=new AtomicReference<String>();
        try(var group=new Group(builder(),null,false)) {
            for(int i=0;i<3;i++) {
                String local=group.configs.get(i).localNodeId().value();
                AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(new AutomaticStore.Faults(){
                    public void at(String point) throws java.io.IOException {
                        if(point.equals("ACCEPT_BEFORE_WRITE")&&local.equals(target.get())&&armed.compareAndSet(true,false))throw new java.io.IOException("first authority IO cut");
                    }
                },(a,b,c)->{},AutomaticRuntime.Events.NONE));
                group.engines.get(i).start().get(15,TimeUnit.SECONDS);
            }
            var leader=group.leader();long before=leader.leadershipStatus().provenIndex();
            rejected(CAPACITY_EXCEEDED,NOT_SUBMITTED,()->leader.add(new Doc(1,"x".repeat(65537))).join());
            assertEquals(before,leader.leadershipStatus().provenIndex());
            target.set(leader.leadershipStatus().localNodeId().value());armed.set(true);
            rejected(STORAGE_FAILURE,INDETERMINATE,()->leader.add(new Doc(1,"shared")).join());
            assertEquals(DurabilityStatus.FAILED,leader.durabilityMetrics().status());
        }
    }

    @Test void codecCallbacksCannotReenterStartupOrCloseAndBuildInvokesNone() throws Exception {
        try(var group=new Group(builder(),null,false)) {
            var handle=new AtomicReference<AutomaticReplicatedSearchEngine<Integer,Doc>>();var calls=new AtomicInteger();
            var codec=new DurableCodec<Integer,Doc>() {
                final Codec delegate=new Codec();
                void callback(){calls.incrementAndGet();var e=handle.get();if(e!=null){
                    rejected(REENTRANT_CALL,NOT_APPLICABLE,()->e.start().join());
                    rejected(REENTRANT_CALL,NOT_APPLICABLE,e::close);assertNotNull(e.leadershipStatus());
                }}
                public String codecId(){callback();return delegate.codecId();}public int codecVersion(){callback();return 1;}
                public byte[] encodeKey(Integer k){callback();return delegate.encodeKey(k);}public Integer decodeKey(byte[] b){callback();return delegate.decodeKey(b);}
                public byte[] encodeDocument(Doc d){callback();return delegate.encodeDocument(d);}public Doc decodeDocument(byte[] b){callback();return delegate.decodeDocument(b);}
            };
            var c=group.configs.getFirst();var old=c.materialization();
            var materialization=DurableStorageConfig.builder(old.directory(),codec).format(old.format()).storageIdentity(old.storageIdentity()).schemaIdentity(old.schemaIdentity())
                    .maxEncodedKeyBytes(old.maxEncodedKeyBytes()).maxEncodedDocumentBytes(old.maxEncodedDocumentBytes()).maxBulkElements(old.maxBulkElements())
                    .maxDocuments(old.maxDocuments()).checkpointWalBytes(old.checkpointWalBytes()).maxRetainedBytes(old.maxRetainedBytes()).maxDerivedStateBytes(old.maxDerivedStateBytes()).build();
            var config=new AutomaticReplicationGroupConfig<>(c.groupId(),c.configurationId(),c.localNodeId(),c.members(),c.replicaDirectory(),materialization,c.bounds(),c.leadershipPolicy());
            calls.set(0);
            try(var engine=AutomaticReplicatedSearchEngines.builder(builder(),config).build()) {
                assertEquals(0,calls.get());handle.set(engine);
                assertEquals(AutomaticReplicationState.FOLLOWER,engine.start().get(15,TimeUnit.SECONDS).state());assertTrue(calls.get()>0);
            }
        }
    }

}
