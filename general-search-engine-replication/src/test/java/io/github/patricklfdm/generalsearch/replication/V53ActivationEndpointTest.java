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

class V53ActivationEndpointTest {
    @TempDir Path temp;
    static MembershipCurrentGeneration.Verifier verifier(){return (r,p,i)->MembershipCapsule.verify(r,p,i,Set.of());}
    final class Local implements AutoCloseable {
        final V53PromisedSourceTest.Local base;
        final MembershipTransferService leaderService;
        final MembershipActivationEndpoint endpoint;
        final AtomicReference<MembershipSourcePull.Link> link=new AtomicReference<>();
        final AtomicInteger calls=new AtomicInteger();
        final Path scratch=temp.resolve("endpoint-"+UUID.randomUUID());
        Local()throws Exception {
            var helper=new V53PromisedSourceTest();helper.temp=temp;base=helper.new Local("genesis");
            leaderService=new MembershipTransferService(base.leader,base.campaign.ballot(),base.leaderResources,V53TransferServiceTest.bound(2),()->{},base.clock::get,0,BUDGET);
            link.set((peer,request,kind,deadline)->{
                calls.incrementAndGet();assertEquals(BUDGET,deadline);
                try{return CompletableFuture.completedFuture(leaderService.handle(base.identity(),request));}
                catch(Exception error){return CompletableFuture.failedFuture(error);}
            });
            endpoint=new MembershipActivationEndpoint(base.peer,base.peerResources,V53TransferServiceTest.bound(2),
                    (peer,request,kind,deadline)->link.get().exchange(peer,request,kind,deadline),verifier(),List.of(),List.of(),scratch,base.clock::get,BUDGET);
        }
        MembershipIdentity proposer(){return base.f.request.targets().getFirst().identity();}
        Decoded prepare()throws Exception{return base.campaign.prepare(base.identity());}
        @Override public void close()throws Exception {endpoint.close();leaderService.close();base.close();}
    }
    @Test void duplicatePrepareSharesOriginalReplyAndExpiryCannotRenewScope()throws Exception {
        try(var l=new Local()) {
            var request=l.prepare();var first=l.endpoint.handle(l.proposer(),request);int calls=l.calls.get();
            assertEquals(3,calls);assertArrayEquals(first.bytes(),l.endpoint.handle(l.proposer(),request).bytes());assertEquals(calls,l.calls.get());
            var files=V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory());l.base.clock.set(BUDGET);
            assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),request));assertEquals(calls,l.calls.get());
            assertEquals(files,V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory()));
        }
    }
    @Test void duplicateInFlightControlSharesTaskAndDifferentControlIsBounded()throws Exception {
        try(var l=new Local()) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);l.link.set((p,r,k,d)->{l.calls.incrementAndGet();entered.countDown();return pending;});
            var request=l.prepare();var first=CompletableFuture.runAsync(()->assertThrows(IOException.class,()->l.endpoint.handle(l.proposer(),request)));
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            var second=CompletableFuture.runAsync(()->assertThrows(IOException.class,()->l.endpoint.handle(l.proposer(),request)));
            var changed=new TreeMap<>(request.value());changed.put("trace",UUID.randomUUID().toString());var other=decode(encode("wire","PREPARE",changed),"wire","PREPARE");
            var failure=l.endpoint.handle(l.proposer(),other);assertEquals("REJECT",failure.kind());assertEquals("CAPACITY_EXCEEDED",object(failure.value().get("payload")).get("reason"));
            V53MembershipTransportTest.waitFor(()->l.endpoint.usage().waiters()==2);
            l.endpoint.close();first.get(5,TimeUnit.SECONDS);second.get(5,TimeUnit.SECONDS);assertTrue(pending.isCancelled());assertEquals(1,l.calls.get());
        }
    }
    @Test void schedulerExpiresPendingWorkWithoutAnIncomingPoll()throws Exception {
        try(var l=new Local()) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);l.link.set((p,r,k,d)->{entered.countDown();return pending;});
            var request=l.prepare();var call=CompletableFuture.runAsync(()->{
                var error=assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),request));
                assertTrue(error instanceof IOException || error instanceof IllegalArgumentException);assertTrue(error.getMessage().contains("deadline") || error.getMessage().contains("cancel"));
            });
            assertTrue(entered.await(5,TimeUnit.SECONDS));l.base.clock.set(BUDGET);
            V53MembershipTransportTest.waitFor(pending::isCancelled);call.get(5,TimeUnit.SECONDS);
        }
    }
    @Test void validHigherPrepareFencesBeforeTheControlQueueCanAcceptIt()throws Exception {
        try(var l=new Local()) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);l.link.set((p,r,k,d)->{entered.countDown();return pending;});
            var first=l.prepare();var call=CompletableFuture.runAsync(()->assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),first)));
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            var values=new TreeMap<>(first.value());var higher=new TreeMap<>(object(first.value().get("ballot")));higher.put("counter",number(higher.get("counter"))+1);values.put("ballot",higher);
            var next=decode(encode("wire","PREPARE",values),"wire","PREPARE");
            // A failed admission/original-record pull must still revoke the old scope.
            try {assertEquals("REJECT",l.endpoint.handle(l.proposer(),next).kind());}catch(IOException|IllegalArgumentException expected) { /* cancelled original source / failed original fetch */ }
            assertTrue(pending.isCancelled());call.get(5,TimeUnit.SECONDS);
            assertThrows(IllegalArgumentException.class,()->l.base.peer.checkActivationBallot(l.base.f.original.seed.capsule.context.authority(),l.base.campaign.ballot()));
        }
    }
    @Test void foreignProposerCannotFenceAndObservationDoesNotWaitForWriter()throws Exception {
        try(var l=new Local()) {
            var request=l.prepare();l.endpoint.handle(l.proposer(),request);var original=l.base.peer.originalBasis().orElseThrow();
            var values=new TreeMap<>(request.value());var higher=new TreeMap<>(object(request.value().get("ballot")));higher.put("counter",number(higher.get("counter"))+1);values.put("ballot",higher);
            var next=decode(encode("wire","PREPARE",values),"wire","PREPARE");
            assertThrows(Exception.class,()->l.base.peer.observeActivation(l.base.identity(),next));l.base.peer.checkActivation(original,null,false);
            synchronized(l.base.peer) {
                var observation=CompletableFuture.runAsync(()->l.base.peer.observeActivation(l.proposer(),next));observation.get(5,TimeUnit.SECONDS);
                assertThrows(IllegalArgumentException.class,()->l.base.peer.checkActivation(original,null,false));
            }
        }
    }
    @Test void sourceFailureDoesNotManufacturePromiseAndExactRetryDoesNotRestartTask()throws Exception {
        try(var l=new Local()) {
            l.link.set((p,r,k,d)->{l.calls.incrementAndGet();return CompletableFuture.failedFuture(lost());});
            var before=V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory());var request=l.prepare();
            assertThrows(IOException.class,()->l.endpoint.handle(l.proposer(),request));assertEquals(3,l.calls.get());
            assertThrows(IOException.class,()->l.endpoint.handle(l.proposer(),request));assertEquals(3,l.calls.get());
            assertEquals(before,V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory()));
        }
    }
    @Test void closePreservesForeignScratchAndCanFinishAfterItsRemoval()throws Exception {
        try(var l=new Local()) {
            Path foreign=Files.writeString(l.scratch.resolve("foreign"),"operator data");
            assertThrows(IllegalArgumentException.class,l.endpoint::close);assertEquals("operator data",Files.readString(foreign));
            Files.delete(foreign);l.endpoint.close();assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(l.scratch,8));
        }
    }
    @Test void failedDrainRetainsScratchOwnershipUntilWorkerStops()throws Exception {
        try(var l=new Local()) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            l.link.set((p,r,k,d)->{
                entered.countDown();boolean interrupted=false;
                for(;;)try{release.await();break;}catch(InterruptedException error){interrupted=true;}
                if(interrupted)Thread.currentThread().interrupt();
                return CompletableFuture.failedFuture(new IOException("released blocked exchange"));
            });
            var request=l.prepare();var call=CompletableFuture.runAsync(()->assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),request)));
            try {
                assertTrue(entered.await(5,TimeUnit.SECONDS));
                assertThrows(IOException.class,l.endpoint::close);
                assertThrows(ReplicationException.class,()->MembershipOwnership.own(l.scratch.resolve("scope.lock"),false));
            }finally{release.countDown();}
            l.endpoint.close();call.get(5,TimeUnit.SECONDS);
            try(var available=MembershipOwnership.own(l.scratch.resolve("scope.lock"),false)){assertTrue(available.lock().isValid());}
        }
    }
    @Test void localRegistrationKeepsOriginalCampaignStartAndReleasesExportsOnExpiry()throws Exception {
        try(var l=new Local()) {
            Path scratch=temp.resolve("local-registration");
            try(var endpoint=new MembershipActivationEndpoint(l.base.leader,l.base.leaderResources,V53TransferServiceTest.bound(2),
                    (p,r,k,d)->CompletableFuture.failedFuture(new IOException("unused")),verifier(),List.of(),List.of(),scratch,l.base.clock::get,BUDGET)) {
                l.base.clock.set(BUDGET-1);int before=l.base.leaderResources.usage().leases();endpoint.serve(l.base.campaign);
                assertEquals(before+1,l.base.leaderResources.usage().leases());l.base.clock.set(BUDGET);
                V53MembershipTransportTest.waitFor(()->endpoint.usage().scopeEnded() && l.base.leaderResources.usage().leases()==before);
                assertThrows(Exception.class,()->endpoint.serve(l.base.campaign));assertEquals(before,l.base.leaderResources.usage().leases());
            }
        }
    }
    @Test void corruptedOriginalRecordFailsBeforeGrantAndDoesNotRetry()throws Exception {
        try(var l=new Local()) {
            var original=l.link.get();l.link.set((p,r,k,d)->original.exchange(p,r,k,d).thenApply(reply->{
                if(!k.equals("CHUNK"))return reply;
                var value=new TreeMap<>(reply.value());var payload=new TreeMap<>(object(value.get("payload")));byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));bytes[0]^=1;
                payload.put("bytes",Base64.getEncoder().encodeToString(bytes));payload.put("digest",hash(bytes));value.put("payload",payload);
                return decode(encode("wire",reply.kind(),value),"wire",reply.kind());
            }));
            var before=V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory());var request=l.prepare();
            assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),request));int calls=l.calls.get();
            assertEquals(2,calls);assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),request));assertEquals(calls,l.calls.get());
            assertEquals(before,V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory()));
        }
    }
    @Test void waitingForWriterDoesNotResetIncomingBudget()throws Exception {
        try(var l=new Local()) {
            var request=l.prepare();var result=new CompletableFuture<Throwable>();Thread receiver;
            synchronized(l.base.peer) {
                receiver=Thread.ofPlatform().start(()->{try{l.endpoint.handle(l.proposer(),request);result.complete(null);}catch(Throwable error){result.complete(error);}});
                V53MembershipTransportTest.waitFor(()->receiver.getState()==Thread.State.BLOCKED);
                l.base.clock.set(BUDGET);
            }
            var error=result.get(5,TimeUnit.SECONDS);receiver.join(5000);assertFalse(receiver.isAlive());
            assertEquals(0,l.calls.get(),"expired incoming request must not start original-source I/O");
            assertInstanceOf(IllegalArgumentException.class,error);assertTrue(error.getMessage().contains("deadline"));
        }
    }
    @Test void correlatedHigherSourceRejectionFencesButForeignReplyDoesNot()throws Exception {
        for(boolean foreign:List.of(false,true))try(var l=new Local()) {
            l.link.set((peer,request,kind,deadline)->{
                l.calls.incrementAndGet();var values=new TreeMap<>(request.value());
                values.put("sender",request.value().get("recipient"));values.put("recipient",request.value().get("sender"));
                if(foreign)values.put("root","0".repeat(64));
                var higher=new TreeMap<>(object(request.value().get("ballot")));higher.put("counter",number(higher.get("counter"))+1);
                values.put("payload",Map.of("promised",higher,"reason","STALE_EPOCH"));
                return CompletableFuture.completedFuture(decode(encode("wire","REJECT",values),"wire","REJECT"));
            });
            var request=l.prepare();assertThrows(Exception.class,()->l.endpoint.handle(l.proposer(),request));assertEquals(1,l.calls.get());
            if(foreign)l.base.peer.checkActivationBallot(l.base.f.original.seed.capsule.context.authority(),l.base.campaign.ballot());
            else {
                assertThrows(IllegalArgumentException.class,()->l.base.peer.checkActivationBallot(l.base.f.original.seed.capsule.context.authority(),l.base.campaign.ballot()));
                assertTrue(l.endpoint.usage().scopeEnded());
            }
        }
    }
    @Test void realTcpEndpointOwnsPrepareSourcesAndSelectedInstallationAtThreeSizes()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-activation-endpoint/run-"+UUID.randomUUID()));
        System.out.println("v53ActivationEndpointEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();
                var endpoints=new ArrayList<MembershipActivationEndpoint>();var refs=new ArrayList<AtomicReference<MembershipTransport>>();
                var events=new TreeMap<String,List<String>>();var pulls=new ArrayList<MembershipSourcePull>();var wire=new ArrayList<Map<String,Object>>();
                var allWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var queue=resources();var bound=V53TransferServiceTest.bound(2);
                try {
                    for(int n=0;n<size;n++) {
                        var target=f.request.targets().get(n);var r=resources();budgets.add(r);var steps=Collections.synchronizedList(new ArrayList<String>());events.put(target.identity().nodeId().value(),steps);
                        var owner=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),r,verifier(),MembershipGrantJournal.MAXIMUM,steps::add);owners.add(owner);
                        var ref=new AtomicReference<MembershipTransport>();refs.add(ref);
                        var endpoint=new MembershipActivationEndpoint(owner,r,bound,(p,request,k,d)->ref.get().exchange(p,request,k,d),verifier(),List.of(),List.of(),temp.resolve("tcp-"+size+"-"+n),System::nanoTime,BUDGET);endpoints.add(endpoint);
                        ref.set(group.start(n,endpoint,(event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE"))allWire.add(V53SelectedPullTest.wire(request,response));},bound,r));
                    }
                    try(var campaign=new MembershipActivation(owners.getFirst(),queue,System::nanoTime,BUDGET)) {
                        endpoints.getFirst().serve(campaign);var images=new TreeMap<String,byte[]>();
                        assertTrue(endpoints.getFirst().activationProgress().isEmpty(),"local serving is not incoming progress");
                        for(int n=1;n<=size/2;n++) {
                            var peer=group.identities.get(n);var request=campaign.prepare(peer);var reply=refs.getFirst().get().exchange(peer,request,"PROMISE",campaign.started()+BUDGET).get(30,TimeUnit.SECONDS);wire.add(V53SelectedPullTest.wire(request,reply));
                            var progress=endpoints.get(n).activationProgress().orElseThrow();
                            assertEquals(MembershipActivationEndpoint.ActivationStage.GRANTED,progress.stage());assertEquals(campaign.ballot(),progress.ballot());
                            var pull=new MembershipSourcePull(group.capsule,group.identities.getFirst(),peer,campaign.ballot(),UUID.randomUUID(),queue,bound,
                                    refs.getFirst().get()::exchange,()->owners.getFirst().checkActivation(campaign.ownSource().basis,null,false),System::nanoTime,campaign.started(),BUDGET);pulls.add(pull);
                            var received=pull.fetch(temp.resolve("tcp-promised-"+size+"-"+n),(String)object(reply.value().get("payload")).get("basis"));images.putAll(received.images());campaign.promised(peer,reply,received,verifier(),List.of());
                        }
                        campaign.installLocal(List.of(),images);
                        for(int n=1;n<=size/2;n++) {
                            var peer=group.identities.get(n);var request=campaign.installation(peer);var reply=refs.getFirst().get().exchange(peer,request,"INSTALL_ACK",campaign.started()+BUDGET).get(30,TimeUnit.SECONDS);
                            wire.add(V53SelectedPullTest.wire(request,reply));campaign.installed(peer,reply);
                            assertEquals(MembershipActivationEndpoint.ActivationStage.INSTALLED,endpoints.get(n).activationProgress().orElseThrow().stage());
                        }
                        assertEquals(MembershipActivation.State.INSTALLED,campaign.state());Files.write(raw.resolve("selected.gsr"),campaign.votingSelection().bytes());f.snapshot("installed");
                        Files.write(raw.resolve("wire.json"),canonical(wire,1024*1024));
                        Files.write(raw.resolve("events.json"),canonical(events.entrySet().stream().map(row->Map.of("node",row.getKey(),"events",row.getValue())).toList(),1024*1024));
                        Files.write(evidence.resolve("stable-"+size+"-network.json"),canonical(allWire,16*1024*1024));
                        cases.add(Map.of("size",size,"selected",campaign.sources().size(),"installed",campaign.sources().size()));
                    }
                }finally {
                    for(var pull:pulls)pull.close();for(var endpoint:endpoints)endpoint.close();for(var transport:group.transports)transport.close();for(var owner:owners)owner.close();
                    for(var r:budgets)assertEquals(0,r.usage().leases());assertEquals(0,queue.usage().leases());
                }
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-activation-endpoint-v1","status","PASS","cases",cases,"network",true,"publicRuntime",false,"automaticCampaign",false),65536));
    }
}
