package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.LongSupplier;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.Decoded;

/** Real admitted calls, original scope locks and a writer-held channel. */
class V53ActivationCloseDrainTest {
    @TempDir Path temp;
    static final class Gate implements AutoCloseable {
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1),interrupted=new CountDownLatch(1);
        void stop() {
            entered.countDown();boolean restore=false;
            for(;;)try{assertTrue(release.await(30,TimeUnit.SECONDS),"activation gate expired");break;}
            catch(InterruptedException error){restore=true;interrupted.countDown();}
            if(restore)Thread.currentThread().interrupt();
        }
        void reached()throws Exception {assertTrue(entered.await(10,TimeUnit.SECONDS),"activation call did not reach gate");}
        public void close(){release.countDown();}
    }
    static MembershipActivationEndpoint endpoint(V53ActivationEndpointTest.Local local,Path scratch,LongSupplier clock,boolean leader)throws Exception {
        return new MembershipActivationEndpoint(leader?local.base.leader:local.base.peer,
                leader?local.base.leaderResources:local.base.peerResources,V53VotingCloseFailureTest.shortClose(),
                (p,r,k,d)->local.link.get().exchange(p,r,k,d),V53ActivationEndpointTest.verifier(),List.of(),List.of(),scratch,clock,BUDGET);
    }
    static Decoded discovery(V53ActivationEndpointTest.Local local) throws Exception {
        return MembershipActivation.frame("STATUS_PROBE",local.base.peer.activationContext(),local.proposer(),local.base.identity(),
                local.base.campaign.ballot(),UUID.randomUUID(),1,Map.of("nonce",UUID.randomUUID().toString()));
    }
    static void locked(Path scratch) {
        assertThrows(ReplicationException.class,()->MembershipOwnership.own(scratch.resolve("scope.lock"),false));
    }
    static void unlocked(Path scratch)throws Exception {
        try(var lock=MembershipOwnership.own(scratch.resolve("scope.lock"),false)){assertTrue(lock.lock().isValid());}
    }

    @ParameterizedTest @ValueSource(strings={"direct","control","registration"})
    void admittedCallsKeepScratchOwnedUntilTheirReturn(String kind)throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var gate=new Gate();var executor=Executors.newSingleThreadExecutor()) {
            local.endpoint.close();Path scratch=temp.resolve("drain-"+kind);
            var holder=new AtomicReference<MembershipActivationEndpoint>();var reads=new AtomicInteger();
            LongSupplier clock=()->{
                if(Thread.currentThread().getName().equals("test-admitted-activation")) {
                    int read=reads.incrementAndGet();var endpoint=holder.get();
                    boolean stop=switch(kind) {
                        case "direct" -> read==2;
                        case "control" -> endpoint.usage().waiters()>0 && !endpoint.usage().controlRunning();
                        default -> read==1;
                    };
                    if(stop)gate.stop();
                }
                return 0;
            };
            try(var endpoint=endpoint(local,scratch,clock,kind.equals("registration"))) {
                holder.set(endpoint);var request=kind.equals("control")?local.prepare():discovery(local);
                var call=executor.submit(()->{
                    Thread.currentThread().setName("test-admitted-activation");
                    assertThrows(Exception.class,()->{if(kind.equals("registration"))endpoint.serve(local.base.campaign);
                        else endpoint.handle(local.proposer(),request);});
                });
                try {
                    gate.reached();locked(scratch);
                    var failure=assertThrows(IOException.class,endpoint::close);
                    assertTrue(V53SlotCloseDrainTest.contains(failure,"activation caller close timeout"));locked(scratch);
                    assertThrows(IllegalArgumentException.class,()->endpoint.handle(local.proposer(),request));
                }finally{gate.close();call.get(10,TimeUnit.SECONDS);endpoint.close();}
                unlocked(scratch);
            }
        }
    }

    @Test void timeoutDoesNotInterruptAControlStillOwningItsChannel()throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var gate=new Gate();var executor=Executors.newSingleThreadExecutor()) {
            local.endpoint.close();Path scratch=temp.resolve("writer-timeout");
            var forced=new AtomicBoolean();var failure=new AtomicReference<Throwable>();
            local.link.set((p,r,k,d)->{
                Path file=scratch.resolve("source-held");
                try(var channel=FileChannel.open(file,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
                    gate.stop();channel.write(ByteBuffer.wrap(new byte[]{1,2,3}));channel.force(true);forced.set(true);
                    return CompletableFuture.failedFuture(new IOException("released original control"));
                }catch(Throwable error){failure.set(error);return CompletableFuture.failedFuture(error);}
                finally{try{Files.deleteIfExists(file);}catch(IOException error){failure.compareAndSet(null,error);}}
            });
            try(var endpoint=endpoint(local,scratch,()->0,false)) {
                var request=local.prepare();var call=executor.submit(()->assertThrows(Exception.class,()->endpoint.handle(local.proposer(),request)));
                try {
                    gate.reached();assertThrows(IOException.class,endpoint::close);locked(scratch);
                    assertFalse(gate.interrupted.await(200,TimeUnit.MILLISECONDS),"timeout must retain ownership without interrupting its writer");
                }finally{gate.close();call.get(10,TimeUnit.SECONDS);endpoint.close();}
                assertNull(failure.get());assertTrue(forced.get());unlocked(scratch);
            }
        }
    }

    @Test void interruptedCloseKeepsAdmittedCallerAndLockForAnExternalRetry()throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var gate=new Gate();var executor=Executors.newSingleThreadExecutor()) {
            local.endpoint.close();Path scratch=temp.resolve("interrupted-caller");var reads=new AtomicInteger();
            LongSupplier clock=()->{if(Thread.currentThread().getName().equals("test-interrupted-caller") && reads.incrementAndGet()==2)gate.stop();return 0;};
            try(var endpoint=endpoint(local,scratch,clock,false)) {
                var request=discovery(local);var call=executor.submit(()->{Thread.currentThread().setName("test-interrupted-caller");
                    assertThrows(Exception.class,()->endpoint.handle(local.proposer(),request));});
                try {
                    gate.reached();var failure=V53SlotCloseDrainTest.interruptedClose(endpoint);
                    assertTrue(V53SlotCloseDrainTest.contains(failure,"activation caller close interrupted"));locked(scratch);
                    assertThrows(IOException.class,endpoint::close);locked(scratch);
                }finally{gate.close();call.get(10,TimeUnit.SECONDS);endpoint.close();}
                unlocked(scratch);
            }
        }
    }

    @Test void higherPrepareFencesBeforeWaitingForAnOldControlRegistry()throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var gate=new Gate();var executor=Executors.newFixedThreadPool(2)) {
            local.endpoint.close();var once=new AtomicBoolean();
            LongSupplier clock=()->{
                if(Thread.currentThread().getName().startsWith("gse-membership-control-") &&
                        StackWalker.getInstance().walk(frames->frames.anyMatch(frame->frame.getMethodName().equals("progressed"))) &&
                        once.compareAndSet(false,true))gate.stop();
                return 0;
            };
            try(var endpoint=endpoint(local,temp.resolve("early-fence"),clock,false)) {
                var request=local.prepare();var first=executor.submit(()->assertThrows(Exception.class,()->endpoint.handle(local.proposer(),request)));
                Future<?> higher=null;
                try {
                    gate.reached();var changed=new TreeMap<>(request.value());
                    var ballot=new TreeMap<>(MembershipFormat.object(request.value().get("ballot")));
                    ballot.put("counter",MembershipFormat.number(ballot.get("counter"))+1);changed.put("ballot",ballot);
                    var next=MembershipFormat.decode(MembershipFormat.encode("wire","PREPARE",changed),"wire","PREPARE");
                    higher=executor.submit(()->{try{endpoint.handle(local.proposer(),next);}catch(IOException|IllegalArgumentException expected){/* revoked original source */}});
                    V53MembershipTransportTest.waitFor(()->{
                        try{local.base.peer.checkCampaignWait((String)request.value().get("view"),local.base.campaign.ballot());return false;}
                        catch(MembershipCampaignLost lost){return lost.reason==MembershipCampaignLost.Reason.HIGHER_BALLOT;}
                    });
                    assertFalse(higher.isDone(),"the higher PREPARE still waits for old registry admission after fencing");
                }finally{gate.close();first.get(10,TimeUnit.SECONDS);if(higher!=null)higher.get(10,TimeUnit.SECONDS);}
            }
        }
    }

    @ParameterizedTest @ValueSource(strings={"caller","control","expiry"})
    void ownedCallbackCannotDeclareItsOwnDrainComplete(String kind)throws Exception {
        var helper=new V53ActivationEndpointTest();helper.temp=temp;
        try(var local=helper.new Local();var executor=Executors.newSingleThreadExecutor()) {
            local.endpoint.close();Path scratch=temp.resolve("self-"+kind);
            var holder=new AtomicReference<MembershipActivationEndpoint>();var once=new AtomicBoolean();var enabled=new AtomicBoolean();
            var failure=new AtomicReference<Throwable>();var retained=new AtomicBoolean();var attempted=new CountDownLatch(1);
            LongSupplier clock=()->{
                String name=Thread.currentThread().getName();boolean selected=switch(kind) {
                    case "caller" -> name.equals("test-self-activation");
                    case "control" -> name.startsWith("gse-membership-control-");
                    default -> name.startsWith("gse-membership-expiry-");
                };
                if(enabled.get() && selected && once.compareAndSet(false,true)) {
                    try{holder.get().close();}catch(Throwable error){failure.set(error);}
                    try(var available=MembershipOwnership.own(scratch.resolve("scope.lock"),false)){retained.set(false);}
                    catch(ReplicationException expected){retained.set(true);}
                    catch(Exception error){failure.set(error);}
                    attempted.countDown();
                }
                return 0;
            };
            try(var endpoint=endpoint(local,scratch,clock,kind.equals("expiry"))) {
                holder.set(endpoint);
                if(kind.equals("expiry")){endpoint.serve(local.base.campaign);enabled.set(true);}
                else {
                    var request=kind.equals("control")?local.prepare():discovery(local);enabled.set(true);
                    executor.submit(()->{Thread.currentThread().setName("test-self-activation");
                        assertThrows(Exception.class,()->endpoint.handle(local.proposer(),request));}).get(10,TimeUnit.SECONDS);
                }
                assertTrue(attempted.await(10,TimeUnit.SECONDS));
                assertInstanceOf(IOException.class,failure.get());assertEquals("activation close from active callback",failure.get().getMessage());
                assertTrue(retained.get(),"self close must retain original scratch ownership");endpoint.close();unlocked(scratch);
            }
        }
    }
}
