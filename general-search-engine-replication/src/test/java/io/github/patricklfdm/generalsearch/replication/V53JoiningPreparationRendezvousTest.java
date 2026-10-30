package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.LongSupplier;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;
import static io.github.patricklfdm.generalsearch.replication.V53JoiningPreparationDiscoveryTest.reject;

/** Conditional files and actual hint read handlers with controlled visibility.
 * This qualifies routing/waiting only, never native initialization authority. */
class V53JoiningPreparationRendezvousTest {
    @TempDir Path temp;
    V53JoiningPreparationDiscoveryTest.Local local(boolean publish)throws Exception {
        var helper=new V53JoiningPreparationDiscoveryTest();helper.temp=temp;return helper.new Local(3,"ADD",publish);
    }
    MembershipJoiningPreparationRendezvous rendezvous(V53JoiningPreparationDiscoveryTest.Local l,LongSupplier clock,int interval)throws IOException {
        return new MembershipJoiningPreparationRendezvous(l.reader,l.pool,V53MembershipTransportTest.bounds(2,interval,FRAME),
                (p,q,k,d)->{l.sent.add(q);return l.link.get().exchange(p,q,k,d);},
                ()->{if(!l.allowed.get())throw new IOException("original preparation revoked");},clock,0,BUDGET);
    }
    @Test void delayedPublicationIsFoundWithoutWritesOrDeadlineRenewal()throws Exception {
        try(var l=local(true)) {
            var before=V53ReplayFilesTest.files(l.readerPath);var usage=l.pool.usage();var calls=new AtomicInteger();
            l.link.set((p,q,k,d)->calls.incrementAndGet()<=3?CompletableFuture.completedFuture(reject(q,"NOT_READY",false)):l.deliver(p,q,k,d));
            long began=System.nanoTime();
            try(var meeting=rendezvous(l,()->System.nanoTime()-began,20)) {
                assertEquals(l.hint,meeting.await());assertThrows(IllegalArgumentException.class,meeting::await);
                assertEquals(List.of("node-1","node-2","node-3","node-1","node-2"),l.destinations().subList(0,5));
                assertEquals(before,V53ReplayFilesTest.files(l.readerPath));assertTrue(l.reader.originalSelection().isEmpty());
            }
            assertEquals(usage,l.pool.usage());
        }
    }
    @Test void exhaustedRouteIsNeverRetriedInLaterAbsencePasses()throws Exception {
        try(var l=local(true)) {
            var second=new AtomicInteger();
            l.link.set((p,q,k,d)->{
                if(p.nodeId().value().equals("node-3"))return CompletableFuture.failedFuture(lost());
                if(p.nodeId().value().equals("node-2") && second.incrementAndGet()==1)return CompletableFuture.completedFuture(reject(q,"NOT_READY",false));
                return l.deliver(p,q,k,d);
            });
            long began=System.nanoTime();
            try(var meeting=rendezvous(l,()->System.nanoTime()-began,20)){assertEquals(l.hint,meeting.await());}
            var lost=l.sent.stream().filter(q->object(q.value().get("recipient")).get("node").equals("node-3")).toList();
            assertEquals(3,lost.size());assertEquals(1,lost.stream().map(Decoded::digest).distinct().count());
        }
    }
    @Test void allUnavailableAndFatalRefusalStopWithoutAnotherPass()throws Exception {
        for(boolean unavailable:List.of(false,true))try(var l=local(false)) {
            l.link.set((p,q,k,d)->unavailable?CompletableFuture.failedFuture(lost()):CompletableFuture.completedFuture(reject(q,"INTEGRITY_FAILURE",false)));
            try(var meeting=rendezvous(l,l.old.clock::get,20)){assertThrows(IOException.class,meeting::await);}
            assertEquals(unavailable?9:1,l.sent.size());
        }
    }
    @Test void deadlineAndGuardCannotBeResetByAnotherPass()throws Exception {
        for(boolean expiry:List.of(false,true))try(var l=local(false)) {
            var calls=new AtomicInteger();
            l.link.set((p,q,k,d)->{if(calls.incrementAndGet()==3){if(expiry)l.old.clock.set(BUDGET);else l.allowed.set(false);}
                return CompletableFuture.completedFuture(reject(q,"NOT_READY",false));});
            try(var meeting=rendezvous(l,l.old.clock::get,20)){assertThrows(Exception.class,meeting::await);}
            assertEquals(3,l.sent.size());
        }
    }
    @Test void closeWakesAbsenceDelayAndReturnsAllReservations()throws Exception {
        try(var l=local(false)) {
            var usage=l.pool.usage();var scanned=new CountDownLatch(1);var count=new AtomicInteger();
            l.link.set((p,q,k,d)->{var reply=reject(q,"NOT_READY",false);if(count.incrementAndGet()==3)scanned.countDown();return CompletableFuture.completedFuture(reply);});
            try(var meeting=rendezvous(l,l.old.clock::get,10_000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
                var result=threads.submit(meeting::await);assertTrue(scanned.await(5,TimeUnit.SECONDS));meeting.close();
                assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS));assertEquals(3,l.sent.size());
            }
            assertEquals(usage,l.pool.usage());
        }
    }
    @Test void closeCancelsAnActiveReadAndDrainsBeforeReturningItsCharge()throws Exception {
        try(var l=local(true)) {
            var usage=l.pool.usage();var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            l.link.set((p,q,k,d)->{entered.countDown();return pending;});
            try(var meeting=rendezvous(l,l.old.clock::get,10_000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
                var result=threads.submit(meeting::await);assertTrue(entered.await(5,TimeUnit.SECONDS));meeting.close();
                assertTrue(pending.isCancelled());assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS));
            }
            assertEquals(usage,l.pool.usage());
        }
    }
}
