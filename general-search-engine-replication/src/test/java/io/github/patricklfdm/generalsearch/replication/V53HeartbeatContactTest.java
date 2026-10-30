package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53HeartbeatTest.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;

class V53HeartbeatContactTest {
    @TempDir Path temp;
    V53ActivationDriverTest.Local local(AtomicLong clock)throws Exception {
        var helper=new V53ActivationDriverTest();helper.temp=temp;return helper.local(clock,1000);
    }
    @Test void onlyAcceptedActivatedHeartbeatRecordsArrivalWithoutDurableWork()throws Exception {
        var clock=new AtomicLong(10);
        try(var l=local(clock)) {
            var endpoint=l.endpoints.getFirst();var peer=l.group.identities.get(1);var before=files(l);var usage=endpoint.usage();
            assertTrue(endpoint.heartbeatContact().isEmpty());l.events.values().forEach(List::clear);
            endpoint.handle(peer,request(l,100,false));assertTrue(endpoint.heartbeatContact().isEmpty());
            var request=request(l,100,true);endpoint.handle(peer,request);var observed=endpoint.heartbeatContact().orElseThrow();
            assertEquals(peer,observed.proposer());assertEquals(request.value().get("root"),observed.root());
            assertEquals(request.value().get("view"),observed.view());assertEquals(request.value().get("ballot"),observed.ballot());
            assertEquals(10,observed.receivedNanos());assertThrows(UnsupportedOperationException.class,()->observed.ballot().put("counter",1L));
            clock.set(20);endpoint.handle(peer,request);assertEquals(20,endpoint.heartbeatContact().orElseThrow().receivedNanos());
            assertEquals(usage,endpoint.usage());assertTrue(usage.scopeEnded());assertEquals(before,files(l));
            assertTrue(l.events.values().stream().allMatch(List::isEmpty));
        }
    }
    @Test void aHigherFenceInvalidatesOldContactEvenWithoutAnotherHeartbeat()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock)) {
            var endpoint=l.endpoints.getFirst();var peer=l.group.identities.get(1);var old=request(l,100,true);
            endpoint.handle(peer,old);var next=new TreeMap<>(object(old.value().get("ballot")));next.put("counter",101L);
            l.owners.getFirst().observeCurrent(next);assertTrue(endpoint.heartbeatContact().isEmpty());
            assertThrows(IllegalArgumentException.class,()->endpoint.handle(peer,old));assertTrue(endpoint.heartbeatContact().isEmpty());
            clock.set(10);endpoint.handle(peer,request(l,101,true));assertEquals(101L,endpoint.heartbeatContact().orElseThrow().ballot().get("counter"));
            clock.set(20);endpoint.handle(peer,request(l,102,false));assertTrue(endpoint.heartbeatContact().isEmpty());
        }
    }
    @Test void foreignTrafficCannotRefreshOrInvalidateAcceptedContact()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock)) {
            var endpoint=l.endpoints.getFirst();var peer=l.group.identities.get(1);endpoint.handle(peer,request(l,100,true));
            var before=endpoint.heartbeatContact();clock.set(50);
            for(String field:List.of("root","view")) {
                var value=new TreeMap<>(request(l,200,true).value());value.put(field,"a".repeat(64));
                var bad=decode(encode("wire","HEARTBEAT",value),"wire","HEARTBEAT");
                assertThrows(IllegalArgumentException.class,()->endpoint.handle(peer,bad));assertEquals(before,endpoint.heartbeatContact());
            }
            assertThrows(IllegalArgumentException.class,()->endpoint.handle(l.group.identities.get(2),request(l,200,true)));
            assertEquals(before,endpoint.heartbeatContact());
        }
    }
    @Test void writerWaitKeepsOriginalArrivalAndExpiredWorkDoesNotRecord()throws Exception {
        for(boolean expire:List.of(false,true)) {
            var clock=new AtomicLong(10);try(var l=local(clock)) {
                var endpoint=l.endpoints.getFirst();var owner=l.owners.getFirst();var request=request(l,100,true);
                var result=new CompletableFuture<Throwable>();Thread worker;
                synchronized(owner) {
                    worker=Thread.ofPlatform().start(()->{try{endpoint.handle(l.group.identities.get(1),request);result.complete(null);}catch(Throwable error){result.complete(error);}});
                    V53MembershipTransportTest.waitFor(()->worker.getState()==Thread.State.BLOCKED);
                    assertTrue(endpoint.heartbeatContact().isEmpty());clock.set(expire?BUDGET+10:100);
                }
                var error=result.get(5,TimeUnit.SECONDS);worker.join(5000);assertFalse(worker.isAlive());
                if(expire){assertNotNull(error);assertTrue(endpoint.heartbeatContact().isEmpty());}
                else{assertNull(error);assertEquals(10,endpoint.heartbeatContact().orElseThrow().receivedNanos());}
            }
        }
    }
    @Test void lateCompletionCannotReplaceNewerArrivalOrHigherBallot()throws Exception {
        delayed(false,false);delayed(true,false);
    }
    @Test void closeCannotBeReversedByDelayedCompletion()throws Exception {
        delayed(false,true);
    }
    private void delayed(boolean higher,boolean close)throws Exception {
        var time=new AtomicLong(10);var blocked=new CountDownLatch(1);var proceed=new CountDownLatch(1);var reads=new AtomicInteger();
        var helper=new V53ActivationDriverTest();helper.temp=temp;
        try(var l=helper.new Local(3,false,Files.createDirectory(temp.resolve("delayed-"+UUID.randomUUID())),()->{
            if(Thread.currentThread().getName().equals("old-heartbeat") && reads.incrementAndGet()==2) {
                blocked.countDown();try{assertTrue(proceed.await(10,TimeUnit.SECONDS));}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}
            }
            return time.get();
        },1000)) {
            var endpoint=l.endpoints.getFirst();var peer=l.group.identities.get(1);var old=request(l,100,true);var result=new CompletableFuture<Throwable>();
            Thread worker=Thread.ofPlatform().name("old-heartbeat").start(()->{try{endpoint.handle(peer,old);result.complete(null);}catch(Throwable error){result.complete(error);}});
            try {
                assertTrue(blocked.await(5,TimeUnit.SECONDS));assertTrue(endpoint.heartbeatContact().isEmpty());time.set(100);
                if(close)endpoint.close();else endpoint.handle(peer,request(l,higher?101:100,true));
            }finally{proceed.countDown();worker.join(5000);}
            assertFalse(worker.isAlive());var error=result.get(1,TimeUnit.SECONDS);
            if(close){assertNotNull(error);assertTrue(endpoint.heartbeatContact().isEmpty());}
            else{assertNull(error);var contact=endpoint.heartbeatContact().orElseThrow();assertEquals(100,contact.receivedNanos());assertEquals(higher?101L:100L,contact.ballot().get("counter"));}
        }
    }
    @Test void endpointRecreationDoesNotRecoverLivenessFromRetainedPromise()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock)) {
            var old=l.endpoints.getFirst();var peer=l.group.identities.get(1);old.handle(peer,request(l,100,true));
            var before=files(l);old.close();assertTrue(old.heartbeatContact().isEmpty());
            var fresh=new MembershipActivationEndpoint(l.owners.getFirst(),l.budgets.getFirst(),l.bound,
                (p,r,k,d)->l.deliver(0,p,r,k,d),V53ActivationEndpointTest.verifier(),List.of(),List.of(),
                temp.resolve("reopened-"+UUID.randomUUID()),clock::get,BUDGET);
            l.endpoints.set(0,fresh);assertTrue(fresh.heartbeatContact().isEmpty());assertEquals(before,files(l));
            fresh.handle(peer,request(l,100,true));assertTrue(fresh.heartbeatContact().isPresent());assertTrue(fresh.usage().scopeEnded());
        }
    }
}
