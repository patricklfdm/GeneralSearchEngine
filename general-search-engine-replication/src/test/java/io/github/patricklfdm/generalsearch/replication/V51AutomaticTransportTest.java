package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static org.junit.jupiter.api.Assertions.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class V51AutomaticTransportTest {
    static final class Accounting implements AutomaticTransport.Events {
        final Set<Object> live=Collections.newSetFromMap(new IdentityHashMap<>());
        final CountDownLatch entered=new CountDownLatch(2),release=new CountDownLatch(1),drained=new CountDownLatch(2);
        final AtomicBoolean fail=new AtomicBoolean();boolean hold;
        int rejected;
        public void at(String barrier,Map<String,Object> request,Map<String,Object> response) throws IOException {
            if(hold&&barrier.equals("BEFORE_REQUEST_WRITE"))try {
                entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("test release timeout");
            }catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException(e);}
        }
        public synchronized void accounting(String event,Map<String,Object> request,Object token,int bytes) {
            if(event.equals("OUTBOUND_ADMITTED")) {
                assertTrue(live.add(token));assertTrue(live.size()<=2);assertTrue(bytes>48);
                if(fail.getAndSet(false))throw new IllegalStateException("observer failure");
            }else if(event.equals("OUTBOUND_RELEASED")){assertTrue(live.remove(token));drained.countDown();}
            else if(event.equals("OUTBOUND_REJECTED"))rejected++;
        }
        synchronized int size(){return live.size();}
    }
    static final class Pair implements AutoCloseable {
        final AutomaticRecords.Record manifest;final AutomaticTransport sender,receiver;
        Pair(AutomaticTransport.Events observer) throws Exception {
            var value=V51StorageFixture.copy(decode(unbase(V51StorageFixture.samples().get("MANIFEST")),"MANIFEST").value());
            var ports=ReplicaLeaderTestSupport.ports();var members=new ArrayList<Object>();
            for(int i=0;i<3;i++)members.add(Map.of("node","node-"+(i+1),"host","127.0.0.1","port",(long)ports.get(i)));
            value.put("members",members);manifest=decode(encode("MANIFEST",value),"MANIFEST");
            receiver=new AutomaticTransport(manifest,"node-2",V51RuntimeFixture.BOUNDS,r->AutomaticWire.reply(r,"HANDSHAKE",Map.of("mode","AUTOMATIC")));
            sender=new AutomaticTransport(manifest,"node-1",V51RuntimeFixture.BOUNDS,r->AutomaticWire.reply(r,"HANDSHAKE",Map.of("mode","AUTOMATIC")),observer);
        }
        Map<String,Object> request(){
            var ballot=decode(encode("PROMISE",Map.of("manifestDigest",manifest.digest(),"epoch",2L,"proposer","node-1","incarnation",UUID.randomUUID().toString())),"PROMISE");
            return AutomaticWire.message(manifest,ballot,"node-1","node-2","HANDSHAKE",UUID.randomUUID(),1,Map.of("mode","AUTOMATIC"));
        }
        public void close(){sender.close();receiver.close();}
    }
    @Test void cancellationDoesNotFreeAStillRunningReservation() throws Exception {
        var observer=new Accounting();observer.hold=true;
        try(var pair=new Pair(observer)) {
            var one=pair.sender.exchange("node-2",pair.request());var two=pair.sender.exchange("node-2",pair.request());
            try {
                assertTrue(observer.entered.await(3,TimeUnit.SECONDS));assertEquals(2,observer.size());
                assertCapacity(pair.sender.exchange("node-2",pair.request()));
                one.cancel(true);assertCapacity(pair.sender.exchange("node-2",pair.request()));
            }finally{observer.release.countDown();}
            two.get(3,TimeUnit.SECONDS);assertTrue(observer.drained.await(3,TimeUnit.SECONDS));assertEquals(0,observer.size());
            assertEquals(2,observer.rejected);
        }
    }
    @Test void observerAndEncodingFailuresDoNotLeakReservations() throws Exception {
        var observer=new Accounting();observer.fail.set(true);
        try(var pair=new Pair(observer)) {
            assertThrows(ExecutionException.class,()->pair.sender.exchange("node-2",pair.request()).get(3,TimeUnit.SECONDS));
            assertEquals(0,observer.size());
            var malformed=new HashMap<>(pair.request());malformed.put("unexpected",true);
            assertThrows(ExecutionException.class,()->pair.sender.exchange("node-2",malformed).get(3,TimeUnit.SECONDS));
            assertEquals("HANDSHAKE",pair.sender.exchange("node-2",pair.request()).get(3,TimeUnit.SECONDS).get("type"));
        }
        assertEquals(0,observer.size());
    }
    @Test void closeInterruptsHeldSendersAndReleasesAllReservations() throws Exception {
        var observer=new Accounting();observer.hold=true;
        try(var pair=new Pair(observer)) {
            var one=pair.sender.exchange("node-2",pair.request());var two=pair.sender.exchange("node-2",pair.request());
            assertTrue(observer.entered.await(3,TimeUnit.SECONDS));pair.sender.close();
            assertTrue(one.isCompletedExceptionally());assertTrue(two.isCompletedExceptionally());assertEquals(0,observer.size());
        }finally{observer.release.countDown();}
    }
    @ParameterizedTest @ValueSource(booleans={false,true})
    void completedExchangeReleasesCapacityBeforeContinuation(boolean fail) throws Exception {
        var entered=new CountDownLatch(2);var firstRelease=new CountDownLatch(1);var secondRelease=new CountDownLatch(1);
        AutomaticTransport.Events observer=(barrier,request,response)->{
            long sequence=number(request,"eventSequence");
            if(barrier.equals("BEFORE_REQUEST_WRITE")&&sequence<=2)try {
                entered.countDown();
                if(!(sequence==1?firstRelease:secondRelease).await(5,TimeUnit.SECONDS))throw new IOException("test release timeout");
                if(sequence==1&&fail)throw new IllegalStateException("completed exchange failed");
            }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
        };
        try(var pair=new Pair(observer)) {
            var request=new HashMap<>(pair.request());request.put("eventSequence",2L);
            var first=pair.sender.exchange("node-2",pair.request());var second=pair.sender.exchange("node-2",request);
            try {
                assertTrue(entered.await(3,TimeUnit.SECONDS));
                // Attach before releasing either exchange: this continuation executes
                // synchronously when the first future completes, while the second is live.
                var next=first.handle((reply,error)->{
                    assertEquals(fail,error!=null);
                    if(!fail)assertEquals("HANDSHAKE",reply.get("type"));
                    var follow=new HashMap<>(pair.request());follow.put("eventSequence",3L);
                    return pair.sender.exchange("node-2",follow);
                }).thenCompose(value->value);
                firstRelease.countDown();
                assertEquals("HANDSHAKE",next.get(3,TimeUnit.SECONDS).get("type"));
                assertFalse(second.isDone(),"other reservation must remain live");
            }finally{firstRelease.countDown();secondRelease.countDown();}
            second.get(3,TimeUnit.SECONDS);
        }finally{firstRelease.countDown();secondRelease.countDown();}
    }
    static void assertCapacity(CompletableFuture<?> future) {
        var failure=assertThrows(ExecutionException.class,()->future.get(1,TimeUnit.SECONDS));
        assertEquals(ReplicationException.Reason.CAPACITY_EXCEEDED,((ReplicationException)failure.getCause()).reason());
    }
}
