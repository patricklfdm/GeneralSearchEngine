package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.concurrent.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53PendingListenerDrainTest.storage;

class V53LearnerStoreCloseRaceTest {
    @TempDir Path temp;
    static void awaitCancellation(CountDownLatch latch)throws IOException {
        boolean interrupted=Thread.interrupted();long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(20);
        try {
            while(latch.getCount()!=0) {
                long left=end-System.nanoTime();if(left<=0)throw new IOException("store callback gate expired");
                try{latch.await(left,TimeUnit.NANOSECONDS);}catch(InterruptedException e){interrupted=true;}
            }
        }finally{if(interrupted)Thread.currentThread().interrupt();}
    }
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void externalDrainDoesNotHoldTheStoreMonitorAgainstAReentrantCallback(String listener)throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            var store=f.fixture.f.local.store;var budget=f.fixture.f.local.source.client;
            var entered=new CountDownLatch(1);var reenter=new CountDownLatch(1);var release=new CountDownLatch(1);
            var callback=new CompletableFuture<Throwable>();var external=new CompletableFuture<Void>();
            MembershipTransport.Events hook=(event,q,a)->{
                if(!event.equals("BEFORE_RESPONSE_WRITE"))return;
                entered.countDown();awaitCancellation(reenter);
                try{store.close();callback.complete(null);}catch(Throwable error){callback.complete(error);}
                awaitCancellation(release);
            };
            MembershipLearnerCheckpointEndpoint checkpoint=null;MembershipLearnerHeadEndpoint head=null;Thread closer=null;
            try {
                if(listener.equals("checkpoint"))checkpoint=f.listen(hook);
                else{f.pending.endorse();head=f.pending.retainSource().listenHead(f.fixture.f.local.config.bounds(),hook);}
                try(var contact=f.contact()) {
                    var request=listener.equals("checkpoint")?f.first():V53LearnerHeadProtocolTest.query(f.fixture.f.head,f.reader);
                    var pending=contact.exchange(f.local,request,listener.equals("checkpoint")?"SOURCE_OFFER":"LEARNER_HEAD_ACK",System.nanoTime()+TimeUnit.SECONDS.toNanos(20));
                    assertTrue(entered.await(10,TimeUnit.SECONDS));var held=storage(budget.usage());
                    closer=Thread.ofPlatform().start(()->{try{store.close();external.complete(null);}catch(Throwable error){external.completeExceptionally(error);}});
                    // Actual socket cancellation proves the external closer reached
                    // transport stop, while this callback still prevents drain.
                    assertThrows(ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));reenter.countDown();
                    assertEquals("joining "+(listener.equals("checkpoint")?"checkpoint":"progress")+" listener not drained",
                            assertInstanceOf(IOException.class,callback.get(10,TimeUnit.SECONDS)).getMessage());
                    assertFalse(external.isDone());assertEquals(held,storage(budget.usage()));
                    release.countDown();external.get(10,TimeUnit.SECONDS);assertEquals(0,budget.usage().leases());
                }
            }finally {
                reenter.countDown();release.countDown();
                if(closer!=null){closer.join(15000);assertFalse(closer.isAlive());}
                if(checkpoint!=null)checkpoint.close();if(head!=null)head.close();store.close();
            }
        }
    }
}
