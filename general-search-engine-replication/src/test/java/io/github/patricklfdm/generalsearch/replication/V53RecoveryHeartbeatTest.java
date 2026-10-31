package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** A selected proposer is live while recovering; it is not yet service-ready.
 * Held native replies test scheduling, not a latency or failover SLA. */
class V53RecoveryHeartbeatTest {
    @TempDir Path temp;
    @Test void heldInitialBarrierStillSendsHeartbeatWithoutAdvertisingReadiness()throws Exception {run("complete");}
    @Test void higherHeartbeatStopsRecoveryBeforeReady()throws Exception {run("higher");}
    @Test void closingRecoveryCancelsHeartbeatWithoutReady()throws Exception {run("close");}
    @Test void rejectedInstallationCannotSendActivatedHeartbeat()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            var pulses=new AtomicInteger();n.beforeSend.set(request->{if(request.kind().equals("HEARTBEAT"))pulses.incrementAndGet();});
            n.response.set((request,reply)->request.kind().equals("SELECTED")?
                V53ActivationDriverTest.reject(request,"STALE_EPOCH",true,false):reply);
            var session=round.automaticSession(AutomaticLeadershipPolicy.forBounds(n.bounds));
            assertThrows(MembershipCampaignLost.class,()->session.start(System.nanoTime()));
            assertEquals(0,pulses.get());assertEquals(MembershipRoundDriver.State.FAILED,round.state());
            assertThrows(IllegalArgumentException.class,round::readiness);
        }
    }
    private void run(String mode)throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE);
                var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var policy=AutomaticLeadershipPolicy.forBounds(n.bounds);var session=round.automaticSession(policy);
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var sent=new CountDownLatch(1);var heartbeatHeld=new CountDownLatch(1);
            var held=new AtomicBoolean();var heartbeat=new AtomicReference<Decoded>();var initialPulses=new AtomicInteger();
            n.response.set((request,reply)->{
                if(request.kind().equals("ACCEPT") && held.compareAndSet(false,true)) {
                    entered.countDown();hold(release);
                }
                if(held.get() && request.kind().equals("HEARTBEAT")) {
                    if(mode.equals("close")){heartbeatHeld.countDown();hold(release);}
                    if(mode.equals("higher"))return V53ActivationDriverTest.reject(request,"STALE_EPOCH",true,false);
                }
                return reply;
            });
            n.beforeSend.set(request->{if(request.kind().equals("HEARTBEAT")) {
                if(held.get()){heartbeat.compareAndSet(null,request);sent.countDown();}else initialPulses.incrementAndGet();
            }});
            var call=executor.submit(()->session.start(System.nanoTime()+n.offset.get()));
            try {
                assertTrue(entered.await(60,TimeUnit.SECONDS),"missing actual held first BARRIER ACCEPT");
                n.offset.addAndGet(TimeUnit.MILLISECONDS.toNanos(policy.heartbeatIntervalMillis()));
                assertTrue(sent.await(10,TimeUnit.SECONDS),"due heartbeat blocked behind initial recovery BARRIER");
                assertTrue(initialPulses.get()>0,"no immediate installed-campaign heartbeat");
                var advertised=object(heartbeat.get().value().get("payload"));assertEquals(true,advertised.get("activated"));
                assertEquals(0L,object(advertised.get("cut")).get("index"));assertEquals(n.ballot,heartbeat.get().value().get("ballot"));
                assertThrows(IllegalArgumentException.class,round::readiness);
                assertTrue(n.events.stream().noneMatch(e->e.get("event").equals("ROUND_BEFORE_READY")));
                if(mode.equals("close")) {
                    assertTrue(heartbeatHeld.await(10,TimeUnit.SECONDS));round.close();
                    assertThrows(ExecutionException.class,()->call.get(10,TimeUnit.SECONDS));
                    assertEquals(MembershipRoundDriver.State.CLOSED,round.state());
                }else if(mode.equals("higher")) {
                    assertInstanceOf(MembershipCampaignLost.class,assertThrows(ExecutionException.class,()->call.get(30,TimeUnit.SECONDS)).getCause());
                    assertEquals(MembershipRoundDriver.State.FAILED,round.state());
                }else {
                    assertFalse(call.isDone());release.countDown();assertEquals("PUBLISH_ACK",call.get(60,TimeUnit.SECONDS).kind());
                    assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));round.readiness();
                }
                assertEquals(1,n.events.stream().filter(e->e.get("event").equals("SLOT_BEGIN") && Long.valueOf(1).equals(e.get("index"))).count());
            }finally{release.countDown();}
        }
    }
    static void hold(CountDownLatch release) {
        try{if(!release.await(30,TimeUnit.SECONDS))throw new IllegalArgumentException("test release missing");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalArgumentException(error);}
    }
}
