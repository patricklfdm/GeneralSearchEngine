package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53MembershipTransportTest.waitFor;

class V53ActivationWaiterCapacityTest {
    @TempDir Path temp;
    final class Fixture implements AutoCloseable {
        final V53ActivationEndpointTest.Local local;
        final MembershipActivationEndpoint endpoint;
        final ExecutorService callers=Executors.newVirtualThreadPerTaskExecutor();
        final CompletableFuture<Decoded> pending=new CompletableFuture<>();
        final CountDownLatch entered=new CountDownLatch(1);
        final AtomicReference<Decoded> held=new AtomicReference<>();
        final AtomicInteger exchanges=new AtomicInteger();
        final Decoded request;
        Fixture(int limit)throws Exception {
            var helper=new V53ActivationEndpointTest();helper.temp=temp;local=helper.new Local();local.endpoint.close();
            var b=V53TransferServiceTest.bound(2);
            var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),limit,
                    b.maxRetryAttempts(),b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),
                    b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
            endpoint=new MembershipActivationEndpoint(local.base.peer,local.base.peerResources,bounds,(peer,frame,kind,deadline)->{
                exchanges.incrementAndGet();assertEquals(V53SourceExchangeTest.BUDGET,deadline);
                if(held.compareAndSet(null,frame)){entered.countDown();return pending;}
                try{return CompletableFuture.completedFuture(local.leaderService.handle(local.base.identity(),frame));}
                catch(Exception error){return CompletableFuture.failedFuture(error);}
            },V53ActivationEndpointTest.verifier(),List.of(),List.of(),temp.resolve("bounded-"+UUID.randomUUID()),
                    local.base.clock::get,V53SourceExchangeTest.BUDGET);
            request=local.prepare();
        }
        Future<Decoded> call(Decoded frame){return callers.submit(()->endpoint.handle(local.proposer(),frame));}
        int waiters(){return local.base.peerResources.usage().counts().getOrDefault(MembershipResources.Unit.WAITER,0);}
        void release()throws Exception {pending.complete(local.leaderService.handle(local.base.identity(),held.get()));}
        Map<String,String> files()throws Exception{return V53ReplayFilesTest.files(local.base.f.request.targets().get(1).replicaDirectory());}
        @Override public void close()throws Exception {
            try{endpoint.close();}finally{callers.close();local.close();}
        }
    }
    static void rejected(Decoded request,Decoded response) {
        assertEquals("REJECT",response.kind());var values=new TreeMap<>(request.value());
        values.put("sender",request.value().get("recipient"));values.put("recipient",request.value().get("sender"));
        values.put("payload",Map.of("promised",request.value().get("ballot"),"reason","CAPACITY_EXCEEDED"));
        assertArrayEquals(encode("wire","REJECT",values),response.bytes());
    }
    static Decoded prompt(Future<Decoded> response)throws Exception {
        // A refusal must not wait for the blocked original 60-second campaign.
        try{return response.get(2,TimeUnit.SECONDS);}
        catch(TimeoutException error){fail("excess activation waiter was admitted instead of refused");return null;}
    }
    @ParameterizedTest @ValueSource(ints={2,64})
    void duplicateControlsRespectBothInheritedAndSharedWaiterBounds(int limit)throws Exception {
        try(var f=new Fixture(limit)) {
            var calls=new ArrayList<Future<Decoded>>();calls.add(f.call(f.request));assertTrue(f.entered.await(5,TimeUnit.SECONDS));
            for(int n=1;n<limit;n++)calls.add(f.call(f.request));waitFor(()->f.endpoint.usage().waiters()==limit);
            var before=f.files();rejected(f.request,prompt(f.call(f.request)));
            assertEquals(limit,f.waiters());assertEquals(before,f.files());assertEquals(1,f.exchanges.get());
            f.release();var response=calls.getFirst().get(10,TimeUnit.SECONDS);assertEquals("PROMISE",response.kind());
            for(var call:calls)assertArrayEquals(response.bytes(),call.get(10,TimeUnit.SECONDS).bytes());
            assertEquals(0,f.waiters());assertEquals(0,f.endpoint.usage().waiters());assertEquals(3,f.exchanges.get());
            assertArrayEquals(response.bytes(),f.call(f.request).get(5,TimeUnit.SECONDS).bytes());
            assertEquals(3,f.exchanges.get());assertEquals(0,f.waiters());
        }
    }
    @Test void sharedExhaustionRefusesDispatchButStillObservesHigherPrepare()throws Exception {
        try(var f=new Fixture(10000)) {
            var held=new ArrayList<MembershipResources.Lease>();
            try {
                for(int n=0;n<64;n++)held.add(f.local.base.peerResources.reserve(MembershipResources.Unit.WAITER,"other-owner-"+n,0));
                var before=f.files();rejected(f.request,prompt(f.call(f.request)));assertEquals(0,f.exchanges.get());
                var value=new TreeMap<>(f.request.value());var higher=new TreeMap<>(object(value.get("ballot")));
                higher.put("counter",number(higher.get("counter"))+1);value.put("ballot",higher);
                var request=decode(encode("wire","PREPARE",value),"wire","PREPARE");rejected(request,prompt(f.call(request)));
                var lost=assertThrows(MembershipCampaignLost.class,()->f.local.base.peer.checkCampaignWait(
                        (String)f.request.value().get("view"),object(f.request.value().get("ballot"))));
                assertEquals(MembershipCampaignLost.Reason.HIGHER_BALLOT,lost.reason);
                assertEquals(before,f.files());assertEquals(0,f.exchanges.get());assertEquals(0,f.endpoint.usage().waiters());assertEquals(64,f.waiters());
            }finally{held.forEach(MembershipResources.Lease::close);}
        }
    }
    @Test void interruptedDuplicateReleasesOnlyItsWaiterAndKeepsOriginalControl()throws Exception {
        try(var f=new Fixture(2)) {
            var original=f.call(f.request);assertTrue(f.entered.await(5,TimeUnit.SECONDS));
            var failure=new AtomicReference<Throwable>();var interrupted=new AtomicBoolean();
            var duplicate=Thread.ofVirtual().start(()->{
                try{f.endpoint.handle(f.local.proposer(),f.request);}catch(Throwable error){failure.set(error);interrupted.set(Thread.currentThread().isInterrupted());}
            });
            waitFor(()->f.endpoint.usage().waiters()==2);
            try{assertEquals(2,f.waiters());}finally{duplicate.interrupt();duplicate.join(5000);}
            assertFalse(duplicate.isAlive());assertInstanceOf(IOException.class,failure.get());assertTrue(interrupted.get());
            assertEquals(1,f.waiters());assertFalse(f.pending.isCancelled());assertEquals(1,f.exchanges.get());
            var replacement=f.call(f.request);waitFor(()->f.endpoint.usage().waiters()==2);f.release();
            assertArrayEquals(original.get(10,TimeUnit.SECONDS).bytes(),replacement.get(10,TimeUnit.SECONDS).bytes());assertEquals(0,f.waiters());
        }
    }
    @Test void controlReservationFailureReleasesTheAdmittedWaiter()throws Exception {
        try(var f=new Fixture(2)) {
            var held=new ArrayList<MembershipResources.Lease>();
            try {
                int occupied=f.local.base.peerResources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0);
                for(int n=occupied;n<256;n++)held.add(f.local.base.peerResources.reserve(MembershipResources.Unit.CONTROL,"other-control-"+n,1));
                var before=f.files();var failure=assertThrows(ExecutionException.class,()->f.call(f.request).get(5,TimeUnit.SECONDS));
                assertInstanceOf(IllegalArgumentException.class,failure.getCause());assertEquals("resource ownership/count",failure.getCause().getMessage());
                assertEquals(0,f.waiters());assertEquals(0,f.endpoint.usage().waiters());assertEquals(0,f.exchanges.get());assertEquals(before,f.files());
            }finally{held.forEach(MembershipResources.Lease::close);}
            var call=f.call(f.request);assertTrue(f.entered.await(5,TimeUnit.SECONDS));assertEquals(1,f.waiters());
            f.release();assertEquals("PROMISE",call.get(10,TimeUnit.SECONDS).kind());assertEquals(0,f.waiters());
        }
    }
    @Test void closeReleasesAllDuplicateWaitersBeforeReturning()throws Exception {
        try(var f=new Fixture(2)) {
            var first=f.call(f.request);assertTrue(f.entered.await(5,TimeUnit.SECONDS));var second=f.call(f.request);
            waitFor(()->f.endpoint.usage().waiters()==2);assertEquals(2,f.waiters());f.endpoint.close();
            assertEquals(0,f.waiters());assertEquals(0,f.endpoint.usage().waiters());assertTrue(f.pending.isCancelled());
            assertThrows(ExecutionException.class,()->first.get(5,TimeUnit.SECONDS));assertThrows(ExecutionException.class,()->second.get(5,TimeUnit.SECONDS));
        }
    }
}
