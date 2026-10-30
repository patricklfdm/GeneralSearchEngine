package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ElectionWaitTest.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53ActivationProgressTest {
    @TempDir Path temp;
    V53ActivationEndpointTest.Local local()throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;var local=helper.new Local();
        var deadline=new AtomicLong(Long.MIN_VALUE);
        // These histories admit PREPARE after clock zero. Retain its actual
        // first deadline across all subsequent source exchanges.
        local.link.set((p,r,k,d)->{
            deadline.compareAndSet(Long.MIN_VALUE,local.base.clock.get()+BUDGET);assertEquals(deadline.get(),d);local.calls.incrementAndGet();
            try{return CompletableFuture.completedFuture(local.leaderService.handle(local.base.identity(),r));}
            catch(Exception error){return CompletableFuture.failedFuture(error);}
        });
        return local;
    }
    static MembershipElectionWait waitFor(V53ActivationEndpointTest.Local l,long budget) {
        return new MembershipElectionWait(l.base.peer,l.endpoint,l.base.peerResources,POLICY,l.base.clock::get,(a,b)->a,0,millis(budget));
    }
    static Decoded heartbeat(V53ActivationEndpointTest.Local l)throws Exception {
        var fields=new TreeMap<>(l.prepare().value());fields.put("payload",Map.of("cut",l.base.peer.activationContext().cut,"activated",true));
        return decode(encode("wire","HEARTBEAT",fields),"wire","HEARTBEAT");
    }
    @Test void grantCompletionIsOnceOnlyEvenWithNewTrace()throws Exception {
        try(var l=local()) {
            assertTrue(l.endpoint.activationProgress().isEmpty());l.base.clock.set(millis(10));
            var request=l.prepare();l.endpoint.handle(l.proposer(),request);
            var progress=l.endpoint.activationProgress().orElseThrow();
            assertEquals(MembershipActivationEndpoint.ActivationStage.GRANTED,progress.stage());
            assertEquals(millis(10),progress.completedNanos());assertEquals(request.value().get("ballot"),progress.ballot());
            assertEquals(request.value().get("root"),progress.root());assertEquals(request.value().get("view"),progress.view());
            assertThrows(UnsupportedOperationException.class,()->progress.ballot().put("counter",100L));
            var files=V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory());
            l.base.clock.set(millis(20));l.endpoint.handle(l.proposer(),request);
            l.base.clock.set(millis(30));l.endpoint.handle(l.proposer(),V53ActivationTest.changed(request,"trace",UUID.randomUUID().toString()));
            assertEquals(progress,l.endpoint.activationProgress().orElseThrow());assertEquals(files,V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory()));
            // A completed old milestone does not become fresh when first polled.
            try(var wait=waitFor(l,100)) {
                var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
                try{assertEquals(progress.ballot(),result.get(5,TimeUnit.SECONDS).ballot());}
                finally{wait.close();worker.join(5000);}assertFalse(worker.isAlive());
            }
        }
    }
    @Test void installationAdvancesOnceAfterOriginalSourceValidation()throws Exception {
        try(var l=local()) {
            l.base.clock.set(millis(10));l.endpoint.handle(l.proposer(),l.prepare());
            l.base.offer(V53ActivationEndpointTest.verifier());l.base.campaign.installLocal(List.of(),l.base.received.images());
            l.base.clock.set(millis(20));var selected=l.base.campaign.installation(l.base.identity());
            assertEquals("INSTALL_ACK",l.endpoint.handle(l.proposer(),selected).kind());
            var progress=l.endpoint.activationProgress().orElseThrow();
            assertEquals(MembershipActivationEndpoint.ActivationStage.INSTALLED,progress.stage());assertEquals(millis(20),progress.completedNanos());
            assertArrayEquals(l.base.leader.originalSelection().orElseThrow().bytes(),l.base.peer.originalSelection().orElseThrow().bytes());
            l.base.clock.set(millis(30));l.endpoint.handle(l.proposer(),selected);
            assertEquals(progress,l.endpoint.activationProgress().orElseThrow());
        }
    }
    @Test void waitingSourceAndCapacityRejectionCannotCreateProgress()throws Exception {
        try(var l=local()) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);
            l.link.set((p,r,k,d)->{entered.countDown();return pending;});var prepare=l.prepare();
            var task=CompletableFuture.runAsync(()->assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),prepare)));
            try {
                assertTrue(entered.await(5,TimeUnit.SECONDS));assertTrue(l.endpoint.activationProgress().isEmpty());
                var other=V53ActivationTest.changed(prepare,"trace",UUID.randomUUID().toString());
                assertEquals("REJECT",l.endpoint.handle(l.proposer(),other).kind());assertTrue(l.endpoint.activationProgress().isEmpty());
            }finally{l.endpoint.close();task.get(5,TimeUnit.SECONDS);}
            assertTrue(pending.isCancelled());assertTrue(l.endpoint.activationProgress().isEmpty());
        }
    }
    @Test void malformedOriginalSourceAndForeignSenderCannotCreateProgress()throws Exception {
        try(var l=local()) {
            assertThrows(Exception.class,()->l.endpoint.handle(l.base.identity(),l.prepare()));assertTrue(l.endpoint.activationProgress().isEmpty());
            var original=l.link.get();l.link.set((p,r,k,d)->original.exchange(p,r,k,d).thenApply(reply->{
                if(!k.equals("CHUNK"))return reply;
                var value=new TreeMap<>(reply.value());var payload=new TreeMap<>(object(value.get("payload")));
                byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));bytes[0]^=1;
                payload.put("bytes",Base64.getEncoder().encodeToString(bytes));payload.put("digest",hash(bytes));value.put("payload",payload);
                return decode(encode("wire",reply.kind(),value),"wire",reply.kind());
            }));
            assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),l.prepare()));assertTrue(l.endpoint.activationProgress().isEmpty());
        }
    }
    @Test void revocationExpiryAndHigherFenceHideProgressWithoutWriterAccess()throws Exception {
        for(String mode:List.of("close","abandon","expiry","higher"))try(var l=local()) {
            l.endpoint.handle(l.proposer(),l.prepare());assertTrue(l.endpoint.activationProgress().isPresent());
            switch(mode) {
                case "close"->l.endpoint.close();
                case "abandon"->l.endpoint.abandon(l.base.campaign.ballot());
                case "expiry"->l.base.clock.set(BUDGET);
                case "higher"->{var higher=new TreeMap<>(l.base.campaign.ballot());higher.put("counter",number(higher.get("counter"))+1);l.base.peer.observeCurrent(higher);}
                default->throw new AssertionError(mode);
            }
            synchronized(l.base.peer){assertTrue(CompletableFuture.supplyAsync(()->l.endpoint.activationProgress().isEmpty()).get(2,TimeUnit.SECONDS));}
        }
    }
    @Test void idleProgressObservationDoesNotWaitForWriter()throws Exception {
        try(var l=local()) {
            l.endpoint.handle(l.proposer(),l.prepare());var expected=l.endpoint.activationProgress();
            synchronized(l.base.peer){assertEquals(expected,CompletableFuture.supplyAsync(l.endpoint::activationProgress).get(2,TimeUnit.SECONDS));}
        }
    }
    @Test void recreatedEndpointDoesNotInferProgressFromDurableGrant()throws Exception {
        try(var l=local()) {
            l.endpoint.handle(l.proposer(),l.prepare());assertTrue(l.endpoint.activationProgress().isPresent());l.endpoint.close();
            var before=V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory());
            try(var fresh=new MembershipActivationEndpoint(l.base.peer,l.base.peerResources,V53TransferServiceTest.bound(2),
                    (p,r,k,d)->l.link.get().exchange(p,r,k,d),V53ActivationEndpointTest.verifier(),List.of(),List.of(),
                    temp.resolve("fresh-"+UUID.randomUUID()),l.base.clock::get,BUDGET)) {
                assertTrue(fresh.activationProgress().isEmpty());assertTrue(fresh.heartbeatContact().isEmpty());
                assertEquals(before,V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory()));
            }
        }
    }
    @Test void completedGrantPostponesElectionButDoesNotRenewOuterDeadline()throws Exception {
        for(long budget:List.of(20L,100L))try(var l=local()) {
            var draws=new AtomicInteger();
            try(var wait=new MembershipElectionWait(l.base.peer,l.endpoint,l.base.peerResources,POLICY,l.base.clock::get,
                    (a,b)->{draws.incrementAndGet();return a;},0,millis(budget))) {
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try {
                idle(worker);l.base.clock.set(millis(10));l.endpoint.handle(l.proposer(),l.prepare());
                V53MembershipTransportTest.waitFor(()->draws.get()==2);assertFalse(result.isDone());
                l.base.clock.set(millis(budget==20?20:25));
                if(budget==20)assertEquals("election wait closed/original deadline",assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS)).getCause().getMessage());
                else assertEquals(l.base.campaign.ballot(),result.get(5,TimeUnit.SECONDS).ballot());
            }finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());
            }
        }
    }
    @Test void latestOfHeartbeatAndProgressWinsWithoutPollingRenewal()throws Exception {
        for(boolean progressLast:List.of(false,true))try(var l=local();var wait=waitFor(l,100)) {
            l.base.clock.set(millis(10));
            if(progressLast)l.endpoint.handle(l.proposer(),heartbeat(l));else l.endpoint.handle(l.proposer(),l.prepare());
            l.base.clock.set(millis(20));
            if(progressLast)l.endpoint.handle(l.proposer(),l.prepare());else l.endpoint.handle(l.proposer(),heartbeat(l));
            var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();Thread worker=run(wait,result);
            try{idle(worker);l.base.clock.set(millis(35));assertEquals(l.base.campaign.ballot(),result.get(5,TimeUnit.SECONDS).ballot());}
            finally{wait.close();worker.join(5000);}
            assertFalse(worker.isAlive());
        }
    }
    @Test void delayedOlderHeartbeatCannotUndoAnAlreadyConsumedMilestone()throws Exception {
        try(var l=local()) {
            l.endpoint.close();var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            var heartbeatReads=new AtomicInteger();var waitReads=new AtomicInteger();var draws=new AtomicInteger();
            java.util.function.LongSupplier clock=()->{
                long now=l.base.clock.get();String name=Thread.currentThread().getName();
                if(name.equals("delayed-progress-heartbeat") && heartbeatReads.incrementAndGet()==2) {
                    entered.countDown();try{assertTrue(release.await(10,TimeUnit.SECONDS));}
                    catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}
                }
                if(name.equals("milestone-wait"))waitReads.incrementAndGet();return now;
            };
            try(var endpoint=new MembershipActivationEndpoint(l.base.peer,l.base.peerResources,V53TransferServiceTest.bound(2),
                    (p,r,k,d)->l.link.get().exchange(p,r,k,d),V53ActivationEndpointTest.verifier(),List.of(),List.of(),
                    temp.resolve("delayed-"+UUID.randomUUID()),clock,BUDGET);
                var wait=new MembershipElectionWait(l.base.peer,endpoint,l.base.peerResources,POLICY,clock,
                    (a,b)->{draws.incrementAndGet();return a;},0,millis(100))) {
                l.base.clock.set(millis(10));var pulse=heartbeat(l);var replied=new CompletableFuture<Decoded>();
                Thread old=Thread.ofPlatform().name("delayed-progress-heartbeat").start(()->{
                    try{replied.complete(endpoint.handle(l.proposer(),pulse));}catch(Throwable error){replied.completeExceptionally(error);}
                });
                Thread worker=null;
                try {
                    assertTrue(entered.await(5,TimeUnit.SECONDS));l.base.clock.set(millis(20));endpoint.handle(l.proposer(),l.prepare());
                    var result=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();
                    worker=Thread.ofPlatform().name("milestone-wait").start(()->{try{result.complete(wait.await());}catch(Throwable error){result.completeExceptionally(error);}});
                    idle(worker);assertEquals(2,draws.get());release.countDown();assertEquals("HEARTBEAT_ACK",replied.get(5,TimeUnit.SECONDS).kind());
                    assertEquals(millis(10),endpoint.heartbeatContact().orElseThrow().receivedNanos());
                    l.base.clock.set(millis(25));int before=waitReads.get();
                    V53MembershipTransportTest.waitFor(()->waitReads.get()>=before+10 || result.isDone());
                    assertFalse(result.isDone(),"old contact must not expire the newer milestone");assertEquals(2,draws.get());
                    l.base.clock.set(millis(35));assertEquals(l.base.campaign.ballot(),result.get(5,TimeUnit.SECONDS).ballot());
                }finally{release.countDown();wait.close();old.join(5000);if(worker!=null)worker.join(5000);}
                assertFalse(old.isAlive());assertNotNull(worker);assertFalse(worker.isAlive());
            }
        }
    }
}
