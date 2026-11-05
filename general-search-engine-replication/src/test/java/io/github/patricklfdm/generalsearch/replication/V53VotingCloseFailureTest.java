package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original writers and admitted callbacks; no executor or service replacement. */
class V53VotingCloseFailureTest {
    @TempDir Path temp;
    static ReplicationBounds shortClose() {
        var b=ReplicationBounds.defaults();
        return new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),200,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
    }
    static final class Gate implements AutoCloseable {
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        void stop(){entered.countDown();try{assertTrue(release.await(30,TimeUnit.SECONDS));}
            catch(InterruptedException e){Thread.currentThread().interrupt();throw new AssertionError(e);}}
        void reached()throws Exception {assertTrue(entered.await(15,TimeUnit.SECONDS));}
        public void close(){release.countDown();}
    }
    static void sameCallCharges(MembershipResources.Usage before,MembershipResources.Usage after) {
        assertEquals(before.queued(),after.queued());
        for(var unit:List.of(MembershipResources.Unit.CONTROL,MembershipResources.Unit.WAITER))
            assertEquals(before.counts().getOrDefault(unit,0),after.counts().getOrDefault(unit,0));
    }
    static Future<?> call(ExecutorService executor,String name,MembershipVotingEndpoint endpoint,MembershipIdentity sender,Decoded request) {
        return executor.submit(()->{Thread.currentThread().setName(name);assertThrows(Exception.class,()->endpoint.handle(sender,request));});
    }
    @Test void transferTimeoutStillShutsDownAndDrainsTheWriter()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false,false,true);var writer=new Gate();var incoming=new Gate();var executor=Executors.newFixedThreadPool(2)) {
            var resources=n.budgets.get(1);var original=resources.usage();
            java.util.function.LongSupplier clock=()->{
                String name=Thread.currentThread().getName();
                if(name.equals("gse-membership-voting"))writer.stop();
                if(name.equals("test-voting-transfer") && resources.observations().changes().stream().anyMatch(change->
                        change.event().equals("RESERVE") && change.added().stream().anyMatch(v->v.owner().startsWith("transfer-trace-"))))incoming.stop();
                return System.nanoTime();
            };
            var endpoint=new MembershipVotingEndpoint(n.owners.get(1),resources,shortClose(),(p,q,k,d)->n.transports.get(1).exchange(p,q,k,d),clock,System.nanoTime(),V53NativeVotingTest.BUDGET);
            var sender=n.owners.getFirst().activationIdentity();
            var active=call(executor,"test-voting-control",endpoint,sender,n.request(1,n.accept));
            var request=MembershipActivation.frame("CHUNK",n.owners.get(1).activationContext(),sender,n.owners.get(1).activationIdentity(),n.f.ballot,UUID.randomUUID(),1,
                    Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest",n.accept.digest(),"bytes",""));
            Future<?> transfer=null;
            try {
                writer.reached();transfer=call(executor,"test-voting-transfer",endpoint,sender,request);incoming.reached();
                var failure=assertThrows(RuntimeException.class,endpoint::close);
                assertTrue(V53SlotCloseDrainTest.contains(failure,"transfer service close timeout"));
                assertTrue(V53SlotCloseDrainTest.contains(failure,"voting writer close timeout"),"a transfer failure must not skip the held writer");
                assertTrue(resources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0)>original.counts().getOrDefault(MembershipResources.Unit.CONTROL,0));
                assertThrows(IllegalArgumentException.class,()->endpoint.handle(sender,n.request(1,n.accept)));
            }finally{writer.close();incoming.close();active.get(15,TimeUnit.SECONDS);if(transfer!=null)transfer.get(15,TimeUnit.SECONDS);endpoint.close();}
            sameCallCharges(original,resources.usage());
        }
    }
    @ParameterizedTest @ValueSource(booleans={false,true})
    void successfulWriterDrainStillWaitsForItsAdmittedReplyWaiter(boolean interrupted)throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false);var reply=new Gate();var executor=Executors.newFixedThreadPool(2)) {
            var forced=new AtomicBoolean();n.hooks.get(1).set(point->{if(point.equals("ACCEPT_PARENT_FORCED"))forced.set(true);});
            var resources=n.budgets.get(1);var original=resources.usage();
            java.util.function.LongSupplier clock=()->{if(Thread.currentThread().getName().equals("test-voting-reply") && forced.get())reply.stop();return System.nanoTime();};
            var endpoint=new MembershipVotingEndpoint(n.owners.get(1),resources,ReplicationBounds.defaults(),
                    (p,q,k,d)->n.transports.get(1).exchange(p,q,k,d),clock,System.nanoTime(),V53NativeVotingTest.BUDGET);
            var active=call(executor,"test-voting-reply",endpoint,n.owners.getFirst().activationIdentity(),n.request(1,n.accept));
            Future<?> closing=null;
            try {
                reply.reached();assertTrue(resources.usage().counts().getOrDefault(MembershipResources.Unit.WAITER,0)>0);
                if(interrupted) {
                    var failure=V53SlotCloseDrainTest.interruptedClose(endpoint);
                    assertTrue(V53SlotCloseDrainTest.contains(failure,"voting close interrupted"));
                    assertTrue(V53SlotCloseDrainTest.contains(failure,"voting caller close interrupted"));
                }
                closing=executor.submit(endpoint::close);
                // The original successful writer is done; the admitted caller still holds its waiter.
                var close=closing;assertThrows(TimeoutException.class,()->close.get(200,TimeUnit.MILLISECONDS));
            }finally{reply.close();active.get(15,TimeUnit.SECONDS);if(closing!=null)closing.get(15,TimeUnit.SECONDS);endpoint.close();}
            sameCallCharges(original,resources.usage());
        }
    }
    @ParameterizedTest @ValueSource(booleans={false,true})
    void activeWorkerOrCallerCannotDeclareItsOwnDrainComplete(boolean worker)throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false);var executor=Executors.newSingleThreadExecutor()) {
            var forced=new AtomicBoolean();n.hooks.get(1).set(point->{if(point.equals("ACCEPT_PARENT_FORCED"))forced.set(true);});
            var holder=new AtomicReference<MembershipVotingEndpoint>();var failure=new AtomicReference<Throwable>();var once=new AtomicBoolean();
            var resources=n.budgets.get(1);var original=resources.usage();
            java.util.function.LongSupplier clock=()->{
                String name=Thread.currentThread().getName();
                if((worker?name.equals("gse-membership-voting"):name.equals("test-self-close") && forced.get()) && once.compareAndSet(false,true))
                    failure.set(assertThrows(IllegalStateException.class,holder.get()::close));
                return System.nanoTime();
            };
            try(var endpoint=new MembershipVotingEndpoint(n.owners.get(1),resources,ReplicationBounds.defaults(),
                    (p,q,k,d)->n.transports.get(1).exchange(p,q,k,d),clock,System.nanoTime(),V53NativeVotingTest.BUDGET)) {
                holder.set(endpoint);call(executor,"test-self-close",endpoint,n.owners.getFirst().activationIdentity(),n.request(1,n.accept)).get(15,TimeUnit.SECONDS);
                endpoint.close();assertNotNull(failure.get());
                assertEquals("voting close from active "+(worker?"writer":"handler"),failure.get().getMessage());
            }
            sameCallCharges(original,resources.usage());
        }
    }

}
