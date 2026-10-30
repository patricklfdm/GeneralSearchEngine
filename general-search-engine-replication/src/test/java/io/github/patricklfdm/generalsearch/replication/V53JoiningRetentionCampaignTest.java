package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.identity;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Conditional joint grants exercise the actual old-side exchange, never the
 * native maintenance prelude or original joining initialization capability. */
class V53JoiningRetentionCampaignTest {
    @TempDir Path temp;
    final class Local implements AutoCloseable {
        final V53CurrentGenerationFixture fixture;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<Path> directories=new ArrayList<>();
        final List<MembershipResources> pools=new ArrayList<>();
        final List<MembershipActivationEndpoint> endpoints=new ArrayList<>();
        final ExecutorService executor=Executors.newVirtualThreadPerTaskExecutor();
        final AtomicLong clock=new AtomicLong();
        final List<Decoded> requests=new ArrayList<>();
        final AtomicReference<MembershipSourcePull.Link> link=new AtomicReference<>();
        final MembershipActivation campaign;
        Local(int size,String kind)throws Exception {
            fixture=new V53CurrentGenerationFixture(size,new V53CapsuleFixture(size,kind,6));
            Path base=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            for(int i=1;i<=size;i++) {
                Path path=base.resolve("node-"+i);directories.add(path);fixture.provision(path);var identity=V53DeclarationsTest.node(i);
                V53JoiningRetentionNetworkTest.identity(path,identity);var pool=resources();pools.add(pool);
                owners.add(MembershipGrantJournal.openGenerations(path,fixture.root(),identity,pool,fixture::verify,e->{}));
            }
            for(int i=0;i<size;i++) {int from=i;
                endpoints.add(new MembershipActivationEndpoint(owners.get(i),pools.get(i),bounds(),(p,q,k,d)->deliver(from,p,q,k,d),
                        fixture::verify,List.of(),List.of(),base.resolve("endpoint-"+i),clock::get,BUDGET));
            }
            campaign=new MembershipActivation(owners.getFirst(),pools.getFirst(),clock::get,0,BUDGET);endpoints.getFirst().serve(campaign);
            link.set((p,q,k,d)->deliver(0,p,q,k,d));
        }
        CompletableFuture<Decoded> deliver(int from,MembershipIdentity peer,Decoded q,String kind,long deadline) {
            assertEquals(BUDGET,deadline);
            return CompletableFuture.supplyAsync(()->{try{return endpoints.get(Integer.parseInt(peer.nodeId().value().substring(5))-1)
                    .handle(owners.get(from).activationIdentity(),q);}catch(IOException e){throw new CompletionException(e);}},executor);
        }
        MembershipJoiningRetentionCampaign.OldSide step()throws Exception{return step(bounds());}
        MembershipJoiningRetentionCampaign.OldSide step(ReplicationBounds bound)throws Exception {
            return new MembershipJoiningRetentionCampaign.OldSide(campaign,owners.getFirst(),pools.getFirst(),bound,
                    (p,q,k,d)->{requests.add(q);return link.get().exchange(p,q,k,d);},()->{},clock::get,0,BUDGET,V53DeclarationsTest.node(6));
        }
        @Override public void close()throws Exception {
            campaign.close();for(var endpoint:endpoints)endpoint.close();executor.shutdownNow();assertTrue(executor.awaitTermination(10,TimeUnit.SECONDS));
            for(var owner:owners)owner.close();for(var pool:pools)assertEquals(0,pool.usage().leases());
        }
    }
    @Test void allJoiningProfilesPrepareOnlyOldMajorityWithoutSelectingOrCallingJoiningNode()throws Exception {
        for(var profile:V53SelectionTest.PROFILES) {
            if(profile.getValue().equals("REMOVE"))continue;
            try(var l=new Local(profile.getKey(),profile.getValue());var step=l.step()) {
                var hint=step.run();assertEquals(profile.getKey()/2+1,hint.sources().size());
                assertEquals(MembershipActivation.State.PREPARING,l.campaign.state());
                assertTrue(l.requests.stream().allMatch(q->q.kind().equals("PREPARE")));assertEquals(profile.getKey()/2,l.requests.size());
                for(var owner:l.owners)assertTrue(owner.originalSelection().isEmpty());
                for(String node:hint.sources().keySet()) {
                    var owner=l.owners.get(Integer.parseInt(node.substring(5))-1);var basis=owner.originalSource().basis;
                    assertEquals(basis.digest(),hint.sources().get(node));assertEquals(hint.ballot(),basis.value().get("ballot"));
                    hint.fragment(l.campaign.ownSource().capsule.context,V53DeclarationsTest.node(6),owner.activationIdentity(),basis);
                }
                assertThrows(IllegalArgumentException.class,step::run);
            }
        }
    }
    @Test void lostReplyRepeatsExactPrepareAndExhaustedTransportUsesAnotherOldVoter()throws Exception {
        for(boolean exhausted:List.of(false,true))try(var l=new Local(3,"ADD");var step=l.step()) {
            var normal=l.link.get();var attempts=new AtomicInteger();
            l.link.set((p,q,k,d)->normal.exchange(p,q,k,d).thenCompose(reply->{
                if(p.nodeId().value().equals("node-2") && (attempts.getAndIncrement()==0 || exhausted))return CompletableFuture.failedFuture(lost());
                return CompletableFuture.completedFuture(reply);
            }));
            var hint=step.run();assertEquals(Set.of("node-1",exhausted?"node-3":"node-2"),hint.sources().keySet());
            var repeats=l.requests.stream().filter(q->identity(object(q.value().get("recipient"))).nodeId().value().equals("node-2")).toList();
            assertEquals(exhausted?3:2,repeats.size());assertEquals(1,repeats.stream().map(Decoded::digest).distinct().count());
            assertEquals(11L,number(hint.ballot().get("counter")));assertEquals(MembershipActivation.State.PREPARING,l.campaign.state());
        }
    }
    @Test void stricterAttemptBudgetAndUnavailableMajorityRemainBounded()throws Exception {
        try(var l=new Local(3,"REPLACE")) {
            var b=bounds();var once=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),1,
                    b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
            l.link.set((p,q,k,d)->CompletableFuture.failedFuture(lost()));
            try(var step=l.step(once)){assertThrows(IllegalArgumentException.class,step::run);assertEquals(2,l.requests.size());}
            assertTrue(l.owners.getFirst().originalSelection().isEmpty());
        }
    }
    @Test void rejectionAndMalformedCorrelationNeverBecomeAnotherSourceOrRenewABallot()throws Exception {
        for(String fault:List.of("reject","higher","correlation","capacity","closed"))try(var l=new Local(3,"ADD");var step=l.step()) {
            l.link.set((p,q,k,d)->{
                if(Set.of("capacity","closed").contains(fault))return CompletableFuture.failedFuture(new MembershipTransport.Failure(
                        fault.equals("capacity")?MembershipTransport.Reason.CAPACITY:MembershipTransport.Reason.CLOSED,"injected",null));
                return CompletableFuture.completedFuture(V53ActivationDriverTest.reject(q,"NOT_READY",fault.equals("higher"),fault.equals("correlation")));
            });
            assertThrows(Exception.class,step::run);assertEquals(1,l.requests.size());assertTrue(l.owners.getFirst().originalSelection().isEmpty());
            if(fault.equals("higher"))assertEquals(12L,number(l.owners.getFirst().discoveryState(l.pools.getFirst()).ballot().get("counter")));
        }
    }
    @Test void originalDeadlineAndHigherFenceRejectLatePreparedReplies()throws Exception {
        for(boolean higher:List.of(false,true))try(var l=new Local(3,"ADD");var step=l.step()) {
            var normal=l.link.get();l.link.set((p,q,k,d)->normal.exchange(p,q,k,d).thenApply(reply->{
                if(higher){var ballot=new TreeMap<>(l.campaign.ballot());ballot.put("counter",number(ballot.get("counter"))+1);l.owners.getFirst().observeCurrent(ballot);}
                else l.clock.set(BUDGET);return reply;
            }));
            assertThrows(IllegalArgumentException.class,step::run);assertEquals(1,l.requests.size());assertTrue(l.owners.getFirst().originalSelection().isEmpty());
        }
    }
    @Test void closeCancelsPendingExchangeAndReleasesOnlyItsOwnControlCharge()throws Exception {
        try(var l=new Local(3,"ADD");var step=l.step()) {
            var before=l.pools.getFirst().usage();
            var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();l.link.set((p,q,k,d)->{entered.countDown();return pending;});
            var task=l.executor.submit(step::run);assertTrue(entered.await(5,TimeUnit.SECONDS));step.close();
            assertThrows(ExecutionException.class,()->task.get(5,TimeUnit.SECONDS));assertTrue(pending.isCancelled());
            assertEquals(before.queued()+l.requests.getFirst().size(),l.pools.getFirst().usage().queued(),"only the enclosing campaign still owns its PREPARE header");
            assertTrue(l.owners.getFirst().originalSelection().isEmpty());
        }
    }
    @Test void nativePreludeRefusesConditionalHistoryBeforeAllocatingAnotherBallot()throws Exception {
        try(var l=new Local(3,"ADD")) {
            var before=V53ReplayFilesTest.files(l.directories.getFirst());var usage=l.pools.getFirst().usage();
            try(var nativeStep=new MembershipJoiningRetentionCampaign(l.owners.getFirst(),l.endpoints.getFirst(),l.pools.getFirst(),bounds(),
                    (p,q,k,d)->{throw new AssertionError("conditional history must not reach native preparation I/O");},()->{},
                    temp.resolve("native-prelude"),l.clock::get,0,BUDGET,V53DeclarationsTest.node(6))) {
                assertThrows(IllegalArgumentException.class,nativeStep::run);
            }
            assertEquals(before,V53ReplayFilesTest.files(l.directories.getFirst()));assertEquals(usage,l.pools.getFirst().usage());
        }
    }
    @Test void hintIsBoundToOriginalMajorityCutIdentityBallotAndBasisBytes()throws Exception {
        var in=V53JoiningRetentionSeedTest.input(3,"ADD");var c=in.current().context;var sources=new TreeMap<String,String>();
        for(var source:in.sources())sources.put(source.owner.nodeId().value(),source.basis.digest());
        var original=new MembershipJoiningRetentionCampaign.Hint(c.root,MembershipContext.cutDigest(c.cut),in.joining(),object(in.sources().getFirst().basis.value().get("ballot")),sources);
        for(var source:in.sources())assertDoesNotThrow(()->original.fragment(c,in.joining(),source.owner,source.basis));
        assertThrows(IllegalArgumentException.class,()->original.check(c,V53DeclarationsTest.node(3)));
        for(String fault:List.of("cut","basis","minority","ballot","non-old")) {
            var changed=new TreeMap<>(sources);var ballot=new TreeMap<>(original.ballot());String cut=original.cut();
            switch(fault){case "cut"->cut="ff".repeat(32);case "basis"->changed.put("node-1","ff".repeat(32));case "minority"->changed.remove("node-2");
                case "ballot"->ballot.put("counter",number(ballot.get("counter"))+1);case "non-old"->{changed.remove("node-2");changed.put("node-6","ff".repeat(32));}}
            var hint=new MembershipJoiningRetentionCampaign.Hint(c.root,cut,in.joining(),ballot,changed);
            assertThrows(IllegalArgumentException.class,()->hint.fragment(c,in.joining(),in.sources().getFirst().owner,in.sources().getFirst().basis));
        }
    }
}
