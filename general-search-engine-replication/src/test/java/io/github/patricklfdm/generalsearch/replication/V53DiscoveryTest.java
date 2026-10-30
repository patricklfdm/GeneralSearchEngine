package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53DiscoveryTest {
    @TempDir Path temp;
    final class Local implements AutoCloseable {
        final V53MembershipTransportTest.Group group;
        final MembershipResources budget=resources();
        final MembershipGrantJournal owner;
        final AtomicLong clock=new AtomicLong();
        final List<Decoded> requests=new ArrayList<>();
        final List<Long> deadlines=new ArrayList<>();
        final List<String> events=new ArrayList<>();
        final Map<String,Object> ballot;
        Local()throws Exception {
            var helper=new V53MembershipTransportTest();helper.temp=temp;group=helper.new Group(3);var t=group.fixture.request.targets().getFirst();
            owner=MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),group.fixture.result.root(),t.identity(),budget,
                    V53ActivationEndpointTest.verifier(),MembershipGrantJournal.MAXIMUM,events::add);
            ballot=owner.discoveryState(budget).ballot();events.clear();
        }
        MembershipDiscovery query(MembershipSourcePull.Link link,ReplicationBounds bounds)throws Exception {
            return new MembershipDiscovery(owner,budget,bounds,(p,r,k,d)->{requests.add(r);deadlines.add(d);return link.exchange(p,r,k,d);},()->{},clock::get,0,BUDGET);
        }
        MembershipDiscovery query(MembershipSourcePull.Link link)throws Exception{return query(link,V53TransferServiceTest.bound(2));}
        MembershipIdentity peer(){return group.identities.get(1);}
        Decoded response(Decoded request){return MembershipDiscovery.answer(group.capsule.context,peer(),group.identities.getFirst(),request);}
        CompletableFuture<Decoded> normal(MembershipIdentity p,Decoded r,String k,long d){return CompletableFuture.completedFuture(response(r));}
        Map<String,String> files()throws Exception{return V53ReplayFilesTest.files(group.fixture.request.targets().getFirst().replicaDirectory());}
        @Override public void close()throws Exception {owner.close();group.close();assertEquals(0,budget.usage().leases());}
    }
    @Test void exactRevocationKeepsCancellationAndGenericCancellationCannotImpersonateIt()throws Exception {
        try(var l=new Local()) {
            var lost=new MembershipCampaignLost(MembershipCampaignLost.Reason.HIGHER_BALLOT,"original parent revoked");
            for(boolean typed:List.of(false,true)) {
                var cancelled=typed?new MembershipCampaignLost.Cancelled(lost):new CancellationException("original campaign revoked");
                if(!typed)cancelled.initCause(lost);
                var future=CompletableFuture.<Decoded>failedFuture(cancelled);assertTrue(future.isCancelled());
                try(var query=l.query((p,r,k,d)->future)) {
                    var actual=assertThrows(IOException.class,()->query.query(l.peer()));
                    if(typed)assertSame(lost,actual);else assertFalse(actual instanceof MembershipCampaignLost);
                }
            }
        }
    }
    @Test void realTcpDiscoveryReadsPublishedStorageAtEveryStableSizeWithoutAnyForce()throws Exception {
        var evidence=Files.createDirectories(Path.of("target/v53-discovery/run-"+UUID.randomUUID()));System.out.println("v53DiscoveryEvidence="+evidence.toAbsolutePath());
        var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            var raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;f.campaign(1);f.publish(1,false);
                var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();var endpoints=new ArrayList<MembershipActivationEndpoint>();
                var wire=new ArrayList<Map<String,Object>>();var events=new ArrayList<String>();
                try {
                    for(var t:f.request.targets()) {
                        var budget=resources();budgets.add(budget);
                        var owner=MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),budget,
                                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,events::add);owners.add(owner);
                        var endpoint=new MembershipActivationEndpoint(owner,budget,V53TransferServiceTest.bound(2),
                                (p,r,k,d)->{throw new AssertionError("status must not fetch a source");},
                                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),List.of(),List.of(),temp.resolve("status-endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);
                        endpoints.add(endpoint);group.start(owners.size()-1,endpoint,MembershipTransport.Events.NONE,V53TransferServiceTest.bound(2),budget);
                    }
                    events.clear();
                    for(int from=0;from<size;from++)for(int to=0;to<size;to++)if(from!=to) {
                        var transport=group.transports.get(from);MembershipSourcePull.Link link=(p,r,k,d)->transport.exchange(p,r,k,d).thenApply(reply->{wire.add(V53SelectedPullTest.wire(r,reply));return reply;});
                        try(var query=new MembershipDiscovery(owners.get(from),budgets.get(from),V53TransferServiceTest.bound(2),link,()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                            var hint=query.query(group.identities.get(to));assertEquals(owners.get(to).activationContext().cut,hint.cut());assertFalse(hint.ready());
                        }
                    }
                    assertTrue(events.isEmpty(),"status must not perform a durable force");
                }finally {for(var t:group.transports)t.close();for(var endpoint:endpoints)endpoint.close();for(var owner:owners)owner.close();}
                f.snapshot("after");Files.write(raw.resolve("wire.json"),canonical(wire,4*1024*1024));
                Files.write(raw.resolve("events.json"),canonical(events,65536));cases.add(Map.of("size",size,"exchanges",wire.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-discovery-v1","status","PASS","cases",cases,
                "network",true,"publicRuntime",false,"adoption",false,"scope","read-only-published-cut-discovery"),65536));
    }
    @Test void actualOwnerAnswersStaleViewWithoutPromiseOrCounterChanges()throws Exception {
        try(var l=new Local()) {
            var before=l.files();var raw=new TreeMap<>(l.group.request(1,0).value());raw.put("view","f".repeat(64));
            var correlation=new TreeMap<>(object(raw.get("ballot")));correlation.put("counter",MembershipValidation.MAX);raw.put("ballot",correlation);
            var request=decode(encode("wire","STATUS_PROBE",raw),"wire","STATUS_PROBE");var response=l.owner.discoveryStatus(l.peer(),request);
            MembershipWire.correlated(request,response,"STATUS");assertEquals(l.group.capsule.context.cut,object(response.value().get("payload")).get("cut"));
            assertEquals(before,l.files());assertTrue(l.events.isEmpty());
            // Read-only discovery correlation did not fence a subsequent real lower campaign.
            assertNotNull(l.owner.beginActivation());
        }
    }
    @Test void realActivationEndpointDiscoversWithoutOpeningOrRevivingCampaignScope()throws Exception {
        var helper=new V53ActivationDriverTest();helper.temp=temp;
        try(var l=helper.local()) {
            var endpoint=l.endpoints.getFirst();var owner=l.owners.getFirst();var request=l.group.request(1,0);
            var path=l.group.fixture.request.targets().getFirst().replicaDirectory();var before=V53ReplayFilesTest.files(path);
            var usage=endpoint.usage();var reply=endpoint.handle(l.group.identities.get(1),request);
            assertEquals(owner.activationContext().cut,object(reply.value().get("payload")).get("cut"));
            assertEquals(usage,endpoint.usage());assertEquals(before,V53ReplayFilesTest.files(path));
            try(var driver=l.driver(2)) {
                driver.run();endpoint.abandon(object(driver.selection().value().get("ballot")));
                before=V53ReplayFilesTest.files(path);usage=endpoint.usage();assertTrue(usage.scopeEnded());
                endpoint.handle(l.group.identities.get(1),request);assertEquals(usage,endpoint.usage());assertEquals(before,V53ReplayFilesTest.files(path));
            }
            endpoint.close();assertThrows(IllegalArgumentException.class,()->endpoint.handle(l.group.identities.get(1),request));
        }
    }
    @Test void removedHistoricalIdentitiesDiscoverJointAndFinalViewsWithoutVoting()throws Exception {
        for(int through:List.of(6,7)) {
            var f=new V53CapsuleFixture(3,"REPLACE",through);var c=f.verify().context;var local=c.identities.get("node-1");
            var historical=c.identities.get("node-3");var ballot=Map.of("counter",10L,"proposer","node-3","incarnation",historical.storageId().toString());
            var request=decode(encode("wire","STATUS_PROBE",Map.of("root",c.root,"view","e".repeat(64),"ballot",ballot,
                    "sender",MembershipBootstrapSeed.identity(historical),"recipient",MembershipBootstrapSeed.identity(local),"trace",UUID.randomUUID().toString(),
                    "sequence",1L,"payload",Map.of("nonce",UUID.randomUUID().toString()))),"wire","STATUS_PROBE");
            var reply=MembershipDiscovery.answer(c,local,historical,request);assertEquals(c.cut,object(reply.value().get("payload")).get("cut"));
            assertFalse((boolean)object(reply.value().get("payload")).get("ready"));
            if(through==7)assertFalse(c.voters().contains("node-3"));
        }
    }
    @Test void actualAdoptedOwnerReportsItsForcedNewViewAndPreservesAllBytes()throws Exception {
        // Conditional membership certificates belong to the storage fixture, not
        // the original-bootstrap TCP evidence or a complete distributed transition.
        for(int through:List.of(6,7)) {
            var f=new V53AdoptionFenceFixture(3,through);var path=temp.resolve("adopted-"+through);f.provision(path);var budget=resources();
            try(var owner=f.open(path,budget,e->{})) {
                owner.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());var current=owner.activationContext();
                var before=V53ReplayFilesTest.files(path);var sender=current.identities.get("node-3");
                var request=decode(encode("wire","STATUS_PROBE",Map.of("root",current.root,"view",f.initial.fixture.verify().context.authority(),
                        "sender",MembershipBootstrapSeed.identity(sender),"recipient",MembershipBootstrapSeed.identity(owner.activationIdentity()),
                        "ballot",Map.of("counter",1L,"proposer","node-3","incarnation",sender.storageId().toString()),
                        "trace",UUID.randomUUID().toString(),"sequence",1L,"payload",Map.of("nonce",UUID.randomUUID().toString()))),"wire","STATUS_PROBE");
                var reply=owner.discoveryStatus(sender,request);assertEquals(current.cut,object(reply.value().get("payload")).get("cut"));
                assertEquals(before,V53ReplayFilesTest.files(path));assertNotEquals(request.value().get("view"),current.authority());
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void foreignRootRecycledIdentityAndNonProbeCannotReadStatus()throws Exception {
        try(var l=new Local()) {
            var before=l.files();
            for(String mode:List.of("root","storage","endpoint","ballot","kind")) {
                var fields=new TreeMap<>(l.group.request(1,0).value());var sender=l.peer();String kind="STATUS_PROBE";
                if(mode.equals("root"))fields.put("root","a".repeat(64));
                if(mode.equals("storage") || mode.equals("endpoint")) {
                    sender=new MembershipIdentity(sender.nodeId(),mode.equals("storage")?UUID.randomUUID():sender.storageId(),
                            mode.equals("endpoint")?new ReplicationEndpoint("127.0.0.1",1):sender.endpoint());fields.put("sender",MembershipBootstrapSeed.identity(sender));
                }
                if(mode.equals("ballot")){var b=new TreeMap<>(object(fields.get("ballot")));b.put("incarnation",UUID.randomUUID().toString());fields.put("ballot",b);}
                if(mode.equals("kind")){kind="STATUS";fields.put("payload",Map.of("nonce",UUID.randomUUID().toString(),"ready",true,"cut",l.group.capsule.context.cut));}
                var request=decode(encode("wire",kind,fields),"wire",kind);var peer=sender;
                assertThrows(IllegalArgumentException.class,()->l.owner.discoveryStatus(peer,request));
            }
            assertEquals(before,l.files());assertTrue(l.events.isEmpty());
        }
    }
    @Test void transientFailuresRetryExactProbeUnderOriginalDeadline()throws Exception {
        try(var l=new Local()) {
            var count=new AtomicInteger();try(var query=l.query((p,r,k,d)->count.incrementAndGet()<3?CompletableFuture.failedFuture(lost()):l.normal(p,r,k,d))) {
                assertEquals(l.group.capsule.context.cut,query.query(l.peer()).cut());
            }
            assertEquals(3,l.requests.size());assertEquals(1,l.requests.stream().map(Decoded::digest).distinct().count());assertEquals(Set.of(BUDGET),new HashSet<>(l.deadlines));
            assertTrue(l.events.isEmpty());
        }
    }
    @Test void boundedExhaustionAndNonRetryableFailuresReleaseAllQueryCapacity()throws Exception {
        for(var reason:MembershipTransport.Reason.values())try(var l=new Local()) {
            var baseline=l.budget.usage();try(var query=l.query((p,r,k,d)->CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"injected",null)))) {
                assertThrows(MembershipTransport.Failure.class,()->query.query(l.peer()));
            }
            assertEquals(Set.of(MembershipTransport.Reason.IO,MembershipTransport.Reason.DEADLINE).contains(reason)?3:1,l.requests.size());assertEquals(baseline,l.budget.usage());
        }
    }
    @Test void stricterRetryLimitAndExplicitRejectionAreNotRetried()throws Exception {
        try(var l=new Local()) {
            var b=V53TransferServiceTest.bound(2);var one=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),1,b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
            try(var q=l.query((p,r,k,d)->CompletableFuture.failedFuture(lost()),one)){assertThrows(IOException.class,()->q.query(l.peer()));}
            assertEquals(1,l.requests.size());l.requests.clear();
            try(var q=l.query((p,r,k,d)->CompletableFuture.completedFuture(V53ActivationDriverTest.reject(r,"CAPACITY_EXCEEDED",false,false)))){assertThrows(MembershipSourcePull.Rejected.class,()->q.query(l.peer()));}
            assertEquals(1,l.requests.size());
        }
    }
    @Test void malformedReplyAndChangedNonceCannotBecomeHints()throws Exception {
        for(String mode:List.of("nonce","root","ballot","sender","view"))try(var l=new Local();var query=l.query((p,r,k,d)->{
            var value=new TreeMap<>(l.response(r).value());
            if(mode.equals("nonce")){var payload=new TreeMap<>(object(value.get("payload")));payload.put("nonce",UUID.randomUUID().toString());value.put("payload",payload);}
            else if(mode.equals("ballot")){var b=new TreeMap<>(object(value.get("ballot")));b.put("counter",99L);value.put("ballot",b);}
            else if(mode.equals("sender"))value.put("sender",r.value().get("sender"));else value.put(mode,"b".repeat(64));
            return CompletableFuture.completedFuture(decode(encode("wire","STATUS",value),"wire","STATUS"));
        })) {assertThrows(IllegalArgumentException.class,()->query.query(l.peer()));assertEquals(1,l.requests.size());}
    }
    @Test void newerUnverifiedHintNeverLearnsUnknownPeersOrChangesLocalAuthority()throws Exception {
        try(var l=new Local()) {
            var before=l.files();var initial=l.owner.activationCapsule();
            try(var query=l.query((p,r,k,d)->{
                var v=new TreeMap<>(l.response(r).value());var cut=new TreeMap<>(initial.context.cut);var view=new TreeMap<>(object(cut.get("view")));
                view.put("old",List.of("node-2","node-3","node-4"));view.put("new",view.get("old"));view.put("generation",1L);cut.put("view",view);cut.put("index",50L);
                v.put("payload",Map.of("cut",cut,"ready",true,"nonce",object(r.value().get("payload")).get("nonce")));
                return CompletableFuture.completedFuture(decode(encode("wire","STATUS",v),"wire","STATUS"));
            })) {var hint=query.query(l.peer());assertEquals(50L,hint.cut().get("index"));assertTrue(hint.ready());}
            assertSame(initial,l.owner.activationCapsule());assertFalse(initial.context.identities.containsKey("node-4"));assertEquals(before,l.files());assertTrue(l.events.isEmpty());
            try(var query=l.query(l::normal)){assertThrows(IllegalArgumentException.class,()->query.query(V53DeclarationsTest.node(4)));}
        }
    }
    @Test void closeCancelsPendingExchangeAndCannotReturnALateHint()throws Exception {
        try(var l=new Local()) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);var baseline=l.budget.usage();var result=new CompletableFuture<Throwable>();
            try(var query=l.query((p,r,k,d)->{entered.countDown();return pending;})) {
                var thread=Thread.ofPlatform().start(()->{try{query.query(l.peer());result.complete(null);}catch(Throwable e){result.complete(e);}});
                assertTrue(entered.await(5,TimeUnit.SECONDS));query.close();assertNotNull(result.get(5,TimeUnit.SECONDS));thread.join(5000);assertFalse(thread.isAlive());assertTrue(pending.isCancelled());
            }
            assertEquals(baseline,l.budget.usage());
        }
    }
    @Test void deadlineBackwardClockHigherFenceAndClosedOwnerRejectLateReply()throws Exception {
        for(String mode:List.of("deadline","backward","fence","close"))try(var l=new Local();var query=l.query((p,r,k,d)->{
            var reply=l.response(r);
            if(mode.equals("deadline"))l.clock.set(BUDGET);else if(mode.equals("backward"))l.clock.set(-1);else if(mode.equals("fence")) {
                var higher=new TreeMap<>(l.ballot);higher.put("counter",99L);l.owner.observeCurrent(higher);
            }else try{l.owner.close();}catch(IOException e){return CompletableFuture.failedFuture(e);}
            return CompletableFuture.completedFuture(reply);
        })) {assertThrows(Exception.class,()->query.query(l.peer()));assertEquals(1,l.requests.size());}
    }
    @Test void capacityRefusesBeforeExchangeAndOwnerWaitDoesNotResetBudget()throws Exception {
        try(var l=new Local()) {
            assertThrows(IllegalArgumentException.class,()->new MembershipDiscovery(l.owner,resources(),V53TransferServiceTest.bound(2),l::normal,()->{},l.clock::get,0,BUDGET));
            var leases=new ArrayList<MembershipResources.Lease>();int available=256-l.budget.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0);
            try {
                for(int i=0;i<available;i++)leases.add(l.budget.reserve(MembershipResources.Unit.CONTROL,"external-"+i,1));
                try(var query=l.query(l::normal)){assertThrows(IllegalArgumentException.class,()->query.query(l.peer()));}assertTrue(l.requests.isEmpty());
            }finally{leases.forEach(MembershipResources.Lease::close);}
            try(var query=l.query(l::normal)) {
                var result=new CompletableFuture<Throwable>();Thread thread;
                synchronized(l.owner) {
                    thread=Thread.ofPlatform().start(()->{try{query.query(l.peer());result.complete(null);}catch(Throwable e){result.complete(e);}});
                    V53MembershipTransportTest.waitFor(()->thread.getState()==Thread.State.BLOCKED);l.clock.set(BUDGET);
                }
                assertNotNull(result.get(5,TimeUnit.SECONDS));thread.join(5000);assertFalse(thread.isAlive());assertTrue(l.requests.isEmpty());
            }
        }
    }
}
