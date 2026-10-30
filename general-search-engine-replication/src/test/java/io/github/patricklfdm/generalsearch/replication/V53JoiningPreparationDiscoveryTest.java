package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Conditional original files and actual PREPARE/read handlers. Discovery is
 * routing only and does not qualify native initialization or public readiness. */
class V53JoiningPreparationDiscoveryTest {
    @TempDir Path temp;
    final class Local implements AutoCloseable {
        final V53JoiningRetentionCampaignTest.Local old;
        final MembershipResources pool=resources();
        final MembershipGrantJournal reader;
        final Path readerPath;
        final MembershipActivation prepared;
        final MembershipJoiningPreparation publication;
        final MembershipJoiningRetentionCampaign.Hint hint;
        final AtomicReference<MembershipSourcePull.Link> link=new AtomicReference<>();
        final AtomicBoolean allowed=new AtomicBoolean(true);
        final List<MembershipFormat.Decoded> sent=new ArrayList<>();
        Local(int size,String kind,boolean publish)throws Exception {
            var helper=new V53JoiningRetentionCampaignTest();helper.temp=temp;old=helper.new Local(size,kind);
            readerPath=temp.resolve("reader-"+UUID.randomUUID());old.fixture.provision(readerPath);var identity=V53DeclarationsTest.node(6);
            V53JoiningRetentionNetworkTest.identity(readerPath,identity);
            reader=MembershipGrantJournal.openGenerations(readerPath,old.fixture.root(),identity,pool,old.fixture::verify,e->{});
            if(publish) {
                prepared=new MembershipActivation(old.owners.get(1),old.pools.get(1),old.clock::get,0,BUDGET);old.endpoints.get(1).serve(prepared);
                try(var step=new MembershipJoiningRetentionCampaign.OldSide(prepared,old.owners.get(1),old.pools.get(1),bounds(),
                        (p,q,k,d)->old.deliver(1,p,q,k,d),()->{},old.clock::get,0,BUDGET,identity)) {hint=step.run();}
                publication=new MembershipJoiningPreparation(old.owners.get(1),old.pools.get(1),hint,()->{},old.clock::get,0,BUDGET);
                old.endpoints.get(1).publishJoiningPreparation(publication);
            }else{prepared=null;publication=null;hint=null;}
            link.set(this::deliver);
        }
        CompletableFuture<Decoded> deliver(MembershipIdentity peer,Decoded request,String kind,long deadline) {
            assertEquals(BUDGET,deadline);
            try {var reply=old.endpoints.get(Integer.parseInt(peer.nodeId().value().substring(5))-1).handle(reader.activationIdentity(),request);
                return CompletableFuture.completedFuture(reply);
            }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        }
        MembershipJoiningPreparationDiscovery discovery()throws IOException {
            return new MembershipJoiningPreparationDiscovery(reader,pool,bounds(),(p,q,k,d)->{sent.add(q);return link.get().exchange(p,q,k,d);},
                    ()->{if(!allowed.get())throw new IOException("original preparation revoked");},old.clock::get,0,BUDGET);
        }
        List<String> destinations(){return sent.stream().map(q->MembershipContext.identity(object(q.value().get("recipient"))).nodeId().value()).toList();}
        @Override public void close()throws Exception {
            if(publication!=null)old.endpoints.get(1).revokeJoiningPreparation(publication);if(prepared!=null)prepared.close();
            reader.close();old.close();assertEquals(0,pool.usage().leases());
        }
    }
    static Decoded reject(Decoded request,String reason,boolean foreign) {
        var fields=new TreeMap<>(request.value());fields.put("sender",request.value().get("recipient"));fields.put("recipient",request.value().get("sender"));
        fields.put("payload",Map.of("reason",reason,"promised",request.value().get("ballot")));if(foreign)fields.put("trace",UUID.randomUUID().toString());
        return decode(encode("wire","REJECT",fields),"wire","REJECT");
    }
    @Test void everyJoiningProfileFindsAnotherOldProposerWithoutObservingOrSelecting()throws Exception {
        for(var profile:V53SelectionTest.PROFILES)if(!profile.getValue().equals("REMOVE"))try(var l=new Local(profile.getKey(),profile.getValue(),true)) {
            var before=V53ReplayFilesTest.files(l.readerPath);var state=l.reader.discoveryState(l.pool);var usage=l.pool.usage();
            try(var discovery=l.discovery()) {
                assertEquals(l.hint,discovery.find());assertEquals("node-1",l.destinations().getFirst());
                assertTrue(l.destinations().subList(1,l.sent.size()).stream().allMatch("node-2"::equals));
                assertTrue(l.sent.stream().allMatch(q->Set.of("CHUNK","TRANSFER_COMMIT").contains(q.kind())));
                assertThrows(IllegalArgumentException.class,discovery::find);
                assertEquals(before,V53ReplayFilesTest.files(l.readerPath));assertEquals(state,l.reader.discoveryState(l.pool));
                assertEquals(MembershipActivation.State.PREPARING,l.prepared.state());assertTrue(l.old.owners.get(1).originalSelection().isEmpty());
            }
            assertEquals(usage,l.pool.usage());
        }
    }
    @Test void unavailableTransportRepeatsOnlyTheSameRequestBeforeTryingAnotherPeer()throws Exception {
        try(var l=new Local(3,"ADD",true);var discovery=l.discovery()) {
            l.link.set((p,q,k,d)->p.nodeId().value().equals("node-1")?CompletableFuture.failedFuture(lost()):l.deliver(p,q,k,d));
            assertEquals(l.hint,discovery.find());var failed=l.sent.stream().filter(q->MembershipContext.identity(object(q.value().get("recipient"))).nodeId().value().equals("node-1")).toList();
            assertEquals(3,failed.size());assertEquals(1,failed.stream().map(Decoded::digest).distinct().count());
        }
    }
    @Test void explicitFailuresAndForeignNotReadyNeverRotateToAnotherPeer()throws Exception {
        for(String reason:List.of("CAPACITY_EXCEEDED","INTEGRITY_FAILURE","STALE_EPOCH","FOREIGN_IDENTITY","PROTOCOL_MISMATCH","REMOVED","foreign"))
            try(var l=new Local(3,"ADD",true);var discovery=l.discovery()) {
                l.link.set((p,q,k,d)->CompletableFuture.completedFuture(reject(q,reason.equals("foreign")?"NOT_READY":reason,reason.equals("foreign"))));
                assertThrows(Exception.class,discovery::find,reason);assertEquals(1,l.sent.size(),reason);
            }
    }
    @Test void allAbsentIsOneBoundedPassAndLeavesEveryOriginalUntouched()throws Exception {
        try(var l=new Local(5,"REPLACE",false)) {
            var before=V53ReplayFilesTest.files(l.readerPath);var usage=l.pool.usage();
            try(var discovery=l.discovery()){assertThrows(IOException.class,discovery::find);assertEquals(List.of("node-1","node-2","node-3","node-4","node-5"),l.destinations());}
            assertEquals(before,V53ReplayFilesTest.files(l.readerPath));assertEquals(usage,l.pool.usage());
        }
    }
    @Test void midTransferAbsenceNeverSelectsAnotherProposer()throws Exception {
        for(String stage:List.of("data","commit"))try(var l=new Local(3,"ADD",true);var discovery=l.discovery()) {
            l.link.set((p,q,k,d)->p.nodeId().value().equals("node-2") &&
                    (stage.equals("data")?number(q.value().get("sequence"))==2:q.kind().equals("TRANSFER_COMMIT"))
                    ?CompletableFuture.completedFuture(reject(q,"NOT_READY",false)):l.deliver(p,q,k,d));
            var error=assertThrows(MembershipSourcePull.Rejected.class,discovery::find);
            assertTrue(number(error.response.value().get("sequence"))>1);assertFalse(l.destinations().contains("node-3"));
        }
    }
    @Test void localTransportFaultsAndUnknownIoDoNotBecomeAbsence()throws Exception {
        for(var fault:List.of(new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"injected",null),
                new MembershipTransport.Failure(MembershipTransport.Reason.CLOSED,"injected",null),new IOException("unclassified local I/O")))
            try(var l=new Local(3,"ADD",false);var discovery=l.discovery()) {
                l.link.set((p,q,k,d)->CompletableFuture.failedFuture(fault));assertSame(fault,assertThrows(IOException.class,discovery::find));
                assertEquals(1,l.sent.size());
            }
    }
    @Test void deadlineAndOriginalGuardCannotBeRenewedByAbsenceReplies()throws Exception {
        for(boolean expiry:List.of(false,true))try(var l=new Local(3,"ADD",true);var discovery=l.discovery()) {
            l.link.set((p,q,k,d)->l.deliver(p,q,k,d).thenApply(reply->{if(expiry)l.old.clock.set(BUDGET);else l.allowed.set(false);return reply;}));
            assertThrows(Exception.class,discovery::find);assertEquals(1,l.sent.size());
        }
    }
    @Test void closeCancelsPendingReadAndReturnsResourcesAfterItsWorkerExits()throws Exception {
        try(var l=new Local(3,"ADD",true)) {
            var usage=l.pool.usage();var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            l.link.set((p,q,k,d)->{entered.countDown();return pending;});
            try(var discovery=l.discovery();var threads=Executors.newVirtualThreadPerTaskExecutor()) {
                var running=threads.submit(discovery::find);assertTrue(entered.await(5,TimeUnit.SECONDS));discovery.close();
                assertTrue(pending.isCancelled());assertThrows(ExecutionException.class,()->running.get(5,TimeUnit.SECONDS));
            }
            assertEquals(usage,l.pool.usage());
        }
    }
    @Test void malformedAbsenceRequestsDoNotReceiveNotReady()throws Exception {
        try(var l=new Local(3,"ADD",false)) {
            var context=l.reader.activationContext();var peer=l.old.owners.getFirst().activationIdentity();
            for(String fault:List.of("offset","view","sender","root")) {
                var q=MembershipActivation.frame("CHUNK",context,l.reader.activationIdentity(),peer,l.reader.discoveryState(l.pool).ballot(),UUID.randomUUID(),1,
                        Map.of("action","REQUEST","id",UUID.randomUUID().toString(),"offset",fault.equals("offset")?1L:0L,"bytes","",
                                "digest",MembershipJoiningPreparation.reference(context,l.reader.activationIdentity())));
                var values=new TreeMap<>(q.value());if(fault.equals("root"))values.put("root","ff".repeat(32));if(fault.equals("view"))values.put("view","ff".repeat(32));
                if(fault.equals("sender"))values.put("sender",MembershipBootstrapSeed.identity(peer));
                var changed=decode(encode("wire","CHUNK",values),"wire","CHUNK");
                assertThrows(IllegalArgumentException.class,()->l.old.endpoints.getFirst().handle(l.reader.activationIdentity(),changed),fault);
            }
        }
    }
}
