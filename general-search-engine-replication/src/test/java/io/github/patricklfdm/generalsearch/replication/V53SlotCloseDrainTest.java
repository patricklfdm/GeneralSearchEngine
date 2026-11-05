package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;

/** A real native ACCEPT writer remains inside its original time check until released.
 * Cancelling its reply is not proof that the writer or its CONTROL lease drained. */
class V53SlotCloseDrainTest {
    @TempDir Path temp;

    static final class Gate implements Runnable,AutoCloseable {
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        @Override public void run() {
            // The clock is already injectable. Stop only the actual voting writer,
            // before it opens pulls or acquires the durable journal monitor.
            if(!Thread.currentThread().getName().equals("gse-membership-voting"))return;
            entered.countDown();
            try {assertTrue(release.await(30,TimeUnit.SECONDS),"native writer test gate expired");}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError("native writer test gate interrupted",error);}
        }
        void reached()throws Exception {assertTrue(entered.await(15,TimeUnit.SECONDS),"native ACCEPT did not reach writer");}
        @Override public void close(){release.countDown();}
    }
    static Throwable interruptedClose(AutoCloseable endpoint) {
        Thread.currentThread().interrupt();
        try {return assertThrows(Exception.class,endpoint::close);}
        finally {assertTrue(Thread.interrupted(),"close must preserve interruption");}
    }
    static boolean contains(Throwable failure,String message) {
        if(message.equals(failure.getMessage()))return true;
        if(failure.getCause()!=null && contains(failure.getCause(),message))return true;
        for(var suppressed:failure.getSuppressed())if(contains(suppressed,message))return true;
        return false;
    }
    static void finishDrain(AutoCloseable endpoint,Gate gate)throws Exception {
        try(var executor=Executors.newSingleThreadExecutor()) {
            var started=new CountDownLatch(1);
            var closing=executor.submit(()->{started.countDown();endpoint.close();return null;});
            try {
                assertTrue(started.await(5,TimeUnit.SECONDS));
                assertThrows(TimeoutException.class,()->closing.get(200,TimeUnit.MILLISECONDS),
                        "close must not report success while the original writer is still held");
            }finally{gate.close();}
            closing.get(15,TimeUnit.SECONDS);
        }
        endpoint.close();
    }
    @ParameterizedTest @ValueSource(booleans={false,true})
    void failedSlotCloseRetainsWriterDrainOnEveryRetry(boolean interrupted)throws Exception {
        var helper=new V53SlotEndpointTest();helper.temp=temp;
        try(var n=helper.new Network(3,false);var gate=new Gate()) {
            var endpoint=n.endpoints.get(1);n.beforeClock.set(gate);
            var request=n.request(1,"ACCEPT",Map.of("acceptance",n.accept.digest()));
            var call=CompletableFuture.runAsync(()->assertThrows(IOException.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request)));
            try {
                gate.reached();
                var failure=interrupted?interruptedClose(endpoint):assertThrows(IllegalArgumentException.class,endpoint::close);
                assertEquals(interrupted?"voting close interrupted":"voting writer close timeout",failure.getMessage());
                call.get(10,TimeUnit.SECONDS);
                assertTrue(n.resources.get(1).usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0)>0,
                        "the actual writer must retain its CONTROL charge");
                assertThrows(IllegalArgumentException.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request));
                assertEquals("voting close interrupted",interruptedClose(endpoint).getMessage());
                finishDrain(endpoint,gate);
                assertEquals(0,n.resources.get(1).usage().counts().getOrDefault(MembershipResources.Unit.WAITER,0));
            }finally{gate.close();call.get(15,TimeUnit.SECONDS);endpoint.close();}
        }
    }
    @ParameterizedTest @ValueSource(booleans={false,true})
    void activationScopeRetainsFailedSlotDrainUntilItsWriterStops(boolean closeParent)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network();var gate=new Gate()) {
            n.activate();var accepted=n.begin(false);var endpoint=n.endpoints.get(1);n.beforeClock.set(gate);
            AutoCloseable closing=closeParent?endpoint:()->endpoint.abandon(n.ballot);
            var request=n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest()));
            var call=CompletableFuture.runAsync(()->assertThrows(IOException.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request)));
            try {
                gate.reached();assertTrue(contains(interruptedClose(closing),"voting close interrupted"));call.get(10,TimeUnit.SECONDS);
                assertTrue(n.resources.get(1).usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0)>0);
                assertTrue(contains(interruptedClose(closing),"voting close interrupted"),"parent must retry its retained child");
                var lock=n.incomingScratch.get(1).resolve("scope.lock");
                assertThrows(ReplicationException.class,()->MembershipOwnership.own(lock,false),"failed child drain must retain the parent scratch lock");
                finishDrain(closing,gate);
                if(closeParent)try(var available=MembershipOwnership.own(lock,false)){assertTrue(available.lock().isValid());}
                else assertThrows(ReplicationException.class,()->MembershipOwnership.own(lock,false),"abandon only closes the campaign scope");
            }finally{gate.close();call.get(15,TimeUnit.SECONDS);endpoint.close();}
        }
    }
    @Test void simultaneousClosersBothWaitForTheOriginalWriter()throws Exception {
        var helper=new V53SlotEndpointTest();helper.temp=temp;
        try(var n=helper.new Network(3,false);var gate=new Gate();var executor=Executors.newSingleThreadExecutor()) {
            var endpoint=n.endpoints.get(1);n.beforeClock.set(gate);
            var request=n.request(1,"ACCEPT",Map.of("acceptance",n.accept.digest()));
            var call=CompletableFuture.runAsync(()->assertThrows(IOException.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request)));
            try {
                gate.reached();var first=executor.submit(endpoint::close);
                call.get(10,TimeUnit.SECONDS); // The first closer cancelled the actual response.
                try {finishDrain(endpoint,gate);}finally{gate.close();first.get(15,TimeUnit.SECONDS);}
            }finally{gate.close();call.get(15,TimeUnit.SECONDS);endpoint.close();}
        }
    }
}
