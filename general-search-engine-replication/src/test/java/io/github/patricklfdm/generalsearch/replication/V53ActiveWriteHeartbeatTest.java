package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Native stable-slot scheduling; these deliberately held replies are not
 * whole competing-candidate history qualification or a failover SLA. */
class V53ActiveWriteHeartbeatTest {
    @TempDir Path temp;
    @Test void heldAcceptStillSendsHeartbeatThenCompletesTheOnlyData()throws Exception {run("complete");}
    @Test void higherHeartbeatResponseStopsHeldDataWithoutReplay()throws Exception {run("higher");}
    @Test void closeCancelsHeartbeatAndHeldDataWithoutSuccess()throws Exception {run("close");}
    @Test void heldPublicationStillSendsHeartbeatBeforeLocalCompletion()throws Exception {run("publish");}
    private void run(String mode)throws Exception {
        boolean higher=mode.equals("higher"),closing=mode.equals("close");
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE);
                var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var policy=AutomaticLeadershipPolicy.forBounds(n.bounds);
            var session=round.automaticSession(policy);
            session.start(System.nanoTime()+n.offset.get());
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var sent=new CountDownLatch(1);
            var heartbeatHeld=new CountDownLatch(1);
            var held=new AtomicBoolean();var heartbeat=new AtomicReference<Decoded>();
            n.response.set((request,reply)->{
                if(request.kind().equals(mode.equals("publish")?"PUBLISH":"ACCEPT") && held.compareAndSet(false,true)) {
                    entered.countDown();
                    try{if(!release.await(30,TimeUnit.SECONDS))throw new IllegalArgumentException("test release missing");}
                    catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalArgumentException(error);}
                }
                if(closing && held.get() && request.kind().equals("HEARTBEAT")) {
                    heartbeatHeld.countDown();
                    try{if(!release.await(30,TimeUnit.SECONDS))throw new IllegalArgumentException("heartbeat release missing");}
                    catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalArgumentException(error);}
                }
                if(higher && held.get() && request.kind().equals("HEARTBEAT"))return V53ActivationDriverTest.reject(request,"STALE_EPOCH",true,false);
                return reply;
            });
            n.beforeSend.set(request->{if(held.get() && request.kind().equals("HEARTBEAT")) {heartbeat.compareAndSet(null,request);sent.countDown();}});
            var data=helper.data(n);var call=executor.submit(()->session.submit("DATA",data));
            try {
                assertTrue(entered.await(60,TimeUnit.SECONDS),"no actual held original response");
                n.offset.addAndGet(TimeUnit.MILLISECONDS.toNanos(policy.heartbeatIntervalMillis()));
                assertTrue(sent.await(10,TimeUnit.SECONDS),"due heartbeat was blocked behind DATA");
                if(!higher)assertFalse(call.isDone(),"DATA unexpectedly completed before its original ACCEPT response");
                var advertised=object(heartbeat.get().value().get("payload"));assertEquals(true,advertised.get("activated"));
                assertEquals(1L,object(advertised.get("cut")).get("index"));
                assertEquals(n.ballot,heartbeat.get().value().get("ballot"));
                if(closing) {
                    assertTrue(heartbeatHeld.await(10,TimeUnit.SECONDS));round.close();
                    assertThrows(ExecutionException.class,()->call.get(10,TimeUnit.SECONDS));
                    assertEquals(MembershipRoundDriver.State.CLOSED,round.state());
                    assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
                }else if(higher) {
                    var error=assertThrows(ExecutionException.class,()->call.get(30,TimeUnit.SECONDS));
                    assertInstanceOf(MembershipCampaignLost.class,error.getCause());
                    assertEquals(MembershipRoundDriver.State.FAILED,round.state());
                    assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
                }else {
                    release.countDown();assertEquals("PUBLISH_ACK",call.get(60,TimeUnit.SECONDS).kind());round.readiness();
                    assertEquals(2L,n.owners.getFirst().activationContext().cut.get("index"));
                }
                // A fixed single DATA, including any identical transport retries.
                assertEquals(1,n.events.stream().filter(e->e.get("event").equals("SLOT_BEGIN") && Long.valueOf(2).equals(e.get("index"))).count());
            }finally{release.countDown();}
        }
    }
}
