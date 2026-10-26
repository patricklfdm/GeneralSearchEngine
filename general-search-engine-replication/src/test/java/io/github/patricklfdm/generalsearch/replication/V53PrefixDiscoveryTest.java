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

class V53PrefixDiscoveryTest {
    @TempDir Path temp;
    V53ActivationDriverTest.Local local(AtomicLong clock)throws Exception {
        var helper=new V53ActivationDriverTest();helper.temp=temp;return helper.local(clock,1000);
    }
    MembershipSourcePull pull(V53ActivationDriverTest.Local l,MembershipSourcePull.Link link)throws Exception {
        return MembershipSourcePull.prefix(l.owners.getFirst(),new MembershipDiscovery.Hint(l.group.identities.get(1),l.owners.get(1).activationContext().cut,false),
                l.budgets.getFirst(),l.bound,link,()->{},l.clock,0,BUDGET);
    }
    MembershipSourcePull pull(V53ActivationDriverTest.Local l)throws Exception {return pull(l,(p,r,k,d)->l.deliver(0,p,r,k,d));}
    @Test void realTcpFetchesCompletePublishedPrefixesWithoutGrantAtEveryStableSize()throws Exception {
        var evidence=Files.createDirectories(Path.of("target/v53-prefix-discovery/run-"+UUID.randomUUID()));System.out.println("v53PrefixDiscoveryEvidence="+evidence.toAbsolutePath());
        var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            var raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;f.campaign(1);f.publish(1,false);
                var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();var endpoints=new ArrayList<MembershipActivationEndpoint>();
                var wire=new ArrayList<Map<String,Object>>();var events=new ArrayList<String>();
                try {
                    for(int i=0;i<2;i++) {
                        var t=f.request.targets().get(i);var budget=resources();budgets.add(budget);
                        var owner=MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),budget,
                                (r,p,m)->MembershipCapsule.verify(r,p,m,f.observations),MembershipGrantJournal.MAXIMUM,events::add);owners.add(owner);
                        var endpoint=new MembershipActivationEndpoint(owner,budget,bounds(),(p,r,k,d)->{throw new AssertionError("read-only source must not grant");},
                                (r,p,m)->MembershipCapsule.verify(r,p,m,f.observations),List.of(),List.of(),temp.resolve("endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);
                        endpoints.add(endpoint);group.start(i,endpoint,MembershipTransport.Events.NONE,bounds(),budget);
                    }
                    events.clear();long started=System.nanoTime();
                    MembershipSourcePull.Link link=(p,r,k,d)->group.transports.getFirst().exchange(p,r,k,d).thenApply(reply->{wire.add(V53SelectedPullTest.wire(r,reply));return reply;});
                    MembershipDiscovery.Hint hint;
                    try(var discovery=new MembershipDiscovery(owners.getFirst(),budgets.getFirst(),bounds(),link,()->{},System::nanoTime,started,BUDGET)) {hint=discovery.query(group.identities.get(1));}
                    var scratch=temp.resolve("prefix-"+UUID.randomUUID());
                    try(var pull=MembershipSourcePull.prefix(owners.getFirst(),hint,budgets.getFirst(),bounds(),link,()->{},System::nanoTime,started,BUDGET)) {
                        var received=pull.fetchPrefix(scratch);var verified=pull.verifiedPrefix((r,p,m)->MembershipCapsule.verify(r,p,m,f.observations));
                        assertEquals(hint.cut(),verified.context.cut);assertNull(received.packetBinding().basisId());assertNull(received.packetBinding().basisDigest());
                        assertThrows(IllegalArgumentException.class,received::basis);assertThrows(IllegalArgumentException.class,received::promise);
                        assertThrows(IllegalArgumentException.class,()->pull.verifiedOriginalSource((r,p,m)->MembershipCapsule.verify(r,p,m,f.observations)));
                        Files.createDirectory(raw.resolve("received"));try(var paths=Files.list(scratch)){for(var file:paths.toList())Files.copy(file,raw.resolve("received").resolve(file.getFileName()));}
                    }
                    assertFalse(Files.exists(scratch));assertTrue(events.isEmpty());assertTrue(endpoints.stream().allMatch(v->v.usage().scopeEnded()));
                }finally {for(var t:group.transports)t.close();for(var endpoint:endpoints)endpoint.close();for(var owner:owners)owner.close();}
                f.snapshot("after");Files.write(raw.resolve("wire.json"),canonical(wire,4*1024*1024));Files.write(raw.resolve("events.json"),canonical(events,65536));
                cases.add(Map.of("size",size,"exchanges",wire.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-prefix-discovery-v1","status","PASS","cases",cases,
                "network",true,"publicRuntime",false,"adoption",false,"scope","read-only-current-prefix-acquisition"),65536));
    }
    @Test void removedOldViewReaderFetchesActualAdoptedJointAndFinalPrefix()throws Exception {
        // The historical membership forces remain conditional fixture inputs; the
        // export, transfer, receiving ownership and actual adoption bytes are real.
        for(int through:List.of(6,7)) {
            var f=new V53AdoptionFenceFixture(3,through);var server=temp.resolve("server-"+through);f.provision(server);
            var client=temp.resolve("reader-"+through);V53FloorWorker.provision(client,3,0,3);var a=resources();var b=resources();
            try(var owner=f.open(server,a,e->{});var reader=MembershipGrantJournal.openGenerations(client,f.initial.root(),V53DeclarationsTest.node(3),b,
                    (r,p,m)->MembershipCapsule.verify(r,p,m,f.owned),e->{})) {
                owner.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());var before=V53ReplayFilesTest.files(server);var old=V53ReplayFilesTest.files(client);
                try(var service=MembershipTransferService.prefix(owner,a,bounds(),()->{},()->0L,0,BUDGET);
                    var pull=MembershipSourcePull.prefix(reader,new MembershipDiscovery.Hint(owner.activationIdentity(),owner.activationContext().cut,false),b,bounds(),
                        (p,r,k,d)->{try{return CompletableFuture.completedFuture(service.handle(reader.activationIdentity(),r));}catch(IOException|RuntimeException e){return CompletableFuture.failedFuture(e);}},
                        ()->{},()->0L,0,BUDGET)) {
                    var received=pull.fetchPrefix(temp.resolve("received-"+through));
                    assertThrows(IllegalArgumentException.class,()->pull.verifiedPrefix((r,p,m)->MembershipCapsule.verify(r,p,m,Set.of())));
                    assertEquals(owner.activationContext().cut,pull.verifiedPrefix((r,p,m)->MembershipCapsule.verify(r,p,m,f.owned)).context.cut);
                    assertNotEquals(reader.activationContext().authority(),owner.activationContext().authority());
                    assertArrayEquals(f.remote.packet().bytes(),received.packet().bytes());
                }
                assertEquals(before,V53ReplayFilesTest.files(server));assertEquals(old,V53ReplayFilesTest.files(client));
            }
            assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());
        }
    }
    @Test void lostOfferDataAndCommitResponsesRetryIdenticalBytesWithoutAnotherGrant()throws Exception {
        try(var l=local(new AtomicLong())) {
            var seen=new HashSet<String>();var attempts=new ArrayList<String>();var lost=new HashSet<String>();
            var path=l.group.fixture.request.targets().get(1).replicaDirectory();var before=V53ReplayFilesTest.files(path);
            try(var pull=pull(l,(p,r,k,d)->l.deliver(0,p,r,k,d).thenCompose(reply->{
                attempts.add(r.digest());assertEquals(BUDGET,d);
                if(!lost.contains(k)){lost.add(k);seen.add(r.digest());return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null));}
                return CompletableFuture.completedFuture(reply);
            }))) {pull.fetchPrefix(temp.resolve("lost"));assertNotNull(pull.verifiedPrefix(V53ActivationEndpointTest.verifier()));}
            assertEquals(Set.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT"),lost);
            for(var digest:seen)assertEquals(2,Collections.frequency(attempts,digest));assertEquals(before,V53ReplayFilesTest.files(path));
        }
    }
    @Test void permanentFailuresAndExplicitRejectsAreNotRetried()throws Exception {
        try(var l=local(new AtomicLong())) {
            for(var reason:List.of(MembershipTransport.Reason.CAPACITY,MembershipTransport.Reason.PROTOCOL,MembershipTransport.Reason.CLOSED)) {
                var count=new AtomicInteger();try(var pull=pull(l,(p,r,k,d)->{count.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"test",null));})) {
                    assertThrows(IOException.class,()->pull.fetchPrefix(temp.resolve(reason.name())));assertEquals(1,count.get());
                }
            }
            var count=new AtomicInteger();try(var pull=pull(l,(p,r,k,d)->{count.incrementAndGet();return CompletableFuture.completedFuture(V53ActivationDriverTest.reject(r,"STALE_EPOCH",false,false));})) {
                assertThrows(MembershipSourcePull.Rejected.class,()->pull.fetchPrefix(temp.resolve("reject")));assertEquals(1,count.get());
            }
        }
    }
    @Test void transientFailureStopsAtThreeExactAttempts()throws Exception {
        try(var l=local(new AtomicLong())) {
            var seen=new ArrayList<String>();try(var pull=pull(l,(p,r,k,d)->{seen.add(r.digest());return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null));})) {
                assertThrows(IOException.class,()->pull.fetchPrefix(temp.resolve("exhausted")));assertEquals(3,seen.size());assertEquals(1,new HashSet<>(seen).size());
            }
        }
    }
    @Test void receiverRejectsLateReplyAfterFencingOrDeadline()throws Exception {
        for(boolean fence:List.of(false,true))try(var l=local(new AtomicLong())) {
            var time=new AtomicLong();var owner=l.owners.getFirst();var original=owner.discoveryState(l.budgets.getFirst());
            try(var pull=MembershipSourcePull.prefix(owner,new MembershipDiscovery.Hint(l.group.identities.get(1),l.owners.get(1).activationContext().cut,false),l.budgets.getFirst(),l.bound,
                    (p,r,k,d)->l.deliver(0,p,r,k,d).thenApply(reply->{if(fence){var higher=new TreeMap<>(original.ballot());higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);}else time.set(BUDGET);return reply;}),
                    ()->{},time::get,0,BUDGET)) {assertThrows(IllegalArgumentException.class,()->pull.fetchPrefix(temp.resolve("late-"+fence)));}
        }
    }
    @Test void cancelledPullCancelsPendingExchangeAndReleasesReservations()throws Exception {
        try(var l=local(new AtomicLong())) {
            var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();var before=l.budgets.getFirst().usage();
            try(var pull=pull(l,(p,r,k,d)->{entered.countDown();return pending;});var executor=Executors.newVirtualThreadPerTaskExecutor()) {
                var running=executor.submit(()->pull.fetchPrefix(temp.resolve("cancel")));assertTrue(entered.await(5,TimeUnit.SECONDS));pull.close();
                assertThrows(ExecutionException.class,()->running.get(5,TimeUnit.SECONDS));assertTrue(pending.isCancelled());
            }
            assertEquals(before,l.budgets.getFirst().usage());
        }
    }
    @Test void exportRevokesOnSelectorChangeInsteadOfBlockingAdoption()throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);var path=temp.resolve("replace");f.provision(path);var budget=resources();
        try(var owner=f.open(path,budget,e->{})) {
            var old=owner.activationContext();var ballot=owner.discoveryState(budget).ballot();
            try(var export=owner.exportPrefix(cutDigest(old.cut),ballot,old.authority(),budget,()->0L,0,BUDGET)) {
                var packet=export.references().get(cutDigest(old.cut));owner.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
                assertThrows(IllegalArgumentException.class,()->export.read(packet.digest(),0,16));assertThrows(IllegalArgumentException.class,export::references);
            }
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void exportExpiresAfterWaitingForWriterAndRejectsWrongSharedBudget()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock)) {
            var owner=l.owners.get(1);var state=owner.discoveryState(l.budgets.get(1));var before=l.budgets.get(1).usage();
            assertThrows(IllegalArgumentException.class,()->owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),resources(),clock::get,0,BUDGET));
            try(var executor=Executors.newVirtualThreadPerTaskExecutor()) {
                Future<?> pending;var entered=new CountDownLatch(1);
                synchronized(owner){pending=executor.submit(()->{entered.countDown();return owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),l.budgets.get(1),clock::get,0,BUDGET);});assertTrue(entered.await(5,TimeUnit.SECONDS));clock.set(BUDGET);}
                assertThrows(ExecutionException.class,()->pending.get(5,TimeUnit.SECONDS));
            }
            assertEquals(before,l.budgets.get(1).usage());
        }
    }
    @Test void untrustedHintAndSubstitutedVerifierCannotBecomeAuthority()throws Exception {
        try(var l=local(new AtomicLong())) {
            var hint=new TreeMap<>(l.owners.get(1).activationContext().cut);hint.put("index",99L);
            try(var pull=MembershipSourcePull.prefix(l.owners.getFirst(),new MembershipDiscovery.Hint(l.group.identities.get(1),hint,true),l.budgets.getFirst(),l.bound,
                    (p,r,k,d)->l.deliver(0,p,r,k,d),()->{},l.clock,0,BUDGET)) {
                assertThrows(Exception.class,()->pull.fetchPrefix(temp.resolve("hint")));
            }
            try(var pull=pull(l)) {pull.fetchPrefix(temp.resolve("valid"));
                assertThrows(IllegalArgumentException.class,()->pull.verifiedPrefix((r,p,m)->new V53CapsuleFixture(3,"REPLACE",7).verify()));
                assertThrows(IllegalArgumentException.class,()->pull.fetchRecord("0".repeat(64),"PROMISE",v->{}));
            }
        }
    }
    @Test void scratchMutationAndCorruptTransferAreRejectedAndCleaned()throws Exception {
        try(var l=local(new AtomicLong())) {
            var scratch=temp.resolve("scratch");try(var pull=pull(l)) {
                pull.fetchPrefix(scratch);Files.write(scratch.resolve("source.gscp"),new byte[]{1});
                assertThrows(IllegalArgumentException.class,()->pull.verifiedPrefix(V53ActivationEndpointTest.verifier()));
            }
            assertFalse(Files.exists(scratch));
            try(var pull=pull(l,(p,r,k,d)->l.deliver(0,p,r,k,d).thenApply(reply->{
                if(!k.equals("CHUNK"))return reply;var value=new TreeMap<>(reply.value());var payload=new TreeMap<>(object(value.get("payload")));
                payload.put("bytes",Base64.getEncoder().encodeToString(new byte[]{9}));value.put("payload",payload);return decode(encode("wire","CHUNK",value),"wire","CHUNK");
            }))) {assertThrows(IllegalArgumentException.class,()->pull.fetchPrefix(temp.resolve("corrupt")));}
            assertFalse(Files.exists(temp.resolve("corrupt")));
        }
    }
    @Test void exportRejectsReplacedFileAndOwnerClose()throws Exception {
        try(var l=local(new AtomicLong())) {
            var owner=l.owners.get(1);var state=owner.discoveryState(l.budgets.get(1));
            try(var export=owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),l.budgets.get(1),()->0L,0,BUDGET)) {
                var packet=export.references().get(cutDigest(state.context().cut));var dir=l.group.fixture.request.targets().get(1).replicaDirectory();
                var selector=decode(Files.readAllBytes(dir.resolve("selector.gsr")),"records","SELECTOR");var file=dir.resolve("generations").resolve((String)selector.value().get("generation")).resolve("source.gscp");
                var replacement=file.resolveSibling("replacement");Files.write(replacement,Files.readAllBytes(file));Files.move(replacement,file,StandardCopyOption.REPLACE_EXISTING);
                assertThrows(IllegalArgumentException.class,()->export.read(packet.digest(),0,16));owner.close();assertThrows(IllegalArgumentException.class,export::references);
            }
        }
    }
    @Test void readOnlySessionRejectsChangedRootIdentityViewBallotAndTrace()throws Exception {
        try(var l=local(new AtomicLong())) {
            var owner=l.owners.get(1);var state=owner.discoveryState(l.budgets.get(1));var reader=l.group.identities.getFirst();
            for(String changed:List.of("root","storage","view","ballot","trace")) {
                var request=l.group.request(0,1,"CHUNK",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,
                        "digest",cutDigest(state.context().cut),"bytes",""));
                try(var export=owner.exportPrefix(cutDigest(state.context().cut),object(request.value().get("ballot")),state.context().authority(),l.budgets.get(1),()->0L,0,BUDGET);
                    var session=new MembershipSourceSession(export,reader,UUID.fromString((String)request.value().get("trace")),l.budgets.get(1),1024,FRAME,()->0L,0,BUDGET)) {
                    var fields=new TreeMap<>(request.value());
                    switch(changed) {
                        case "root","view" -> fields.put(changed,"f".repeat(64));
                        case "storage" -> {var id=new TreeMap<>(object(fields.get("sender")));id.put("storage",UUID.randomUUID().toString());fields.put("sender",id);}
                        case "trace" -> fields.put("trace",UUID.randomUUID().toString());
                        case "ballot" -> {var ballot=new TreeMap<>(object(fields.get("ballot")));ballot.put("counter",99L);fields.put("ballot",ballot);}
                    }
                    var bad=decode(encode("wire","CHUNK",fields),"wire","CHUNK");
                    assertThrows(IllegalArgumentException.class,()->session.handle(reader,bad),changed);
                }
            }
        }
    }
    @Test void boundedExportsExpireAndReleaseWithoutHoldingAnObsoleteGeneration()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock)) {
            var owner=l.owners.get(1);var resources=l.budgets.get(1);var state=owner.discoveryState(resources);var before=resources.usage();
            var exports=new ArrayList<MembershipPrefixExport>();
            try {
                for(int n=0;n<6;n++)exports.add(owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),resources,clock::get,0,BUDGET));
                assertThrows(IllegalArgumentException.class,()->owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),resources,clock::get,0,BUDGET));
                clock.set(BUDGET);
                try(var fresh=owner.exportPrefix(cutDigest(state.context().cut),state.ballot(),state.context().authority(),resources,clock::get,BUDGET,BUDGET)) {
                    assertNotNull(fresh.references());for(var old:exports)assertThrows(IllegalArgumentException.class,old::references);
                }
            }finally{exports.forEach(MembershipPrefixExport::close);}
            assertEquals(before,resources.usage());
        }
    }
}
