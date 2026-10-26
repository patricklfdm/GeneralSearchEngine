package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.LongSupplier;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53ActivationDriverTest {
    @TempDir Path temp;
    final class Local implements AutoCloseable {
        final V53MembershipTransportTest.Group group;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<MembershipActivationEndpoint> endpoints=new ArrayList<>();
        final List<AtomicReference<MembershipTransport>> transports=new ArrayList<>();
        final ExecutorService executor=Executors.newVirtualThreadPerTaskExecutor();
        final AtomicReference<MembershipSourcePull.Link> override=new AtomicReference<>();
        final List<Map<String,Object>> wire=Collections.synchronizedList(new ArrayList<>());
        final List<Decoded> requests=Collections.synchronizedList(new ArrayList<>());
        final List<Long> deadlines=Collections.synchronizedList(new ArrayList<>());
        final Map<String,List<String>> events=new TreeMap<>();
        final ReplicationBounds bound;
        final LongSupplier clock;
        final boolean tcp;
        Local(int size,boolean tcp,Path raw,LongSupplier clock,int requestMillis)throws Exception {
            this.clock=clock;this.tcp=tcp;bound=V53MembershipTransportTest.bounds(2,requestMillis,FRAME);
            var helper=new V53MembershipTransportTest();helper.temp=temp;group=helper.new Group(size,raw);
            for(int i=0;i<size;i++) {
                var target=group.fixture.request.targets().get(i);var budget=resources();budgets.add(budget);
                var steps=Collections.synchronizedList(new ArrayList<String>());events.put(target.identity().nodeId().value(),steps);
                owners.add(MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),group.fixture.result.root(),target.identity(),budget,V53ActivationEndpointTest.verifier(),MembershipGrantJournal.MAXIMUM,steps::add));
                transports.add(new AtomicReference<>());
            }
            for(int i=0;i<size;i++) {
                int from=i;
                var endpoint=new MembershipActivationEndpoint(owners.get(i),budgets.get(i),bound,(p,r,k,d)->deliver(from,p,r,k,d),V53ActivationEndpointTest.verifier(),List.of(),List.of(),temp.resolve("endpoint-"+UUID.randomUUID()),clock,BUDGET);
                endpoints.add(endpoint);
                if(tcp)transports.get(i).set(group.start(i,endpoint,(event,r,s)->{if(event.equals("BEFORE_RESPONSE_WRITE"))wire.add(V53SelectedPullTest.wire(r,s));},bound,budgets.get(i)));
            }
            override.set((p,r,k,d)->deliver(0,p,r,k,d));
        }
        CompletableFuture<Decoded> deliver(int from,MembershipIdentity peer,Decoded request,String kind,long deadline) {
            if(tcp)return transports.get(from).get().exchange(peer,request,kind,deadline);
            return CompletableFuture.supplyAsync(()->{try{return endpoints.get(group.identities.indexOf(peer)).handle(group.identities.get(from),request);}catch(IOException e){throw new CompletionException(e);}},executor);
        }
        MembershipActivationDriver driver(int maximum)throws Exception {return driver(maximum,bound);}
        MembershipActivationDriver driver(int maximum,ReplicationBounds settings)throws Exception {
            return new MembershipActivationDriver(owners.getFirst(),endpoints.getFirst(),budgets.getFirst(),settings,(p,r,k,d)->{
                requests.add(r);deadlines.add(d);return override.get().exchange(p,r,k,d);
            },V53ActivationEndpointTest.verifier(),List.of(),List.of(),temp.resolve("driver-"+UUID.randomUUID()),clock,BUDGET,maximum);
        }
        @Override public void close()throws Exception {
            for(var endpoint:endpoints)endpoint.close();for(var t:group.transports)t.close();executor.shutdownNow();assertTrue(executor.awaitTermination(10,TimeUnit.SECONDS));
            for(var owner:owners)owner.close();group.close();for(var budget:budgets)assertEquals(0,budget.usage().leases());
        }
    }
    Local local()throws Exception{return local(new AtomicLong(),1000);}
    Local local(AtomicLong clock,int millis)throws Exception{return new Local(3,false,Files.createDirectory(temp.resolve("raw-"+UUID.randomUUID())),clock::get,millis);}
    static Decoded reject(Decoded request,String reason,boolean higher,boolean foreign) {
        var value=new TreeMap<>(request.value());value.put("sender",request.value().get("recipient"));value.put("recipient",request.value().get("sender"));
        var promised=new TreeMap<>(object(request.value().get("ballot")));if(higher)promised.put("counter",number(promised.get("counter"))+1);
        value.put("payload",Map.of("promised",promised,"reason",reason));if(foreign)value.put("root","0".repeat(64));
        return decode(encode("wire","REJECT",value),"wire","REJECT");
    }
    static long ballot(Decoded request){return number(object(request.value().get("ballot")).get("counter"));}
    static Decoded wireRequest(Map<String,Object> row) {
        byte[] bytes=Base64.getDecoder().decode((String)row.get("request"));
        return MembershipWire.decode(bytes,FRAME);
    }
    @Test void preferredQuorumHonorsBothMajoritiesAcrossAllSevenProfiles()throws Exception {
        for(var profile:V53SelectionTest.PROFILES)for(int through:List.of(5,6,7)) {
            var f=new V53CapsuleFixture(profile.getKey(),profile.getValue(),through);
            var context=f.verify().context;var local=context.identities.get("node-1");
            for(String deferred:context.voters()) {
                var chosen=MembershipActivationDriver.preferred(context,local,deferred);var names=new HashSet<String>();names.add("node-1");chosen.forEach(p->names.add(p.nodeId().value()));
                for(String side:List.of("old","new")){var voters=list(context.view.get(side));assertTrue(names.stream().filter(voters::contains).count()>voters.size()/2);}
                if(!deferred.equals("node-1"))assertFalse(names.contains(deferred));
            }
        }
    }
    @Test void everySelectedAckIsRequiredBeforeLocalInstallation()throws Exception {
        var raw=Files.createDirectory(temp.resolve("multi-ack"));
        try(var l=new Local(5,false,raw,()->0,1000);var driver=l.driver(2)) {
            var normal=l.override.get();var held=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);var answer=new AtomicReference<Decoded>();
            l.override.set((p,r,k,d)->{
                if(r.kind().equals("SELECTED") && p.nodeId().value().equals("node-3"))return normal.exchange(p,r,k,d).thenCompose(reply->{answer.set(reply);entered.countDown();return held;});
                return normal.exchange(p,r,k,d);
            });
            var run=CompletableFuture.supplyAsync(()->{try{return driver.run();}catch(IOException e){throw new CompletionException(e);}});
            assertTrue(entered.await(10,TimeUnit.SECONDS));assertFalse(run.isDone());assertThrows(IllegalArgumentException.class,driver::selection);
            assertFalse(l.events.get("node-1").contains("INSTALL_BEFORE_RETURN"));held.complete(answer.get());
            assertEquals("SELECTED",run.get(10,TimeUnit.SECONDS).kind());assertEquals(1,l.events.get("node-1").stream().filter("INSTALL_BEFORE_RETURN"::equals).count());
        }
    }
    @Test void higherPromiseAfterRemoteInstallRejectsLateAckAndLocalInstallation()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            var normal=l.override.get();
            l.override.set((p,r,k,d)->normal.exchange(p,r,k,d).thenApply(reply->{
                if(r.kind().equals("SELECTED")){var higher=new TreeMap<>(object(r.value().get("ballot")));higher.put("counter",number(higher.get("counter"))+1);l.owners.getFirst().observeCurrent(higher);}
                return reply;
            }));
            assertThrows(Exception.class,driver::run);assertFalse(l.events.get("node-1").contains("INSTALL_BEFORE_RETURN"));assertEquals(1,driver.campaigns());
            assertEquals(1,l.events.get("node-2").stream().filter("INSTALL_BEFORE_RETURN"::equals).count());
        }
    }
    @Test void freshBallotCannotAllocateAfterEnclosingDeadline()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock,1000)) {
            var before=V53ReplayFilesTest.files(l.group.fixture.request.targets().getFirst().replicaDirectory());clock.set(BUDGET);
            assertThrows(IllegalArgumentException.class,()->new MembershipActivation(l.owners.getFirst(),l.budgets.getFirst(),clock::get,0,BUDGET));
            assertEquals(before,V53ReplayFilesTest.files(l.group.fixture.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void waitingForLocalWriterCannotAllocateAfterOriginalDeadline()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock,1000)) {
            var owner=l.owners.getFirst();var before=V53ReplayFilesTest.files(l.group.fixture.request.targets().getFirst().replicaDirectory());
            var result=new CompletableFuture<Throwable>();Thread worker;
            synchronized(owner) {
                worker=Thread.ofPlatform().start(()->{try(var c=new MembershipActivation(owner,l.budgets.getFirst(),clock::get,0,BUDGET)){result.complete(null);}catch(Throwable e){result.complete(e);}});
                V53MembershipTransportTest.waitFor(()->worker.getState()==Thread.State.BLOCKED);clock.set(BUDGET);
            }
            assertNotNull(result.get(5,TimeUnit.SECONDS));worker.join(5000);assertFalse(worker.isAlive());
            assertEquals(before,V53ReplayFilesTest.files(l.group.fixture.request.targets().getFirst().replicaDirectory()),"expired writer wait must not allocate or force a grant");
        }
    }
    @Test void exactTransientControlRetryPreservesBytesAndDeadline()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            var normal=l.override.get();var failures=new AtomicInteger();
            l.override.set((p,r,k,d)->r.kind().equals("PREPARE") && failures.getAndIncrement()==0?CompletableFuture.failedFuture(lost()):normal.exchange(p,r,k,d));
            assertEquals("SELECTED",driver.run().kind());assertEquals(1,driver.campaigns());
            assertArrayEquals(l.requests.get(0).bytes(),l.requests.get(1).bytes());assertEquals(Set.of(BUDGET),new HashSet<>(l.deadlines));
            assertThrows(IllegalArgumentException.class,driver::run);
        }
    }
    @Test void stricterCallerRetryLimitIsRespected()throws Exception {
        try(var l=local()) {
            var b=l.bound;var one=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),1,b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
            var normal=l.override.get();l.override.set((p,r,k,d)->p.nodeId().value().equals("node-2")?CompletableFuture.failedFuture(lost()):normal.exchange(p,r,k,d));
            try(var driver=l.driver(2,one)) {
                driver.run();assertEquals(1,l.requests.stream().filter(r->r.kind().equals("PREPARE") && identity(object(r.value().get("recipient"))).nodeId().value().equals("node-2")).count());
            }
        }
    }
    @Test void unavailablePrepareUsesAnotherSourceWithoutChangingBallot()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            var normal=l.override.get();l.override.set((p,r,k,d)->p.nodeId().value().equals("node-2")?CompletableFuture.failedFuture(lost()):normal.exchange(p,r,k,d));
            var result=driver.run();assertEquals(List.of("node-1","node-3"),list(result.value().get("sources")).stream().map(v->object(v).get("voter")).toList());
            assertEquals(1,driver.campaigns());assertEquals(3,l.requests.stream().filter(r->r.kind().equals("PREPARE") && identity(object(r.value().get("recipient"))).nodeId().value().equals("node-2")).count());
        }
    }
    @Test void failedSelectedPeerGetsFreshBallotAndAlternativeOpportunity()throws Exception {
        for(boolean lostAck:List.of(false,true))try(var l=local();var driver=l.driver(3)) {
            var normal=l.override.get();var installed=new AtomicBoolean();
            l.override.set((p,r,k,d)->{
                if(p.nodeId().value().equals("node-2") && r.kind().equals("SELECTED")) {
                    if(lostAck && installed.compareAndSet(false,true))return normal.exchange(p,r,k,d).thenCompose(reply->CompletableFuture.failedFuture(lost()));
                    return lostAck?CompletableFuture.failedFuture(lost()):CompletableFuture.completedFuture(reject(r,"CAPACITY_EXCEEDED",false,false));
                }
                return normal.exchange(p,r,k,d);
            });
            var result=driver.run();assertEquals(2,driver.campaigns());assertEquals(3,ballot(result));
            assertEquals(List.of("node-1","node-3"),list(result.value().get("sources")).stream().map(v->object(v).get("voter")).toList());
            assertTrue(l.requests.stream().filter(r->r.kind().equals("PREPARE") && ballot(r)==3).allMatch(r->identity(object(r.value().get("recipient"))).nodeId().value().equals("node-3")));
            assertEquals(Set.of(BUDGET),new HashSet<>(l.deadlines));
            assertEquals(1,l.events.get("node-1").stream().filter("INSTALL_BEFORE_RETURN"::equals).count());
            if(lostAck)assertEquals(1,l.events.get("node-2").stream().filter("INSTALL_BEFORE_RETURN"::equals).count());
        }
    }
    @Test void preferredFailureFallsBackToPreviouslyDeferredPeer()throws Exception {
        try(var l=local();var driver=l.driver(3)) {
            var normal=l.override.get();l.override.set((p,r,k,d)->{
                if((r.kind().equals("SELECTED") && ballot(r)==2) || (r.kind().equals("PREPARE") && p.nodeId().value().equals("node-3")))return CompletableFuture.completedFuture(reject(r,"CAPACITY_EXCEEDED",false,false));
                return normal.exchange(p,r,k,d);
            });
            var result=driver.run();assertEquals(2,driver.campaigns());assertEquals(3,ballot(result));
            var peers=l.requests.stream().filter(r->r.kind().equals("PREPARE") && ballot(r)==3).map(r->identity(object(r.value().get("recipient"))).nodeId().value()).toList();
            assertEquals(List.of("node-3","node-2"),peers);
        }
    }
    @Test void stalledSourceCannotHoldHealthyAlternativeAndIsDrained()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock,100);var driver=l.driver(2)) {
            var normal=l.override.get();var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);
            l.override.set((p,r,k,d)->{if(p.nodeId().value().equals("node-2")){entered.countDown();return pending;}return normal.exchange(p,r,k,d);});
            var run=CompletableFuture.supplyAsync(()->{try{return driver.run();}catch(IOException e){throw new CompletionException(e);}});
            assertTrue(entered.await(5,TimeUnit.SECONDS));clock.set(TimeUnit.MILLISECONDS.toNanos(101));
            assertEquals("SELECTED",run.get(10,TimeUnit.SECONDS).kind());assertEquals(1,driver.campaigns());assertTrue(pending.isCancelled());
        }
    }
    @Test void closeCancelsPendingPeerAndLeavesNoStagedFiles()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);
            l.override.set((p,r,k,d)->{entered.countDown();return pending;});
            var run=CompletableFuture.runAsync(()->assertThrows(Exception.class,driver::run));
            assertTrue(entered.await(5,TimeUnit.SECONDS));driver.close();run.get(5,TimeUnit.SECONDS);assertTrue(pending.isCancelled());
            assertTrue(l.endpoints.getFirst().usage().scopeEnded());assertThrows(Exception.class,driver::selection);
        }
    }
    @Test void failedInstallationAtDeadlineCannotStartFreshGrant()throws Exception {
        var clock=new AtomicLong();try(var l=local(clock,1000);var driver=l.driver(3)) {
            var normal=l.override.get();l.override.set((p,r,k,d)->{
                if(r.kind().equals("SELECTED")){clock.set(BUDGET);return CompletableFuture.completedFuture(reject(r,"CAPACITY_EXCEEDED",false,false));}
                return normal.exchange(p,r,k,d);
            });
            assertThrows(Exception.class,driver::run);assertEquals(1,driver.campaigns());assertEquals(2,ballot(l.owners.getFirst().promised().orElseThrow()));
            assertFalse(l.events.get("node-1").contains("INSTALL_BEFORE_RETURN"));
        }
    }
    @Test void malformedReplyFailsWithoutRetryOrForeignFencing()throws Exception {
        try(var l=local();var driver=l.driver(3)) {
            l.override.set((p,r,k,d)->CompletableFuture.completedFuture(reject(r,"STALE_EPOCH",true,true)));
            assertThrows(IOException.class,driver::run);assertEquals(1,l.requests.size());assertEquals(1,driver.campaigns());
            var basis=l.owners.getFirst().originalBasis().orElseThrow();l.owners.getFirst().checkActivation(basis,null,false);
        }
    }
    @Test void correlatedHigherPromiseStopsCampaignBeforeWriterAdmission()throws Exception {
        try(var l=local();var driver=l.driver(3)) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);
            l.override.set((p,r,k,d)->{entered.countDown();return pending;});
            var run=CompletableFuture.runAsync(()->assertThrows(Exception.class,driver::run));assertTrue(entered.await(5,TimeUnit.SECONDS));
            synchronized(l.owners.getFirst()) {
                var reply=reject(l.requests.getFirst(),"STALE_EPOCH",true,false);
                CompletableFuture.runAsync(()->pending.complete(reply)).get(5,TimeUnit.SECONDS);
                assertThrows(IllegalArgumentException.class,()->l.owners.getFirst().checkActivation(l.owners.getFirst().originalBasis().orElseThrow(),null,false));
            }
            run.get(5,TimeUnit.SECONDS);assertEquals(1,driver.campaigns());assertEquals(1,l.requests.size());
        }
    }
    @Test void higherOriginalSourceRejectionFencesBeforeSelection()throws Exception {
        try(var l=local();var driver=l.driver(3)) {
            var normal=l.override.get();l.override.set((p,r,k,d)->r.kind().equals("CHUNK")?CompletableFuture.completedFuture(reject(r,"STALE_EPOCH",true,false)):normal.exchange(p,r,k,d));
            // The writer can observe the higher root promise before the exchange
            // worker publishes its fatal IOException. Both paths must fence, never retry.
            var failure=assertThrows(Exception.class,driver::run);assertTrue(failure instanceof IOException || failure instanceof IllegalArgumentException);
            var reasons=new ArrayList<String>();for(Throwable cause=failure;cause!=null;cause=cause.getCause())reasons.add(String.valueOf(cause.getMessage()));
            assertTrue(reasons.stream().anyMatch(v->v.contains("higher activation promise") || v.contains("higher ballot observed")),reasons.toString());
            assertEquals(1,driver.campaigns());
            assertThrows(IllegalArgumentException.class,()->l.owners.getFirst().checkActivation(l.owners.getFirst().originalBasis().orElseThrow(),null,false));
            assertFalse(l.events.get("node-1").contains("SELECTED_FORCED"));
        }
    }
    @Test void closeDuringCapsuleTransferDrainsAndRemovesOnlyOwnedScratch()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            var normal=l.override.get();var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();var dataRequests=new AtomicInteger();
            l.override.set((p,r,k,d)->{
                // BASIS and PROMISE have completed; the third data request owns capsule scratch.
                if(k.equals("CHUNK") && dataRequests.incrementAndGet()==3){entered.countDown();return pending;}
                return normal.exchange(p,r,k,d);
            });
            var run=CompletableFuture.runAsync(()->assertThrows(Exception.class,driver::run));assertTrue(entered.await(10,TimeUnit.SECONDS));
            try(var dirs=Files.list(temp)){assertTrue(dirs.anyMatch(p->p.getFileName().toString().startsWith("driver-")));}
            driver.close();run.get(5,TimeUnit.SECONDS);assertTrue(pending.isCancelled());
            try(var dirs=Files.list(temp)) {
                var owned=dirs.filter(p->p.getFileName().toString().startsWith("driver-")).toList();assertEquals(1,owned.size());
                assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(owned.getFirst(),8));
            }
        }
    }
    @Test void callerCampaignLimitDoesNotRetireOriginalFailedSources()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            var normal=l.override.get();l.override.set((p,r,k,d)->r.kind().equals("SELECTED")?CompletableFuture.completedFuture(reject(r,"CAPACITY_EXCEEDED",false,false)):normal.exchange(p,r,k,d));
            assertTrue(assertThrows(IOException.class,driver::run).getMessage().contains("campaign capacity"));assertEquals(2,driver.campaigns());
            assertEquals(2,l.budgets.getFirst().usage().counts().get(MembershipResources.Unit.SOURCE));assertFalse(l.events.get("node-1").contains("INSTALL_BEFORE_RETURN"));
        }
    }
    @Test void cancelledDriverPreservesForeignScratch()throws Exception {
        try(var l=local()) {
            Path scratch=temp.resolve("foreign-driver");var driver=new MembershipActivationDriver(l.owners.getFirst(),l.endpoints.getFirst(),l.budgets.getFirst(),l.bound,l.override.get(),V53ActivationEndpointTest.verifier(),List.of(),List.of(),scratch,()->0,BUDGET,1);
            Path foreign=Files.writeString(scratch.resolve("foreign"),"operator");assertThrows(IllegalArgumentException.class,driver::close);assertEquals("operator",Files.readString(foreign));Files.delete(foreign);driver.close();
        }
    }
    @Test void realTcpAutomaticActivationInstallsEverySelectedVoterAtThreeSizes()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-activation-driver/run-"+UUID.randomUUID()));System.out.println("v53ActivationDriverEvidence="+evidence.toAbsolutePath());
        var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));
            try(var l=new Local(size,true,raw,System::nanoTime,10000);var driver=l.driver(2)) {
                var selected=driver.run();assertEquals(1,driver.campaigns());assertEquals(size/2+1,list(selected.value().get("sources")).size());
                Files.write(raw.resolve("selected.gsr"),selected.bytes());l.group.fixture.snapshot("installed");
                var controls=l.wire.stream().filter(row->Set.of("PREPARE","SELECTED").contains(wireRequest(row).kind()))
                        .sorted(Comparator.comparingLong(row->number(wireRequest(row).value().get("sequence")))).toList();
                Files.write(raw.resolve("wire.json"),canonical(controls,1024*1024));
                Files.write(raw.resolve("events.json"),canonical(l.events.entrySet().stream().map(row->Map.of("node",row.getKey(),"events",row.getValue())).toList(),1024*1024));
                Files.write(evidence.resolve("stable-"+size+"-network.json"),canonical(l.wire,16*1024*1024));
                cases.add(Map.of("size",size,"selected",size/2+1,"installed",size/2+1));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-activation-driver-v1","status","PASS","cases",cases,"network",true,"publicRuntime",false,"automaticCampaign",true),65536));
    }
}
