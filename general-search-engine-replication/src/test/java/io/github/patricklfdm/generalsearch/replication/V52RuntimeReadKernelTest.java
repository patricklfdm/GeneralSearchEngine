package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Real runtime/application tests through the internal Phase 2 port, not public qualification. */
class V52RuntimeReadKernelTest {
    @TempDir Path root;
    static final ReplicaReadOptions STALE=new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,Optional.empty(),0);
    static final ReplicaReadOptions STRONG=new ReplicaReadOptions(ReplicaReadPolicy.LEADER_STRONG,Optional.empty(),0);
    static long deadline() {return System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(V51RuntimeFixture.POLICY.operationTimeoutMillis());}
    static void await(CountDownLatch latch) {
        try {assertTrue(latch.await(5,TimeUnit.SECONDS));}catch(InterruptedException e){Thread.currentThread().interrupt();throw new AssertionError(e);}
    }
    static void reason(AutomaticReplicationException.Reason reason,CompletableFuture<?> result) throws Exception {
        var failure=assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS));
        assertEquals(reason,assertInstanceOf(AutomaticReplicationException.class,failure.getCause()).reason());
    }
    final class Reads implements AutoCloseable {
        final ScheduledThreadPoolExecutor timer=new ScheduledThreadPoolExecutor(1);
        final ExecutorService completions=Executors.newVirtualThreadPerTaskExecutor();
        final Semaphore permits=new Semaphore(BOUNDS.maxPendingClientOperations());
        final AutomaticReadQueue<Integer,Document> queue;
        Reads(AutomaticRuntime<Integer,Document> node) {
            timer.setRemoveOnCancelPolicy(true);queue=node.readQueue(permits,timer,completions);
        }
        @Override public void close() throws InterruptedException {
            queue.close();timer.shutdown();completions.shutdown();
            assertTrue(timer.awaitTermination(5,TimeUnit.SECONDS));assertTrue(completions.awaitTermination(5,TimeUnit.SECONDS));
        }
    }

    @Test void loneFollowerCanReadItsVerifiedGenesisWithoutNetworkOrFreshQuorum() throws Exception {
        try(var group=new V51RuntimeFixture(root,true,false)) {
            group.open(1);var follower=group.nodes.get("node-1");
            assertEquals(AutomaticReplicationState.FOLLOWER,follower.started().get(5,TimeUnit.SECONDS).state());
            try(var reads=new Reads(follower)) {
                var result=reads.queue.submit(STALE,v->{assertNull(v.get(1));return v.currentSequence();},deadline()).future().get(5,TimeUnit.SECONDS);
                assertEquals(0,result.progress().index());assertEquals(0,result.value());assertEquals(0,result.applicationSequence());
                reason(NOT_LEADER,reads.queue.submit(STRONG,v->fail("follower strong callback"),deadline()).future());
                assertEquals(0,follower.view().provenIndex());assertTrue(group.wire.isEmpty());
            }
        }
    }

    @Test void fullWaiterCapacityCannotBlockThePublicationThatSatisfiesIt() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();try(var reads=new Reads(leader)) {
                var previous=reads.queue.submit(STALE,v->v.currentSequence(),deadline()).future().get(5,TimeUnit.SECONDS).progress();
                long settledBy=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
                while(reads.queue.counts().owned()!=0&&System.nanoTime()<settledBy)Thread.onSpinWait();
                assertEquals(0,reads.queue.counts().owned(),"previous completion must release before the saturation setup");
                var minimum=new ReplicaReadToken(1,previous.groupId(),previous.historyId(),previous.manifestDigest(),previous.index()+1);
                var options=new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.of(minimum),60000);
                var results=new ArrayList<CompletableFuture<ReplicaReadResult<Document>>>();
                int limit=Math.min(64,BOUNDS.maxPendingClientOperations()-1);
                for(int i=0;i<limit;i++)results.add(reads.queue.submit(options,v->v.get(1),deadline()).future());
                assertEquals(limit,reads.queue.counts().waiting());assertEquals(0,reads.queue.counts().marker());
                assertTrue(reads.permits.tryAcquire());reads.permits.release();
                long index=leader.submit(1,app->app.documents("ADD",List.of(new Document(1,"published")))).get(10,TimeUnit.SECONDS);
                for(var future:results) {
                    var result=future.get(5,TimeUnit.SECONDS);assertEquals(new Document(1,"published"),result.value());
                    assertTrue(result.progress().index()>=index);assertEquals(1,result.applicationSequence());
                }
            }
        }
    }

    @Test void capturedViewStaysAtOneCutWhileAQueuedWriteWaitsForRelease() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();try(var reads=new Reads(leader)) {
                leader.submit(1,app->app.documents("ADD",List.of(new Document(1,"before")))).get(10,TimeUnit.SECONDS);
                var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var invoked=new AtomicInteger();
                var result=reads.queue.submit(STALE,v->{
                    invoked.incrementAndGet();var before=v.get(1);long sequence=v.currentSequence();entered.countDown();await(release);
                    assertEquals(before,v.get(1));assertEquals(sequence,v.currentSequence());return before;
                },deadline()).future();
                CompletableFuture<Long> write;
                try {
                    await(entered);write=leader.submit(2,app->app.documents("UPDATE",List.of(new Document(1,"after"))));
                    assertFalse(write.isDone());assertEquals(1,reads.queue.counts().captured());
                } finally {release.countDown();}
                assertEquals("before",result.get(5,TimeUnit.SECONDS).value().value());write.get(10,TimeUnit.SECONDS);
                assertEquals("after",reads.queue.submit(STALE,v->v.get(1).value(),deadline()).future().get(5,TimeUnit.SECONDS).value());
                assertEquals(1,invoked.get());
            }
        }
    }

    @Test void cancelledActiveViewSurvivesIncompleteCloseAndRetainsStoreOwnership() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();String name=group.name(leader);try(var reads=new Reads(leader)) {
                var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var returned=new CountDownLatch(1);
                var escaped=new AtomicReference<ReplicaReadView<Integer,Document>>();
                var result=reads.queue.submit(STALE,v->{
                    escaped.set(v);entered.countDown();await(release);assertEquals(0,v.currentSequence());returned.countDown();return null;
                },deadline()).future();
                try {
                    await(entered);assertTrue(result.cancel(true));
                    assertEquals(DEADLINE_EXCEEDED,assertThrows(AutomaticReplicationException.class,leader::close).reason());
                    assertEquals(1,reads.queue.counts().captured());
                    assertThrows(AutomaticReplicationException.class,()->AutomaticStore.open(root.resolve(name),group.manifest,name,BOUNDS,AutomaticStore.Faults.NONE));
                } finally {release.countDown();}
                await(returned);group.stop(name);assertTrue(result.isCancelled());
                assertEquals(ReplicaReadException.Reason.VIEW_NOT_ACTIVE,
                        assertThrows(ReplicaReadException.class,escaped.get()::currentSequence).reason());
                try(var reopened=AutomaticStore.open(root.resolve(name),group.manifest,name,BOUNDS,AutomaticStore.Faults.NONE)) {
                    assertEquals(0L,reopened.status().get("applicationSequence"));
                }
            }
        }
    }

    @Test void freshBarrierProducesTheActualNoOpPublicationToken() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();try(var reads=new Reads(leader)) {
                long epoch=leader.view().promisedEpoch();
                var request=reads.queue.submit(STRONG,v->v.currentSequence(),deadline());
                long index=leader.submit(9,app->new byte[0]).get(10,TimeUnit.SECONDS);request.barrier(epoch,index);
                var result=request.future().get(5,TimeUnit.SECONDS);
                assertEquals(index,result.progress().index());assertEquals(0,result.value());assertEquals(ReplicaReadPolicy.LEADER_STRONG,result.policy());
                var mismatch=reads.queue.submit(STRONG,v->fail("wrong barrier callback"),deadline());
                mismatch.barrier(epoch,index-1);reason(STALE_EPOCH,mismatch.future());
            }
        }
    }

    @Test void higherPrepareAfterFreshBarrierFencesTheQueuedCaptureWithoutInvokingIt() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();try(var reads=new Reads(leader)) {
                var calls=new AtomicInteger();long epoch=leader.view().promisedEpoch();
                var request=reads.queue.submit(STRONG,v->calls.incrementAndGet(),deadline());
                long index=leader.submit(9,app->new byte[0]).get(10,TimeUnit.SECONDS);
                var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
                var blocker=leader.inspectLocal(engine->{entered.countDown();await(release);return null;});
                CompletableFuture<Void> prepare;
                try {
                    await(entered);request.barrier(epoch,index);
                    prepare=CompletableFuture.runAsync(()->sendHigherPrepare(group,leader));
                    reason(STALE_EPOCH,request.future());assertEquals(0,calls.get());
                } finally {release.countDown();}
                blocker.get(5,TimeUnit.SECONDS);prepare.get(5,TimeUnit.SECONDS);assertEquals(0,calls.get());
            }
        }
    }

    private static void sendHigherPrepare(V51RuntimeFixture group,AutomaticRuntime<Integer,Document> leader) {
        var manifest=AutomaticRecords.decode(group.manifest,"MANIFEST");var members=AutomaticRecords.nodes(manifest.value());
        String local=group.name(leader),peer=members.stream().filter(n->!n.equals(local)).findFirst().orElseThrow();
        long epoch=AutomaticProtocol.nextEpoch(leader.view().promisedEpoch(),members.indexOf(peer));
        var ballot=AutomaticRecords.decode(AutomaticRecords.encode("PROMISE",Map.of("manifestDigest",manifest.digest(),"epoch",epoch,
                "proposer",peer,"incarnation",UUID.randomUUID().toString())),"PROMISE");
        var request=AutomaticWire.message(manifest,ballot,peer,local,"PREPARE",UUID.randomUUID(),1,Map.of("nonce",UUID.randomUUID().toString()));
        var endpoint=AutomaticRecords.object(AutomaticRecords.list(manifest.value().get("members")).get(members.indexOf(local)));
        try(var socket=new java.net.Socket("127.0.0.1",(int)AutomaticRecords.number(endpoint,"port"))) {
            socket.setSoTimeout(5000);socket.getOutputStream().write(AutomaticWire.encode(request,manifest,BOUNDS.maxFrameBytes()));
            byte[] header=socket.getInputStream().readNBytes(48);int size=AutomaticWire.bodyLength(header,BOUNDS.maxFrameBytes());
            byte[] frame=new byte[48+size];System.arraycopy(header,0,frame,0,48);
            System.arraycopy(socket.getInputStream().readNBytes(size),0,frame,48,size);
            assertEquals("PROMISE",AutomaticWire.decode(frame,manifest,BOUNDS.maxFrameBytes()).get("type"));
        } catch(java.io.IOException error){throw new java.io.UncheckedIOException(error);}
    }
}
