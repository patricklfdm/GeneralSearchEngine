package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.*;
import static io.github.patricklfdm.generalsearch.replication.V52PublicReadTest.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import io.github.patricklfdm.generalsearch.durability.DurabilityStatus;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

/** Real public handles; storage hooks inject I/O failure, never successful reads or authority. */
class V52PublicReadStorageFailureTest {
    @TempDir Path root;
    @AfterEach void reset(){AutomaticRuntimeHooks.CURRENT.remove();}
    V51PublicRuntimeTest fixture(Path directory){var f=new V51PublicRuntimeTest();f.root=directory;return f;}

    void start(V51PublicRuntimeTest.Group group,AtomicReference<String> target,AtomicBoolean armed,
               Map<String,Set<String>> pairs) throws Exception {
        for(int i=0;i<3;i++) {
            String local=group.configs.get(i).localNodeId().value();
            AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(new AutomaticStore.Faults(){
                public void at(String point) throws IOException {
                    if(point.equals("ACCEPT_BEFORE_WRITE")&&local.equals(target.get())&&armed.compareAndSet(true,false))
                        throw new IOException("read qualification authority I/O failure");
                }
            },(a,b,c)->{},(event,row)->{
                if(event.equals("PROMISE_QUORUM")) {
                    var selected=AutomaticRecords.decode(AutomaticRecords.unbase(row.get("selected")),"SELECTED");
                    var nodes=new HashSet<String>();
                    for(var basis:AutomaticRecords.list(selected.value().get("bases")))nodes.add(AutomaticRecords.text(AutomaticRecords.object(basis),"node"));
                    pairs.put(local,Set.copyOf(nodes));
                }
            }));
            group.engines.get(i).start().get(15,TimeUnit.SECONDS);
        }
        AutomaticRuntimeHooks.CURRENT.remove();
    }

    @Test void failedAuthorityWriteRejectsWaitingAndNewReadsWithoutCallbacks() throws Exception {
        var target=new AtomicReference<String>();var armed=new AtomicBoolean();var calls=new AtomicInteger();
        try(var group=fixture(root).new Group(rich(),null,false)) {
            start(group,target,armed,new ConcurrentHashMap<>());var leader=group.leader();leader.add(new Doc(1,"before failure")).join();
            var token=leader.read(STRONG,v->v.get(1)).get(10,TimeUnit.SECONDS).progress();idle(leader);
            var waiting=leader.read(minimum(index(token,token.index()+1),60000),v->{calls.incrementAndGet();return v.get(1);});
            assertFalse(waiting.isDone());target.set(leader.leadershipStatus().localNodeId().value());armed.set(true);
            rejected(STORAGE_FAILURE,INDETERMINATE,()->leader.add(new Doc(2,"failed write")).join());assertFalse(armed.get());
            rejected(STORAGE_FAILURE,NOT_APPLICABLE,waiting::join);
            for(var options:List.of(STRONG,STALE,minimum(token,0)))
                rejected(STORAGE_FAILURE,NOT_APPLICABLE,()->leader.read(options,v->{calls.incrementAndGet();return v.get(1);}).join());
            assertEquals(0,calls.get());idle(leader);assertEquals(DurabilityStatus.FAILED,leader.durabilityMetrics().status());
        }
    }

    @Test void alreadyCapturedFollowerViewSurvivesFatalIoButNoLaterCaptureDoes() throws Exception {
        var target=new AtomicReference<String>();var armed=new AtomicBoolean();var pairs=new ConcurrentHashMap<String,Set<String>>();
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var escaped=new AtomicReference<ReplicaReadView<Integer,Doc>>();
        try(var group=fixture(root).new Group(rich(),null,false)) {
            start(group,target,armed,pairs);var leader=group.leader();leader.add(new Doc(1,"verified before failure")).join();
            var token=leader.read(STRONG,v->v.get(1)).get(10,TimeUnit.SECONDS).progress();String owner=leader.leadershipStatus().localNodeId().value();
            String peer=pairs.get(owner).stream().filter(n->!n.equals(owner)).findFirst().orElseThrow();
            var follower=group.engines.stream().filter(e->e.leadershipStatus().localNodeId().value().equals(peer)).findFirst().orElseThrow();
            follower.read(minimum(token,5000),v->v.get(1)).get(10,TimeUnit.SECONDS);idle(follower);
            var captured=follower.read(STALE,v->{
                escaped.set(v);var before=v.get(1);entered.countDown();
                try {assertTrue(release.await(20,TimeUnit.SECONDS));}catch(InterruptedException e){throw new AssertionError(e);}
                assertEquals(before,v.get(1));return before;
            });
            CompletableFuture<Void> write;
            try {
                await(entered);
                var waiting=follower.read(minimum(index(token,token.index()+1),60000),v->fail("failed authority captured waiter"));
                target.set(peer);armed.set(true);write=leader.add(new Doc(2,"failed selected peer"));
                var failure=assertThrows(ExecutionException.class,()->waiting.get(10,TimeUnit.SECONDS));
                assertEquals(STORAGE_FAILURE,assertInstanceOf(AutomaticReplicationException.class,failure.getCause()).reason());assertFalse(armed.get());
                for(var options:List.of(STRONG,STALE,minimum(token,0)))
                    rejected(STORAGE_FAILURE,NOT_APPLICABLE,()->follower.read(options,v->fail("new capture after fatal I/O")).join());
                assertFalse(captured.isDone());assertEquals(DurabilityStatus.FAILED,follower.durabilityMetrics().status());
            } finally {release.countDown();}
            assertEquals(new Doc(1,"verified before failure"),captured.get(5,TimeUnit.SECONDS).value());idle(follower);
            assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,assertThrows(ReplicaReadException.class,escaped.get()::currentSequence).reason());
            var failed=assertThrows(CompletionException.class,write::join);
            assertEquals(INDETERMINATE,assertInstanceOf(AutomaticReplicationException.class,failed.getCause()).outcome());
        } finally {release.countDown();}
    }

    @Test void corruptRequiredBootstrapAuthorityNeverStartsAReadableHandle() throws Exception {
        for(String file:List.of("manifest.gsr","genesis.gsr")) {
            Path directory=Files.createDirectory(root.resolve(file));
            try(var group=fixture(directory).new Group(rich(),null,false)) {
                var config=group.configs.getFirst();var path=config.replicaDirectory().resolve(file);
                byte[] original=Files.readAllBytes(path),corrupt=original.clone();corrupt[corrupt.length-1]^=1;Files.write(path,corrupt);
                var engine=group.engines.getFirst();rejected(INTEGRITY_FAILURE,NOT_APPLICABLE,()->engine.start().join());
                assertEquals(AutomaticReplicationState.FAILED,engine.leadershipStatus().state());
                var token=new ReplicaReadToken(1,config.groupId(),new UUID(1,2),"ab".repeat(32),0);
                for(var options:List.of(STRONG,STALE,minimum(token,0)))
                    rejected(NOT_READY,NOT_APPLICABLE,()->engine.read(options,v->fail("corrupt startup exposed a view")).join());
                assertArrayEquals(corrupt,Files.readAllBytes(path),"read cannot repair damaged authority");
            }
        }
    }
}
