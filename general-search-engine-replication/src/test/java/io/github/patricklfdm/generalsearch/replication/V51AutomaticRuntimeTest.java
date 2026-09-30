package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.CountDownLatch;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51AutomaticRuntimeTest {
    @TempDir Path root;
    @Test void realSocketsElectPublishAndRetainedSurvivorsRecoverApplication() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();var document=new Document(1,"shared");
            leader.submit(1,app->app.documents("ADD",List.of(document))).get(20,TimeUnit.SECONDS);
            assertEquals(document,leader.inspectLocal(e->e.get(1)).get(5,TimeUnit.SECONDS));
            String old=group.name(leader);group.stop(old);var recovered=group.leader();
            assertEquals(document,recovered.inspectLocal(e->e.get(1)).get(5,TimeUnit.SECONDS));
            recovered.submit(2,app->app.documents("UPDATE",List.of(new Document(1,"updated")))).get(20,TimeUnit.SECONDS);
            assertEquals("updated",recovered.inspectLocal(e->e.get(1).value()).get(5,TimeUnit.SECONDS));
            assertTrue(group.wire.stream().anyMatch(m->m.get("type").equals("BASIS_CHUNK")));
            assertTrue(group.wire.stream().anyMatch(m->m.get("type").equals("SELECTED_OFFER")));
        }
    }
    @Test void businessRejectionLeavesProvenHistoryAndPublishedDocumentUnchanged() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();var doc=new Document(1,"shared");
            leader.submit(1,app->app.documents("ADD",List.of(doc))).get(20,TimeUnit.SECONDS);int cut=leader.view().provenIndex();
            assertThrows(java.util.concurrent.ExecutionException.class,()->leader.submit(1,app->app.documents("ADD",List.of(doc))).get(10,TimeUnit.SECONDS));
            assertEquals(cut,leader.view().provenIndex());assertEquals(doc,leader.inspectLocal(e->e.get(1)).get(5,TimeUnit.SECONDS));
        }
    }
    private static <R> R control(AutomaticRuntime<?,?> runtime,String method,java.util.concurrent.Callable<R> action) throws Exception {
        var call=AutomaticRuntime.class.getDeclaredMethod(method,java.util.concurrent.Callable.class);call.setAccessible(true);
        try {@SuppressWarnings("unchecked") R result=(R)call.invoke(runtime,action);return result;}
        catch(java.lang.reflect.InvocationTargetException error) {
            if(error.getCause() instanceof Exception cause)throw cause;throw (Error)error.getCause();
        }
    }
    @Test void maintenanceWaitsForForegroundAndExpiredWorkCannotExecuteLater() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            // Isolate dispatcher admission from the fixture's own background producer.
            var field=AutomaticRuntime.class.getDeclaredField("rejoin");field.setAccessible(true);
            var rejoin=(AutomaticRejoin)field.get(leader);control(leader,"controlled",()->{rejoin.stop();return null;});rejoin.close();
            var calls=new java.util.concurrent.atomic.AtomicInteger();
            var pending=leader.submit(1,app->{entered.countDown();try{release.await();}catch(InterruptedException e){throw new IllegalStateException(e);}
                return app.documents("ADD",List.of(new Document(14,"foreground")));});
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            try {
                assertThrows(java.util.concurrent.TimeoutException.class,()->control(leader,"maintained",calls::incrementAndGet));
                assertEquals(0,calls.get(),"maintenance must not start during an admitted foreground operation");
                assertEquals("responsive",control(leader,"controlled",()->"responsive"));
            } finally {release.countDown();}
            pending.get(20,TimeUnit.SECONDS);
            assertEquals(1,control(leader,"maintained",calls::incrementAndGet));
            assertEquals(1,calls.get(),"expired maintenance must be cancelled before a later control turn");
            assertEquals("foreground",leader.inspectLocal(e->e.get(14).value()).get(5,TimeUnit.SECONDS));
        }
    }
    @Test void localTransportContentionDoesNotSpendTheWireRetryBudget() throws Exception {
        var occupied=new CountDownLatch(2);var release=new CountDownLatch(1);
        var rejected=new CountDownLatch(4);var written=new java.util.concurrent.atomic.AtomicInteger();
        var owner=new java.util.concurrent.atomic.AtomicReference<String>();
        AutomaticTransport.Events observer=new AutomaticTransport.Events() {
            public void at(String event,java.util.Map<String,Object> request,java.util.Map<String,Object> response) throws java.io.IOException {
                if(!request.get("sender").equals(owner.get())||!event.equals("BEFORE_REQUEST_WRITE"))return;
                if(request.get("type").equals("HANDSHAKE"))try {
                    occupied.countDown();if(!release.await(10,TimeUnit.SECONDS))throw new java.io.IOException("test admission hold expired");
                }catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                if(request.get("type").equals("ACCEPT"))written.incrementAndGet();
            }
            public void accounting(String event,java.util.Map<String,Object> request,Object token,int bytes) {
                if(event.equals("OUTBOUND_REJECTED")&&request.get("sender").equals(owner.get())&&request.get("type").equals("ACCEPT"))rejected.countDown();
            }
        };
        try(var group=new V51RuntimeFixture(root,true,false)) {
            for(int i=1;i<=3;i++)group.open(i,AutomaticStore.Faults.NONE,AutomaticRuntime.Events.NONE,observer);
            var leader=group.leader();owner.set(group.name(leader));
            // Hold real TCP reservations explicitly. Natural background recovery is
            // stopped only in this test, so occupancy cannot depend on scheduling.
            var recoveryField=AutomaticRuntime.class.getDeclaredField("rejoin");recoveryField.setAccessible(true);
            for(var runtime:group.nodes.values()) {
                var recovery=(AutomaticRejoin)recoveryField.get(runtime);
                control(runtime,"controlled",()->{recovery.stop();return null;});recovery.close();
            }
            var protocolField=AutomaticRuntime.class.getDeclaredField("protocol");protocolField.setAccessible(true);
            var peerField=AutomaticProtocol.class.getDeclaredField("quorumPeer");peerField.setAccessible(true);
            var protocol=(AutomaticProtocol)protocolField.get(leader);
            String peer=control(leader,"controlled",()->(String)peerField.get(protocol));
            var transportField=AutomaticRuntime.class.getDeclaredField("transport");transportField.setAccessible(true);
            var transport=(AutomaticTransport)transportField.get(leader);
            var manifest=AutomaticRecords.decode(group.manifest,"MANIFEST");
            var request=AutomaticWire.message(manifest,protocol.promise(),owner.get(),peer,"HANDSHAKE",java.util.UUID.randomUUID(),1000,java.util.Map.of("mode","AUTOMATIC"));
            var capacityField=AutomaticTransport.class.getDeclaredField("outbound");capacityField.setAccessible(true);
            @SuppressWarnings("unchecked") var capacities=(java.util.Map<String,java.util.concurrent.Semaphore>)capacityField.get(transport);
            List<java.util.concurrent.CompletableFuture<java.util.Map<String,Object>>> holders=null;
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            while(holders==null&&System.nanoTime()<deadline) {
                holders=control(leader,"controlled",()->{
                    if(protocol.view().pendingExchanges()!=0||capacities.get(peer).availablePermits()!=2)return null;
                    return List.of(transport.exchange(peer,request),transport.exchange(peer,request));
                });
                if(holders==null)Thread.sleep(5);
            }
            assertNotNull(holders,"initial heartbeats must drain before reserving both slots");
            var first=holders.get(0);var second=holders.get(1);
            try {
                assertTrue(occupied.await(5,TimeUnit.SECONDS),()->"held="+occupied.getCount()+" first="+first+" second="+second);written.set(0);
                var pending=leader.submit(1,app->app.documents("ADD",List.of(new Document(81,"after-capacity"))));
                assertTrue(rejected.await(5,TimeUnit.SECONDS),"must defer beyond the two wire retries while capacity is held");
                assertFalse(pending.isDone());assertEquals(0,written.get(),"unadmitted requests cannot reach the wire");
                assertEquals(AutomaticReplicationState.LEADER_READY,leader.view().state());
                assertTrue(leader.status().peers().stream().filter(p->p.nodeId().value().equals(peer)).findFirst().orElseThrow().reachable(),
                        "local capacity must not mark a previously reachable voter unreachable");
                release.countDown();first.get(3,TimeUnit.SECONDS);second.get(3,TimeUnit.SECONDS);
                pending.get(5,TimeUnit.SECONDS);assertEquals(1,written.get());
                assertEquals("after-capacity",leader.inspectLocal(e->e.get(81).value()).get(5,TimeUnit.SECONDS));
            }finally{release.countDown();}
        }finally{release.countDown();}
    }
    @Test void slowPrivatePreparationKeepsOwnershipUntilCloseCanFinish() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();String name=group.name(leader);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            var pending=leader.submit(1,app->{entered.countDown();try{release.await();}catch(InterruptedException e){throw new IllegalStateException(e);}return app.documents("ADD",List.of(new Document(7,"slow")));});
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            try {
                assertThrows(AutomaticReplicationException.class,leader::close);
                assertThrows(AutomaticReplicationException.class,()->AutomaticStore.open(root.resolve(name),group.manifest,name,V51RuntimeFixture.BOUNDS,AutomaticStore.Faults.NONE));
            } finally {release.countDown();}
            assertThrows(java.util.concurrent.ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));
            group.stop(name);
            try(var store=AutomaticStore.open(root.resolve(name),group.manifest,name,V51RuntimeFixture.BOUNDS,AutomaticStore.Faults.NONE)) {
                assertEquals(0L,store.status().get("applicationSequence"));
            }
        }
    }
    @Test void higherPrepareIsHandledWhilePrivateEncoderIsBlocked() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();String local=group.name(leader);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            var pending=leader.submit(1,app->{entered.countDown();try{release.await();}catch(InterruptedException e){throw new IllegalStateException(e);}return app.documents("ADD",List.of(new Document(9,"fenced")));});
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            try {
                var manifest=AutomaticRecords.decode(group.manifest,"MANIFEST");var members=AutomaticRecords.nodes(manifest.value());
                String peer=members.stream().filter(n->!n.equals(local)).findFirst().orElseThrow();
                long epoch=AutomaticProtocol.nextEpoch(leader.view().promisedEpoch(),members.indexOf(peer));
                var ballot=AutomaticRecords.decode(AutomaticRecords.encode("PROMISE",java.util.Map.of("manifestDigest",manifest.digest(),"epoch",epoch,"proposer",peer,"incarnation",java.util.UUID.randomUUID().toString())),"PROMISE");
                var request=AutomaticWire.message(manifest,ballot,peer,local,"PREPARE",java.util.UUID.randomUUID(),1,java.util.Map.of("nonce",java.util.UUID.randomUUID().toString()));
                var endpoint=AutomaticRecords.object(AutomaticRecords.list(manifest.value().get("members")).get(members.indexOf(local)));
                try(var socket=new java.net.Socket("127.0.0.1",(int)AutomaticRecords.number(endpoint,"port"))) {
                    socket.setSoTimeout(2400);socket.getOutputStream().write(AutomaticWire.encode(request,manifest,V51RuntimeFixture.BOUNDS.maxFrameBytes()));
                    byte[] header=socket.getInputStream().readNBytes(48);int size=AutomaticWire.bodyLength(header,V51RuntimeFixture.BOUNDS.maxFrameBytes());
                    byte[] frame=new byte[48+size];System.arraycopy(header,0,frame,0,48);System.arraycopy(socket.getInputStream().readNBytes(size),0,frame,48,size);
                    assertEquals("PROMISE",AutomaticWire.decode(frame,manifest,V51RuntimeFixture.BOUNDS.maxFrameBytes()).get("type"));
                }
                assertEquals(epoch,leader.view().promisedEpoch());assertNotEquals(AutomaticReplicationState.LEADER_READY,leader.view().state());
            } finally {release.countDown();}
            var error=assertThrows(java.util.concurrent.ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));
            assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,((AutomaticReplicationException)error.getCause()).outcome());
        }
    }
}
