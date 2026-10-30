package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/** Fake probes carry no completion authority; these tests qualify scheduling,
 * cancellation/drain and the unrenewed outer deadline only. */
class V53CompletionWaitTest {
    @Test void onlyAbsencePollsAndSuccessClosesPreparationBeforeReturning()throws Exception {
        var order=new ArrayList<String>();var count=new AtomicInteger();
        try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
            public boolean initialized(){order.add("probe");return count.incrementAndGet()==3;}
            public void close(){order.add("closed");}
        },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(10),1,1000)) {
            wait.run();assertEquals(List.of("probe","probe","probe","closed"),order);assertThrows(IllegalArgumentException.class,wait::run);
        }
    }
    @Test void failuresPropagateWithoutPollingAgain()throws Exception {
        for(var failure:List.of(new IOException("unavailable after finite retries"),new IllegalArgumentException("corruption"))) {
            var calls=new AtomicInteger();var closes=new AtomicInteger();
            try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
                public boolean initialized()throws IOException{calls.incrementAndGet();if(failure instanceof IOException io)throw io;throw (RuntimeException)failure;}
                public void close(){closes.incrementAndGet();}
            },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(10),1,1000)) {
                assertSame(failure,assertThrows(Exception.class,wait::run));assertEquals(1,calls.get());assertEquals(1,closes.get());
            }
        }
    }
    @Test void absenceAndLateSuccessCannotRenewOriginalDeadline()throws Exception {
        for(boolean ready:List.of(false,true)) {
            var clock=new AtomicLong();var calls=new AtomicInteger();
            try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
                public boolean initialized(){calls.incrementAndGet();clock.set(100);return ready;}
                public void close(){}
            },()->{},clock::get,0,100,1,1000)) {assertThrows(IllegalArgumentException.class,wait::run);assertEquals(1,calls.get());}
        }
    }
    @Test void closeWakesAnAbsenceWaitAndDrainsBeforeReturning()throws Exception {
        var seen=new CountDownLatch(1);var closed=new AtomicBoolean();var calls=new AtomicInteger();
        try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
            public boolean initialized(){calls.incrementAndGet();seen.countDown();return false;}
            public void close(){closed.set(true);}
        },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(20),10_000,1000);
                var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var worker=executor.submit(()->{wait.run();return null;});assertTrue(seen.await(5,TimeUnit.SECONDS));wait.close();
            assertThrows(ExecutionException.class,()->worker.get(5,TimeUnit.SECONDS));assertTrue(closed.get());assertEquals(1,calls.get());
        }
    }
    @Test void closeCancelsActiveProbeWithoutInterruptingItsWorker()throws Exception {
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var interrupted=new AtomicBoolean();
        try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
            public boolean initialized()throws IOException{entered.countDown();try{release.await();}catch(InterruptedException e){interrupted.set(true);throw new IOException(e);}return true;}
            public void close(){release.countDown();}
        },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(20),1,1000);
                var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var worker=executor.submit(()->{wait.run();return null;});assertTrue(entered.await(5,TimeUnit.SECONDS));wait.close();
            assertThrows(ExecutionException.class,()->worker.get(5,TimeUnit.SECONDS));assertFalse(interrupted.get());
        }
    }
    @Test void preparationCloseFailureStopsHandoffAndCanBeCleanedAgain()throws Exception {
        var fail=new AtomicBoolean(true);var closes=new AtomicInteger();
        try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
            public boolean initialized(){return true;}
            public void close()throws IOException{closes.incrementAndGet();if(fail.get())throw new IOException("cleanup blocked");}
        },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(10),1,1000)) {
            assertThrows(IOException.class,wait::run);assertEquals(1,closes.get());fail.set(false);wait.close();assertTrue(closes.get()>1);
        }
    }
    @Test void guardFailureAndClosedBeforeRunNeverProbe()throws Exception {
        for(boolean close:List.of(false,true)) {
            var calls=new AtomicInteger();
            try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
                public boolean initialized(){calls.incrementAndGet();return true;}public void close(){}
            },()->{if(!close)throw new IOException("fenced");},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(10),1,1000)) {
                if(close)wait.close();assertThrows(Exception.class,wait::run);assertEquals(0,calls.get());
            }
        }
    }
    @Test void preparationDrainCannotConsumeDeadlineAndStillHandOff()throws Exception {
        var clock=new AtomicLong();var closes=new AtomicInteger();
        try(var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
            public boolean initialized(){return true;}
            public void close(){closes.incrementAndGet();clock.set(100);}
        },()->{},clock::get,0,100,1,1000)) {
            assertThrows(IllegalArgumentException.class,wait::run);assertEquals(1,closes.get());
        }
    }
}
