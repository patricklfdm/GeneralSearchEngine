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

/** Real outgoing control work and ownership; gates only stop existing callbacks. */
class V53ActivationDriverDrainTest {
    @TempDir Path temp;
    V53ActivationDriverTest.Local local(LongSupplier clock)throws Exception {
        var helper=new V53ActivationDriverTest();helper.temp=temp;
        return helper.new Local(3,false,Files.createDirectory(temp.resolve("raw-"+UUID.randomUUID())),clock,200,
                ()->new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,MembershipResources.QUEUE_LIMIT,4096));
    }
    static Future<?> run(ExecutorService executor,MembershipActivationDriver driver) {
        return executor.submit(()->assertThrows(Exception.class,()->driver.run(0)));
    }
    static void locked(Path scratch){V53ActivationCloseDrainTest.locked(scratch);}
    static void unlocked(Path scratch)throws Exception{V53ActivationCloseDrainTest.unlocked(scratch);}
    static Map<String,MembershipResourceObservations.Charge> controls(V53ActivationDriverTest.Local local) {
        var trace=local.budgets.getFirst().observations();assertFalse(trace.truncated());assertFalse(trace.failed());
        var held=new TreeMap<String,MembershipResourceObservations.Charge>();
        for(var change:trace.changes()) {
            for(var charge:change.removed())held.remove(charge.owner());
            for(var charge:change.added())held.put(charge.owner(),charge);
        }
        String request=local.requests.getFirst().digest();
        held.entrySet().removeIf(e->!e.getKey().equals(request) && !e.getKey().startsWith("activation-task-") && !e.getKey().startsWith("source-export-"));
        return held;
    }

    @Test void failedRoundDrainKeepsLocalSourceAndRequestReservations()throws Exception {
        try(var local=local(()->0);var gate=new V53ActivationCloseDrainTest.Gate();var executor=Executors.newSingleThreadExecutor();var driver=local.driver(1)) {
            local.override.set((p,r,k,d)->{gate.stop();return CompletableFuture.failedFuture(new IOException("released original peer"));});
            var running=run(executor,driver);
            try {
                gate.reached();var held=controls(local);assertEquals(3,held.size());
                assertThrows(Exception.class,driver::close);running.get(10,TimeUnit.SECONDS);
                locked(local.driverScratch);
                assertEquals(held,controls(local));
                assertThrows(Exception.class,driver::close);
                assertEquals(held,controls(local));
            }finally{gate.close();running.get(10,TimeUnit.SECONDS);driver.close();}
            unlocked(local.driverScratch);
        }
    }

    @Test void interruptedCloserRetainsOriginalChargesForExternalDrain()throws Exception {
        try(var local=local(()->0);var gate=new V53ActivationCloseDrainTest.Gate();var executor=Executors.newSingleThreadExecutor();var driver=local.driver(1)) {
            local.override.set((p,r,k,d)->{gate.stop();return CompletableFuture.failedFuture(new IOException("released original peer"));});
            var running=run(executor,driver);
            try {
                gate.reached();var held=controls(local);assertEquals(3,held.size());
                var failure=V53SlotCloseDrainTest.interruptedClose(driver);
                assertTrue(V53SlotCloseDrainTest.contains(failure,"activation driver close interrupted"));
                running.get(10,TimeUnit.SECONDS);locked(local.driverScratch);assertEquals(held,controls(local));
                assertFalse(gate.interrupted.await(200,TimeUnit.MILLISECONDS));
            }finally{gate.close();running.get(10,TimeUnit.SECONDS);driver.close();}
            unlocked(local.driverScratch);
        }
    }

    @Test void cancellationDoesNotInterruptAWorkerStillOwningItsChannel()throws Exception {
        try(var local=local(()->0);var gate=new V53ActivationCloseDrainTest.Gate();var executor=Executors.newSingleThreadExecutor();var driver=local.driver(1)) {
            var forced=new AtomicBoolean();var failed=new AtomicReference<Throwable>();
            local.override.set((p,r,k,d)->{
                Path file=local.driverScratch.resolve("source-held");
                try(var channel=FileChannel.open(file,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
                    gate.stop();channel.write(ByteBuffer.wrap(new byte[]{1,2,3}));channel.force(true);forced.set(true);
                    return CompletableFuture.failedFuture(new IOException("released original worker"));
                }catch(Throwable error){failed.set(error);return CompletableFuture.failedFuture(error);}
                finally{try{Files.deleteIfExists(file);}catch(IOException error){failed.compareAndSet(null,error);}}
            });
            var running=run(executor,driver);
            try {
                gate.reached();assertThrows(Exception.class,driver::close);locked(local.driverScratch);
                assertFalse(gate.interrupted.await(200,TimeUnit.MILLISECONDS),"close must cancel protocol work without interrupting its file owner");
            }finally{gate.close();running.get(10,TimeUnit.SECONDS);driver.close();}
            assertNull(failed.get());assertTrue(forced.get());unlocked(local.driverScratch);
        }
    }

    @ParameterizedTest @ValueSource(strings={"runner","peer"})
    void callbackCannotDeclareItsOwnDrainComplete(String callback)throws Exception {
        var holder=new AtomicReference<MembershipActivationDriver>();var scratch=new AtomicReference<Path>();
        var selected=new AtomicBoolean();var failure=new AtomicReference<Throwable>();var locked=new AtomicBoolean();
        Runnable selfClose=()->{
            if(!selected.compareAndSet(false,true))return;
            try{holder.get().close();}catch(Throwable error){failure.set(error);}
            try(var ownership=MembershipOwnership.own(scratch.get().resolve("scope.lock"),false)){locked.set(false);}
            catch(ReplicationException expected){locked.set(true);}
            catch(IOException error){throw new AssertionError(error);}
        };
        LongSupplier clock=()->{if(callback.equals("runner") && holder.get()!=null && Thread.currentThread().getName().equals("test-driver-self"))selfClose.run();return 0;};
        try(var local=local(clock);var executor=Executors.newSingleThreadExecutor();var driver=local.driver(1)) {
            holder.set(driver);scratch.set(local.driverScratch);
            local.override.set((p,r,k,d)->{selfClose.run();return CompletableFuture.failedFuture(new IOException("self close requested"));});
            executor.submit(()->{Thread.currentThread().setName("test-driver-self");assertThrows(Exception.class,()->driver.run(0));}).get(10,TimeUnit.SECONDS);
            assertTrue(selected.get());assertInstanceOf(IOException.class,failure.get());
            assertEquals("activation driver close from active callback",failure.get().getMessage());
            assertTrue(locked.get());driver.close();unlocked(local.driverScratch);
        }
    }
}
