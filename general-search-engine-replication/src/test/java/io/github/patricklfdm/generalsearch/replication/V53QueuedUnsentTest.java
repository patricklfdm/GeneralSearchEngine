package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53MembershipTransportTest.*;

/** Delay only fixture worker dispatch; production deadlines/cancellation remain untouched. */
class V53QueuedUnsentTest {
    @TempDir Path temp;
    private static final class Paused extends AbstractExecutorService {
        final ExecutorService delegate;
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        Paused(ExecutorService delegate){this.delegate=delegate;}
        @Override public void execute(Runnable task) {
            delegate.execute(()->{entered.countDown();try{release.await();}catch(InterruptedException error){Thread.currentThread().interrupt();}task.run();});
        }
        @Override public void shutdown(){delegate.shutdown();}
        @Override public List<Runnable> shutdownNow(){return delegate.shutdownNow();}
        @Override public boolean isShutdown(){return delegate.isShutdown();}
        @Override public boolean isTerminated(){return delegate.isTerminated();}
        @Override public boolean awaitTermination(long time,TimeUnit unit)throws InterruptedException{return delegate.awaitTermination(time,unit);}
    }
    private static Paused pause(MembershipTransport transport)throws Exception {
        var field=MembershipTransport.class.getDeclaredField("workers");field.setAccessible(true);
        var paused=new Paused((ExecutorService)field.get(transport));field.set(transport,paused);return paused;
    }
    @Test void queuedCancellationDeadlineAndCloseReleaseBeforeUnsentObservation()throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;
        for(String mode:List.of("cancel","deadline","close"))try(var group=helper.new Group(3)) {
            var budget=resources(MembershipResources.QUEUE_LIMIT);var reason=new AtomicReference<MembershipTransport.Reason>();
            var observed=new CountDownLatch(1);var callbacks=new AtomicInteger();
            var client=group.start(0,group::status,new MembershipTransport.Events() {
                @Override public void at(String event,Decoded request,Decoded response){fail("queued request reached a connected boundary");}
                @Override public void unsent(Decoded request,UUID invocation,MembershipTransport.Reason failure) {
                    assertEquals(0,budget.usage().leases());assertNotEquals(new UUID(0,0),invocation);
                    reason.set(failure);callbacks.incrementAndGet();observed.countDown();
                }
            },bounds(1,5000,FRAME),budget);
            var paused=pause(client);var request=group.request(0,1);long originalDeadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(1);
            try {
                var pending=client.exchange(group.identities.get(1),request,"STATUS",mode.equals("deadline")?originalDeadline:deadline());
                await(paused.entered);assertEquals(request.size(),budget.usage().queued());assertEquals(1,client.usage().outgoing());
                if(mode.equals("cancel")) {
                    assertTrue(pending.cancel(true));assertEquals(request.size(),budget.usage().queued());
                    assertEquals(MembershipTransport.Reason.CAPACITY,failure(client.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
                    paused.release.countDown();
                }else if(mode.equals("deadline")) {
                    waitFor(()->System.nanoTime()>originalDeadline);paused.release.countDown();
                    assertEquals(MembershipTransport.Reason.DEADLINE,failure(pending).reason);
                }else {
                    client.close();assertEquals(MembershipTransport.Reason.CLOSED,failure(pending).reason);
                }
                await(observed);assertEquals(1,callbacks.get());assertEquals(0,client.usage().outgoing());
                assertEquals(switch(mode){case "cancel"->MembershipTransport.Reason.IO;case "deadline"->MembershipTransport.Reason.DEADLINE;default->MembershipTransport.Reason.CLOSED;},reason.get());
            }finally{paused.release.countDown();}
        }
    }
}
