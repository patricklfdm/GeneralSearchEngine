package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.resources;

/** Cancellation/ownership scheduling only. Fake actions have no native force
 * authority; the production adapter must still acquire its live original owner. */
class V53InitializationTaskTest {
    static void await(CountDownLatch latch)throws IOException {
        try{if(!latch.await(5,TimeUnit.SECONDS))throw new IOException("test latch timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("test worker interrupted",error);}
    }
    static final class Action implements MembershipInitializationTask.Action {
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1),cancelled=new CountDownLatch(1);
        final MembershipResources.Lease charge;
        final boolean force;
        boolean closed,active;final AtomicBoolean interrupted=new AtomicBoolean();
        Action(MembershipResources pool,boolean force){this.force=force;charge=pool.reserve(MembershipResources.Unit.CONTROL,UUID.randomUUID().toString(),1024);}
        @Override public void run()throws IOException {
            synchronized(this){if(closed)throw new IOException("action closed");active=true;}
            try {entered.countDown();await(release);interrupted.set(Thread.currentThread().isInterrupted());
                synchronized(this){if(closed && !force)throw new IOException("cancelled pending read");}
            }finally{synchronized(this){active=false;if(closed)charge.close();}}
        }
        @Override public synchronized void close(){closed=true;cancelled.countDown();if(!force)release.countDown();if(!active)charge.close();}
    }
    @Test void closeCancelsPendingReadAndDrainsBeforeReturning()throws Exception {
        var pool=resources();var action=new Action(pool,false);
        try(var task=new MembershipInitializationTask(2000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var run=threads.submit(()->{task.execute(()->action);return null;});assertTrue(action.entered.await(5,TimeUnit.SECONDS));
            task.close();assertThrows(ExecutionException.class,()->run.get(5,TimeUnit.SECONDS));assertFalse(action.interrupted.get());
            assertEquals(0,pool.usage().leases());assertThrows(IllegalArgumentException.class,()->task.execute(()->action));
        }
    }
    @Test void admittedForceKeepsChargeAndIsNeverInterruptedByClose()throws Exception {
        var pool=resources();var action=new Action(pool,true);
        try(var task=new MembershipInitializationTask(2000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var run=threads.submit(()->{task.execute(()->action);return null;});assertTrue(action.entered.await(5,TimeUnit.SECONDS));
            var close=threads.submit(()->{task.close();return null;});
            try {assertTrue(action.cancelled.await(5,TimeUnit.SECONDS));assertFalse(close.isDone());assertFalse(run.isDone());assertEquals(1,pool.usage().leases());}
            finally{action.release.countDown();}
            run.get(5,TimeUnit.SECONDS);close.get(5,TimeUnit.SECONDS);assertFalse(action.interrupted.get());assertEquals(0,pool.usage().leases());
        }
    }
    @Test void drainTimeoutRetainsForceOwnerUntilExplicitCloseRetry()throws Exception {
        var pool=resources();var action=new Action(pool,true);
        try(var task=new MembershipInitializationTask(30);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var run=threads.submit(()->{task.execute(()->action);return null;});assertTrue(action.entered.await(5,TimeUnit.SECONDS));
            try {assertThrows(IllegalArgumentException.class,task::close);assertEquals(1,pool.usage().leases());assertFalse(run.isDone());}
            finally{action.release.countDown();}
            run.get(5,TimeUnit.SECONDS);task.close();assertFalse(action.interrupted.get());assertEquals(0,pool.usage().leases());
        }
    }
    @Test void closeDuringFactoryRejectsAndClosesTheLateActionBeforeItRuns()throws Exception {
        var pool=resources();var action=new Action(pool,true);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var task=new MembershipInitializationTask(30);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var run=threads.submit(()->{task.execute(()->{entered.countDown();await(release);return action;});return null;});
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            try{assertThrows(IllegalArgumentException.class,task::close);assertEquals(1,pool.usage().leases());}finally{release.countDown();}
            assertThrows(ExecutionException.class,()->run.get(5,TimeUnit.SECONDS));assertEquals(1,action.entered.getCount());
            task.close();assertEquals(0,pool.usage().leases());
        }
    }
    @Test void duplicateTaskCannotEnterFactoryOrCancelTheFirstRun()throws Exception {
        var pool=resources();var action=new Action(pool,true);
        try(var task=new MembershipInitializationTask(2000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var run=threads.submit(()->{task.execute(()->action);return null;});assertTrue(action.entered.await(5,TimeUnit.SECONDS));
            try {assertThrows(IllegalArgumentException.class,()->task.execute(()->{throw new AssertionError("duplicate factory");}));
                assertEquals(1,action.cancelled.getCount());assertFalse(run.isDone());}
            finally{action.release.countDown();}
            run.get(5,TimeUnit.SECONDS);assertEquals(0,pool.usage().leases());
        }
    }
    @Test void factoryAndCleanupFailuresRetainOriginalErrorAndRetryableAction()throws Exception {
        var attempts=new AtomicInteger();var original=new IOException("initialization failed");
        try(var task=new MembershipInitializationTask(2000)) {
            var error=assertThrows(IOException.class,()->task.execute(()->new MembershipInitializationTask.Action(){
                @Override public void run()throws IOException{throw original;}
                @Override public void close()throws IOException{if(attempts.getAndIncrement()==0)throw new IOException("cleanup failed");}
            }));
            assertSame(original,error);assertEquals("cleanup failed",error.getSuppressed()[0].getMessage());task.close();assertTrue(attempts.get()>1);
        }
        try(var task=new MembershipInitializationTask(2000)) {
            assertThrows(IOException.class,()->task.execute(()->{throw new IOException("factory failed");}));
            task.close();assertThrows(IllegalArgumentException.class,()->task.execute(()->{throw new AssertionError("reopened");}));
        }
    }
}
