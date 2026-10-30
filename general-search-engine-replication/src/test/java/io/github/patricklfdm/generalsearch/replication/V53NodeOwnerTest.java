package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V53MembershipTransportTest.waitFor;

class V53NodeOwnerTest {
    @TempDir Path temp;
    final class Fixture implements AutoCloseable {
        final V53MembershipTransportTest.Group group;
        final List<MembershipNodeOwner<Integer,Doc>> nodes=new ArrayList<>();
        final Path scratch;
        Fixture()throws Exception {
            var helper=new V53MembershipTransportTest();helper.temp=temp;group=helper.new Group(3);
            group.fixture.ownedHistory=true;group.fixture.nativeApplication=true;
            scratch=Files.createDirectory(temp.resolve("node-scratch-"+UUID.randomUUID()));
        }
        MembershipReplicaConfig<Integer,Doc> config(ReplicationBounds bounds) {
            return config(0,bounds);
        }
        MembershipReplicaConfig<Integer,Doc> config(int index,ReplicationBounds bounds) {
            var target=group.fixture.request.targets().get(index);
            return new MembershipReplicaConfig<>(group.fixture.result.root(),target.identity(),group.identities.stream().filter(id->!id.equals(target.identity())).toList(),
                    target.replicaDirectory(),target.materialization(),bounds,AutomaticLeadershipPolicy.forBounds(bounds));
        }
        MembershipNodeOwner<Integer,Doc> node(ReplicationBounds bounds,MembershipNodeOwner.Hooks hooks) {
            return node(0,bounds,hooks);
        }
        MembershipNodeOwner<Integer,Doc> node(int index,ReplicationBounds bounds,MembershipNodeOwner.Hooks hooks) {
            var node=new MembershipNodeOwner<>(config(index,bounds),builder().configuration(),scratch.resolve("incoming-"+index),scratch.resolve("outgoing-"+index),
                    System::nanoTime,TimeUnit.SECONDS.toNanos(180),hooks);nodes.add(node);return node;
        }
        MembershipNodeOwner<Integer,Doc> node(){return node(ReplicationBounds.defaults(),MembershipNodeOwner.Hooks.NONE);}
        Path lock(){return group.fixture.request.targets().getFirst().replicaDirectory().resolve("replica.lock");}
        void locked(){assertEquals("membership authority already owned in this process",assertThrows(ReplicationException.class,()->MembershipOwnership.own(lock(),false)).getMessage());}
        void released()throws Exception{try(var owned=MembershipOwnership.own(lock(),false)){assertTrue(owned.lock().isValid());}}
        @Override public void close()throws Exception {
            for(var node:nodes.reversed()){node.close();assertEquals(0,node.usage().leases());}
            group.close();
        }
    }
    static ReplicationBounds shortClose() {
        var b=ReplicationBounds.defaults();return new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),2,b.maxPendingClientOperations(),
                b.maxRetryAttempts(),100,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
    }
    static MembershipNodeOwner.Hooks hooks(MembershipBallotAllocator.Cut storage,MembershipTransport.Events network) {
        return new MembershipNodeOwner.Hooks(storage,network,MembershipRoundDriver.Events.NONE,MembershipSlotDriver.Events.NONE);
    }
    static void hold(CountDownLatch entered,CountDownLatch release) {
        entered.countDown();boolean interrupted=false;
        for(;;)try{if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("fixture release deadline");break;}
        catch(InterruptedException ignored){interrupted=true;}
        if(interrupted)Thread.currentThread().interrupt();
    }
    @Test void coldOpenIsExclusiveAndReopenRestoresNoReadyOrPendingCommand()throws Exception {
        try(var f=new Fixture()) {
            var first=f.node();assertEquals(MembershipNodeOwner.State.NEW,first.state());first.open();f.locked();
            assertEquals(MembershipAutomaticOwner.State.NEW,first.serviceState().orElseThrow());assertThrows(IllegalArgumentException.class,first::readiness);
            var second=f.node();assertThrows(ReplicationException.class,second::open);assertEquals(MembershipNodeOwner.State.FAILED,second.state());second.close();f.locked();
            var before=V53ReplayFilesTest.files(f.group.fixture.request.targets().getFirst().replicaDirectory());
            first.close();f.released();assertEquals(0,first.usage().leases());
            var fresh=f.node();fresh.open();assertEquals(MembershipAutomaticOwner.State.NEW,fresh.serviceState().orElseThrow());
            assertThrows(IllegalArgumentException.class,fresh::readiness);assertThrows(IllegalArgumentException.class,()->fresh.submit("DATA",new byte[]{1}));
            assertEquals(before,V53ReplayFilesTest.files(f.group.fixture.request.targets().getFirst().replicaDirectory()));
            assertThrows(IllegalArgumentException.class,first::open);
        }
    }
    @Test void failedBindKeepsAnExplicitCloseableOwnerAndCanReopenAfterDrain()throws Exception {
        try(var f=new Fixture()) {
            var node=f.node();var address=f.group.identities.getFirst().endpoint();
            try(var occupied=new ServerSocket(address.port(),1,InetAddress.getByName(address.host()))) {
                assertThrows(BindException.class,node::open);assertEquals(MembershipNodeOwner.State.FAILED,node.state());f.locked();
                assertTrue(node.usage().leases()>0);node.close();f.released();assertEquals(0,node.usage().leases());
            }
            var fresh=f.node();fresh.open();assertEquals(MembershipNodeOwner.State.OPEN,fresh.state());
        }
    }
    @Test void closeBeforeOpenCannotStartOrAcquireStorage()throws Exception {
        try(var f=new Fixture()) {
            var node=f.node();node.close();assertEquals(MembershipNodeOwner.State.CLOSED,node.state());
            assertThrows(IllegalArgumentException.class,node::open);assertThrows(IllegalArgumentException.class,node::start);f.released();
        }
    }
    @Test void seedMismatchFailsBeforeBindingAndNeverChangesTheDirectory()throws Exception {
        try(var f=new Fixture()) {
            var config=f.config(ReplicationBounds.defaults());var known=config.seedPeers().getFirst();
            var foreign=new MembershipIdentity(known.nodeId(),UUID.randomUUID(),known.endpoint());
            var bad=new MembershipReplicaConfig<>(config.root(),config.localIdentity(),List.of(foreign),config.replicaDirectory(),config.materialization(),config.bounds(),config.leadershipPolicy());
            try(var node=new MembershipNodeOwner<>(bad,builder().configuration(),f.scratch.resolve("bad-in"),f.scratch.resolve("bad-out"),System::nanoTime,TimeUnit.SECONDS.toNanos(180),MembershipNodeOwner.Hooks.NONE)) {
                assertEquals("node seed differs from original identity",assertThrows(IllegalArgumentException.class,node::open).getMessage());
                assertFalse(Files.exists(f.scratch.resolve("bad-in")));f.locked();
            }
            f.released();
        }
    }
    @Test void cancellationDuringOpenRetainsTheDirectoryUntilTheOpeningWriterStops()throws Exception {
        try(var f=new Fixture()) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var held=new AtomicBoolean();
            var node=f.node(shortClose(),hooks(event->{if(event.equals("CURRENT_VALIDATED") && held.compareAndSet(false,true))hold(entered,release);},MembershipTransport.Events.NONE));
            var result=new CompletableFuture<Throwable>();Thread opener=Thread.ofPlatform().start(()->{try{node.open();result.complete(null);}catch(Throwable error){result.complete(error);}});
            try {
                assertTrue(entered.await(10,TimeUnit.SECONDS));assertEquals("node open drain deadline",assertThrows(IOException.class,node::close).getMessage());f.locked();
                assertEquals(MembershipNodeOwner.State.CLOSING,node.state());
            }finally{release.countDown();opener.join(10000);}
            assertFalse(opener.isAlive());assertEquals("node open cancelled",result.get(1,TimeUnit.SECONDS).getMessage());f.locked();
            node.close();f.released();assertEquals(0,node.usage().leases());
        }
    }
    @Test void undrainedTransportCannotReleaseStorageAndSecondCloseCanFinish()throws Exception {
        try(var f=new Fixture()) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            var node=f.node(shortClose(),hooks(event->{},(event,request,response)->{if(event.equals("AFTER_REQUEST_READ"))hold(entered,release);}));node.open();
            var client=f.group.start(1);var result=client.exchange(f.group.identities.getFirst(),f.group.request(1,0),"STATUS",V53MembershipTransportTest.deadline());
            try {
                assertTrue(entered.await(5,TimeUnit.SECONDS));assertEquals("node transport drain failed",assertThrows(IOException.class,node::close).getMessage());f.locked();
                assertEquals(MembershipNodeOwner.State.CLOSING,node.state());assertTrue(node.usage().leases()>0);
            }finally{release.countDown();}
            assertThrows(ExecutionException.class,()->result.get(5,TimeUnit.SECONDS));node.close();f.released();
            var fresh=f.node();fresh.open();assertEquals(MembershipNodeOwner.State.OPEN,fresh.state());
        }
    }
    @Test void closeFromTransportCallbackDoesNotTreatCancellationAsDrain()throws Exception {
        try(var f=new Fixture()) {
            var holder=new AtomicReference<MembershipNodeOwner<Integer,Doc>>();var closed=new CompletableFuture<Throwable>();
            var node=f.node(ReplicationBounds.defaults(),hooks(event->{},(event,request,response)->{
                if(event.equals("AFTER_REQUEST_READ"))try{holder.get().close();closed.complete(null);}catch(Throwable error){closed.complete(error);}
            }));holder.set(node);node.open();var client=f.group.start(1);
            var reply=client.exchange(f.group.identities.getFirst(),f.group.request(1,0),"STATUS",V53MembershipTransportTest.deadline());
            var error=assertInstanceOf(IOException.class,closed.get(10,TimeUnit.SECONDS));assertEquals("node transport drain failed",error.getMessage());
            assertEquals("transport callback has not drained",error.getCause().getMessage());f.locked();
            assertThrows(ExecutionException.class,()->reply.get(5,TimeUnit.SECONDS));node.close();f.released();
        }
    }
    @Test void closeDuringAutomaticWaitCannotAllocateOrLeaveLiveWork()throws Exception {
        try(var f=new Fixture()) {
            var sends=new AtomicInteger();var node=f.node(ReplicationBounds.defaults(),hooks(event->{},(event,request,response)->{if(event.equals("BEFORE_REQUEST_WRITE"))sends.incrementAndGet();}));
            node.open();var before=V53ReplayFilesTest.files(f.group.fixture.request.targets().getFirst().replicaDirectory());
            var result=node.start();waitFor(()->node.serviceState().orElseThrow()==MembershipAutomaticOwner.State.STARTING);node.close();
            assertThrows(ExecutionException.class,()->result.await(5,TimeUnit.SECONDS));assertEquals(0,sends.get());assertEquals(0,node.usage().leases());
            assertEquals(before,V53ReplayFilesTest.files(f.group.fixture.request.targets().getFirst().replicaDirectory()));f.released();
        }
    }
    @Test void failedGrantWriterMustDrainBeforeColdOpenAndNeverRestoresReady()throws Exception {
        try(var f=new Fixture()) {
            var cut=new AtomicBoolean();var bounds=shortClose();
            var failed=f.node(bounds,hooks(event->{if(event.equals("PROMISE_WRITTEN") && cut.compareAndSet(false,true))throw new IOException("injected grant write failure");},MembershipTransport.Events.NONE));
            failed.open();f.node(1,bounds,MembershipNodeOwner.Hooks.NONE).open();f.node(2,bounds,MembershipNodeOwner.Hooks.NONE).open();
            var reply=failed.start();assertThrows(ExecutionException.class,()->reply.await(15,TimeUnit.SECONDS));assertTrue(cut.get());
            waitFor(()->failed.serviceState().orElseThrow()==MembershipAutomaticOwner.State.FAILED);f.locked();
            assertThrows(IllegalArgumentException.class,failed::readiness);failed.close();f.released();assertEquals(0,failed.usage().leases());
            var reopened=f.node(bounds,MembershipNodeOwner.Hooks.NONE);reopened.open();
            assertEquals(MembershipAutomaticOwner.State.NEW,reopened.serviceState().orElseThrow());assertThrows(IllegalArgumentException.class,reopened::readiness);
            assertThrows(IllegalArgumentException.class,failed::start);
        }
    }
}
