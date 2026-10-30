package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.resources;

/** Dispatch lifecycle only: the opaque fixture below never grants protocol authority. */
class V53EndpointHandoffTest {
    final MembershipFormat.Decoded marker=new V53ContextFixture(3,"ADD").root;
    final MembershipIdentity peer=V53DeclarationsTest.node(1);
    final class Child implements MembershipEndpointHandoff.Endpoint {
        final CountDownLatch entered=new CountDownLatch(1),released=new CountDownLatch(1),closed=new CountDownLatch(1);
        final AtomicInteger closes=new AtomicInteger();boolean block,failClose;
        @Override public MembershipFormat.Decoded handle(MembershipIdentity peer,MembershipFormat.Decoded request)throws IOException {
            entered.countDown();if(block)try{if(!released.await(5,TimeUnit.SECONDS))throw new IOException("test release timeout");}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}return marker;
        }
        @Override public void close()throws IOException {closed.countDown();if(closes.getAndIncrement()==0 && failClose)throw new IOException("injected close failure");}
    }
    @Test void replacementClosesOriginalBeforeOpeningExactlyOneActiveEndpoint()throws Exception {
        var pool=resources();var original=new Child();var active=new Child();
        try(var gate=new MembershipEndpointHandoff(original,false,pool,2000)) {
            assertSame(marker,gate.handle(peer,marker));
            gate.replace(()->{assertTrue(original.closes.get()>0);assertEquals(MembershipEndpointHandoff.State.SWITCHING,gate.state());
                assertThrows(IllegalArgumentException.class,()->gate.handle(peer,marker));return active;});
            assertEquals(MembershipEndpointHandoff.State.ACTIVE,gate.state());assertSame(marker,gate.handle(peer,marker));
            assertThrows(IllegalArgumentException.class,()->gate.replace(()->{throw new AssertionError("second factory");}));
        }
        assertTrue(active.closes.get()>0);assertEquals(0,pool.usage().leases());
    }
    @Test void inFlightOldCallMustExitBeforeFactoryAndCannotReturnAfterSwitch()throws Exception {
        var pool=resources();var original=new Child();original.block=true;var factory=new AtomicBoolean();
        try(var gate=new MembershipEndpointHandoff(original,false,pool,2000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var call=threads.submit(()->gate.handle(peer,marker));assertTrue(original.entered.await(5,TimeUnit.SECONDS));
            var change=threads.submit(()->{gate.replace(()->{factory.set(true);return new Child();});return null;});
            try {assertTrue(original.closed.await(5,TimeUnit.SECONDS));assertFalse(factory.get());assertFalse(change.isDone());
                assertThrows(IllegalArgumentException.class,()->gate.handle(peer,marker));assertTrue(pool.usage().leases()>0);
            }finally{original.released.countDown();}
            assertThrows(ExecutionException.class,()->call.get(5,TimeUnit.SECONDS));change.get(5,TimeUnit.SECONDS);assertTrue(factory.get());
        }
        assertEquals(0,pool.usage().leases());
    }
    @Test void failedDrainRetainsOwnershipUntilOutstandingCallActuallyExits()throws Exception {
        var pool=resources();var original=new Child();original.block=true;
        try(var gate=new MembershipEndpointHandoff(original,false,pool,30);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var call=threads.submit(()->gate.handle(peer,marker));assertTrue(original.entered.await(5,TimeUnit.SECONDS));
            try {assertThrows(IllegalArgumentException.class,()->gate.replace(()->{throw new AssertionError("factory before drain");}));
                assertEquals(MembershipEndpointHandoff.State.FAILED,gate.state());assertThrows(IllegalArgumentException.class,gate::close);
                assertEquals(1,pool.usage().leases());assertThrows(IllegalArgumentException.class,()->gate.handle(peer,marker));
            }finally{original.released.countDown();}
            assertThrows(ExecutionException.class,()->call.get(5,TimeUnit.SECONDS));gate.close();
        }
        assertEquals(0,pool.usage().leases());
    }
    @Test void closingWhileFactoryRunsNeverPublishesOrLeaksItsReturnedEndpoint()throws Exception {
        var pool=resources();var original=new Child();var candidate=new Child();
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var gate=new MembershipEndpointHandoff(original,false,pool,2000);var threads=Executors.newVirtualThreadPerTaskExecutor()) {
            var change=threads.submit(()->{gate.replace(()->{entered.countDown();try {if(!release.await(5,TimeUnit.SECONDS))throw new IOException("test factory timeout");}
                catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}return candidate;});return null;});
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            var close=threads.submit(()->{gate.close();return null;});
            try {long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
                while(gate.state()!=MembershipEndpointHandoff.State.CLOSED && System.nanoTime()<end)Thread.onSpinWait();
                assertEquals(MembershipEndpointHandoff.State.CLOSED,gate.state());assertFalse(close.isDone());assertEquals(1,pool.usage().leases());
            }finally{release.countDown();}
            assertThrows(ExecutionException.class,()->change.get(5,TimeUnit.SECONDS));close.get(5,TimeUnit.SECONDS);
            assertTrue(candidate.closes.get()>0);assertThrows(IllegalArgumentException.class,()->gate.handle(peer,marker));
        }
        assertEquals(0,pool.usage().leases());
    }
    @Test void factoryFailureLeavesNoServingPathAndCloseFailureRetainsRetryableCharge()throws Exception {
        var pool=resources();var original=new Child();
        try(var gate=new MembershipEndpointHandoff(original,false,pool,2000)) {
            assertThrows(IOException.class,()->gate.replace(()->{throw new IOException("factory failure");}));
            assertEquals(MembershipEndpointHandoff.State.FAILED,gate.state());assertThrows(IllegalArgumentException.class,()->gate.handle(peer,marker));
        }
        original=new Child();original.failClose=true;
        try(var gate=new MembershipEndpointHandoff(original,true,pool,2000)) {
            assertThrows(IOException.class,gate::close);assertEquals(MembershipEndpointHandoff.State.CLOSED,gate.state());
            assertEquals(1,pool.usage().leases());assertThrows(IllegalArgumentException.class,()->gate.handle(peer,marker));gate.close();
        }
        assertEquals(0,pool.usage().leases());
    }
    @Test void closeInsideFactoryFailsWithoutDeadlockingAndKeepsOwnershipForRetry()throws Exception {
        var pool=resources();var original=new Child();
        try(var gate=new MembershipEndpointHandoff(original,false,pool,2000)) {
            assertThrows(IllegalArgumentException.class,()->gate.replace(()->{gate.close();return new Child();}));
            assertEquals(MembershipEndpointHandoff.State.CLOSED,gate.state());assertEquals(1,pool.usage().leases());gate.close();
        }
        assertEquals(0,pool.usage().leases());
    }
}
