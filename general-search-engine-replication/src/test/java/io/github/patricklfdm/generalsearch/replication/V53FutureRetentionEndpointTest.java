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
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53FutureRetentionEndpointTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(90);
    final class Group implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture fixture;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipGrantJournal.Applied> applied=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<AtomicReference<MembershipBallotAllocator.Cut>> hooks=new ArrayList<>();
        final List<Map<String,Object>> events=new ArrayList<>();
        final List<Map<String,Object>> timeline=Collections.synchronizedList(new ArrayList<>());
        Group(int size,boolean nativeApply)throws Exception {
            Path raw=Files.createDirectories(Path.of("target/v53-future-endpoint/run-"+UUID.randomUUID()));
            System.out.println("v53FutureEndpointEvidence="+raw.toAbsolutePath());System.out.flush();
            fixture=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(
                    Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),size,false));
            fixture.ownedHistory=true;fixture.nativeApplication=true;
            for(var t:fixture.request.targets())try(var owner=fixture.open(t,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
            fixture.snapshot("retaining-genesis");fixture.campaign(1);
            fixture.observer=(target,operation,event)->{if(operation.equals("apply-1"))throw new V53NativeApplicationTest.Stop();};
            assertThrows(V53NativeApplicationTest.Stop.class,()->fixture.publish(1,false));
            fixture.observer=(target,operation,event)->{};fixture.observations.clear();fixture.snapshot("certified");
            for(var t:fixture.request.targets()) {
                var budget=new MembershipResources(512*MembershipResources.MIB);budgets.add(budget);
                var hook=new AtomicReference<MembershipBallotAllocator.Cut>(event->{});hooks.add(hook);
                var trace=new ArrayList<String>();events.add(Map.of("node",t.identity().nodeId().value(),"events",trace));
                var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),fixture.result.root(),t.identity(),budget,
                        MembershipGrantJournal.MAXIMUM,event->{trace.add(event);timeline.add(Map.of("node",t.identity().nodeId().value(),"event",event));hook.get().at(event);});owners.add(owner);
                if(nativeApply)applied.add(owner.applyCurrent(builder().configuration(),t.materialization()));
            }
            fixture.snapshot("before-endpoint");
        }
        MembershipIdentity peer(){return fixture.request.targets().getLast().identity();}
        MembershipFutureRetentionIntent intent()throws Exception {
            return owners.getFirst().futureRetentionIntent(peer(),fixture.ballot,owners.getFirst().pendingPublication(applied.getFirst()));
        }
        Decoded request(int receiver,MembershipFutureRetentionIntent intent)throws Exception {
            var source=owners.getFirst();return MembershipActivation.frame("FUTURE_RETENTION_INTENT",source.activationContext(),source.activationIdentity(),
                    owners.get(receiver).activationIdentity(),fixture.ballot,UUID.randomUUID(),1,intent.payload);
        }
        Decoded deliver(int receiver,Decoded request)throws Exception{return owners.get(receiver).recordFutureRetention(owners.getFirst().activationIdentity(),request);}
        Map<String,String> files(int receiver)throws Exception{return V53ReplayFilesTest.files(fixture.request.targets().get(receiver).replicaDirectory());}
        void publishAll()throws Exception {
            var acks=applied.stream().map(a->a.endorsement().acknowledgement()).toList();var observed=new HashSet<MembershipContext.Owned>();
            applied.forEach(a->observed.add(a.endorsement().owned()));
            for(int i=0;i<owners.size();i++)owners.get(i).publishCurrent(applied.get(i),acks,observed,List.of());
        }
        void nextBarrier()throws Exception {
            var copies=new ArrayList<MembershipFloor.Copy>();for(var owner:owners)copies.add(owner.floorCopyCurrent());
            for(var owner:owners){owner.establishFloor(copies);owner.retireInactive();owner.releaseFloor();owner.rotateJournal();}
            var context=owners.getFirst().activationContext();
            var entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),"index",number(context.cut.get("index"))+1,
                    "previous",context.cut.get("entry"),"origin",fixture.ballot,"kind","BARRIER","payload",hash(new byte[0]))),"records","ENTRY");
            var accepts=new HashSet<MembershipContext.Owned>();for(var owner:owners)accepts.add(owner.acceptCurrent(entry,new byte[0]));
            var accepted=MembershipPendingAccept.decode(Files.readAllBytes(fixture.request.targets().getFirst().replicaDirectory().resolve(MembershipPendingAccept.FILE))).accept();
            var fields=new TreeMap<>(accepted.value());fields.put("accepts",V53PublicationLifetimeTest.witnesses(context.root,"ACCEPT",accepted,accepts));
            var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<MembershipContext.Owned>();
            for(var owner:owners)proofs.add(owner.proveCurrent(proof,accepts));
            fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(context.root,"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var phased=new HashSet<>(accepts);phased.addAll(proofs);
            for(var owner:owners)owner.certifyCurrent(certificate,phased);
            applied.clear();for(int i=0;i<owners.size();i++)applied.add(owners.get(i).applyCurrent(builder().configuration(),fixture.request.targets().get(i).materialization()));
        }
        @Override public void close()throws Exception {
            for(var owner:owners)owner.close();for(var budget:budgets)assertEquals(0,budget.usage().leases());
            Files.write(fixture.raw.resolve("endpoint-events.json"),canonical(events,8*1024*1024));
            Files.write(fixture.raw.resolve("timeline.json"),canonical(timeline,8*1024*1024));
            fixture.snapshot("after-endpoint");V53NativeApplicationTest.save(fixture);
        }
    }
    @Test void pendingRecordingServicesProgressOutsideTheWriterWithoutInventingAnAck()throws Exception {
        try(var group=new Group(3,true)) {
            var requests=new LinkedHashMap<MembershipIdentity,Decoded>();var pending=new LinkedHashMap<MembershipIdentity,CompletableFuture<Decoded>>();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{requests.put(peer,request);var f=new CompletableFuture<Decoded>();pending.put(peer,f);return f;};
            var pulses=new AtomicInteger();
            MembershipSourcePull.Guard pulse=()->{
                assertFalse(Thread.holdsLock(group.owners.getFirst()));pulses.incrementAndGet();
                var peer=group.owners.get(1).activationIdentity();
                try{pending.get(peer).complete(group.deliver(1,requests.get(peer)));}
                catch(Exception error){throw new IOException(error);}
            };
            try(var quorum=new MembershipFutureRetentionQuorum(group.owners.getFirst(),group.peer(),group.fixture.ballot,
                    group.owners.getFirst().pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),link,System::nanoTime,System.nanoTime(),BUDGET,pulse)) {
                assertEquals(Set.of("node-1","node-2"),quorum.record().voters());
                assertEquals(1,pulses.get());assertTrue(pending.get(group.peer()).isCancelled());
                assertEquals(2,requests.size());
            }
        }
    }
    @Test void progressCannotRenewOriginalRecordingDeadlineAndCancelsPendingPeers()throws Exception {
        try(var group=new Group(3,true)) {
            long started=System.nanoTime();var clock=new AtomicLong(started);var pending=new ArrayList<CompletableFuture<Decoded>>();
            var deadlines=new ArrayList<Long>();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{deadlines.add(deadline);var f=new CompletableFuture<Decoded>();pending.add(f);return f;};
            try(var quorum=new MembershipFutureRetentionQuorum(group.owners.getFirst(),group.peer(),group.fixture.ballot,
                    group.owners.getFirst().pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),link,clock::get,started,BUDGET,()->clock.set(started+BUDGET))) {
                var error=assertThrows(IllegalArgumentException.class,quorum::record);
                assertEquals("original future quorum deadline/closed",error.getMessage());
                assertEquals(List.of(started+BUDGET,started+BUDGET),deadlines);
                assertTrue(pending.stream().allMatch(CompletableFuture::isCancelled));
            }
        }
    }
    @Test void realNetworkReceiverUsesOwnNativeProofIncludingIntendedTargetVoter()throws Exception {
        for(int size:List.of(3,4,5))try(var group=new Group(size,true)) {
            var intent=group.intent();var endpoints=new ArrayList<MembershipActivationEndpoint>();var transports=new ArrayList<MembershipTransport>();
            var links=new ArrayList<AtomicReference<MembershipTransport>>();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var collecting=new AtomicBoolean();var dropped=new AtomicBoolean();var sent=new ConcurrentHashMap<String,List<String>>();
            for(int i=0;i<size;i++)links.add(new AtomicReference<>());
            try {
                for(int i=0;i<size;i++) {
                    int n=i;var owner=group.owners.get(i);var bounds=ReplicationBounds.defaults();
                    var endpoint=new MembershipActivationEndpoint(owner,group.budgets.get(i),bounds,
                            (peer,request,kind,deadline)->links.get(n).get().exchange(peer,request,kind,deadline),List.of(),List.of(),
                            temp.resolve("endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);endpoints.add(endpoint);
                    var transport=new MembershipTransport(owner.activationCapsule(),owner.activationIdentity(),bounds,group.budgets.get(i),endpoint,
                            (event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                wire.add(V53SelectedPullTest.wire(request,response));
                                if(size==3 && n==2 && collecting.get() && dropped.compareAndSet(false,true))throw new IOException("lost original future ACK");
                            }});
                    transports.add(transport);links.get(i).set(transport);
                }
                var digests=new HashSet<String>();
                for(int i=1;i<size;i++) {
                    var request=group.request(i,intent);var remote=group.owners.get(i);
                    var response=transports.getFirst().exchange(remote.activationIdentity(),request,"FUTURE_RETENTION_ACK",System.nanoTime()+BUDGET).get(90,TimeUnit.SECONDS);
                    MembershipWire.correlated(request,response,"FUTURE_RETENTION_ACK");var value=object(response.value().get("payload"));
                    assertEquals(intent.digest,value.get("intent"));assertEquals("FUTURE",value.get("storage"));assertEquals(1L,value.get("revision"));
                    var retained=remote.futureRetentionState();assertTrue(digests.add(retained.digest));assertEquals(retained.digest,value.get("digest"));
                    assertEquals(remote.activationIdentity().nodeId().value(),retained.record("selector.gsr").value().get("node"));
                    assertEquals(remote.activationIdentity().nodeId().value(),retained.record("ack.gsr").value().get("voter"));
                    assertEquals(intent.upper,retained.target());assertEquals(group.peer(),retained.peers.getFirst().identity());
                    var before=group.files(i);assertArrayEquals(response.bytes(),group.deliver(i,request).bytes());assertEquals(before,group.files(i));
                    assertEquals(0L,remote.activationContext().cut.get("index"));
                }
                assertFalse(group.owners.getFirst().futureRetentionState().pending());
                collecting.set(true);
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                    sent.computeIfAbsent(peer.nodeId().value(),k->Collections.synchronizedList(new ArrayList<>())).add(request.digest());
                    if(size==3 && peer.nodeId().value().equals("node-2"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline voter",null));
                    return transports.getFirst().exchange(peer,request,kind,deadline).thenApply(response->{
                        group.timeline.add(Map.of("node",peer.nodeId().value(),"event","FUTURE_ACK_RECEIVED","digest",response.digest()));return response;});
                };
                try(var quorum=new MembershipFutureRetentionQuorum(group.owners.getFirst(),group.peer(),group.fixture.ballot,
                        group.owners.getFirst().pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),link,System::nanoTime,System.nanoTime(),BUDGET)) {
                    var recorded=quorum.record();recorded.check();assertEquals(size/2+1,recorded.voters().size());assertEquals(intent.digest,recorded.intent());
                    group.timeline.add(Map.of("node","node-1","event","FUTURE_QUORUM_COMPLETE"));group.fixture.snapshot("recorded-quorum");
                    assertTrue(group.owners.getFirst().futureRetentionState().pending());
                    if(size==3){assertTrue(dropped.get());assertEquals(Set.of("node-1","node-3"),recorded.voters());assertEquals(2,sent.get("node-3").size());assertEquals(1,new HashSet<>(sent.get("node-3")).size());}
                    var requests=new TreeMap<>(sent).entrySet().stream().map(row->Map.of("node",row.getKey(),"digests",List.copyOf(row.getValue()))).toList();
                    Files.write(group.fixture.raw.resolve("quorum.json"),canonical(Map.of("intent",recorded.intent(),"voters",recorded.voters().stream().sorted().toList(),"requests",requests,"lostAck",dropped.get()),65536));
                    group.owners.getFirst().observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",group.owners.getFirst().activationIdentity().storageId().toString()));
                    assertThrows(IllegalArgumentException.class,recorded::check);
                }
            }finally {
                for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();
                Files.write(group.fixture.raw.resolve("wire.json"),canonical(wire,1024*1024));
            }
        }
    }
    @Test void nativeApplicationMustExistInThisOwnerNotJustOnDiskOrAtSender()throws Exception {
        try(var group=new Group(3,false)) {
            var t=group.fixture.request.targets().getFirst();group.applied.add(group.owners.getFirst().applyCurrent(builder().configuration(),t.materialization()));
            var request=group.request(1,group.intent());var before=group.files(1);
            var response=group.deliver(1,request);assertEquals("REJECT",response.kind());
            assertEquals("NOT_READY",object(response.value().get("payload")).get("reason"));assertEquals(before,group.files(1));
            assertFalse(group.owners.get(1).futureRetentionState().pending());
        }
    }
    @Test void minorityCannotProduceRecordingAndRetriesOnlyIdenticalFrames()throws Exception {
        try(var group=new Group(3,true)) {
            var sent=new TreeMap<String,List<String>>();
            MembershipSourcePull.Link failed=(peer,request,kind,deadline)->{
                sent.computeIfAbsent(peer.nodeId().value(),k->new ArrayList<>()).add(request.digest());
                return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"unavailable",null));
            };
            try(var quorum=new MembershipFutureRetentionQuorum(group.owners.getFirst(),group.peer(),group.fixture.ballot,
                    group.owners.getFirst().pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),failed,System::nanoTime,System.nanoTime(),BUDGET)) {
                assertEquals("future retention quorum unavailable",assertThrows(IllegalArgumentException.class,quorum::record).getMessage());
            }
            for(var values:sent.values()){assertEquals(3,values.size());assertEquals(1,new HashSet<>(values).size());}
            assertTrue(group.owners.getFirst().futureRetentionState().pending());
            for(var owner:group.owners.subList(1,3))assertFalse(owner.futureRetentionState().pending());
        }
    }
    @Test void closingDuringExchangeSubmissionCancelsTheReturnedFuture()throws Exception {
        try(var group=new Group(3,true)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                entered.countDown();try{if(!release.await(20,TimeUnit.SECONDS))throw new AssertionError("release missing");}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new CompletionException(error);}return pending;
            };
            var executor=Executors.newSingleThreadExecutor();
            try(var quorum=new MembershipFutureRetentionQuorum(group.owners.getFirst(),group.peer(),group.fixture.ballot,
                    group.owners.getFirst().pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),link,System::nanoTime,System.nanoTime(),BUDGET)) {
                var running=executor.submit(()->assertThrows(IllegalArgumentException.class,quorum::record));
                assertTrue(entered.await(20,TimeUnit.SECONDS));quorum.close();release.countDown();running.get(20,TimeUnit.SECONDS);assertTrue(pending.isCancelled());
            }finally{release.countDown();executor.shutdownNow();assertTrue(executor.awaitTermination(20,TimeUnit.SECONDS));}
        }
    }
    @Test void lateAndUnrelatedRepliesCannotCompleteRecording()throws Exception {
        try(var group=new Group(3,true)) {
            for(boolean late:List.of(true,false)) {
                long started=System.nanoTime();var clock=new AtomicLong(started);
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                    try {
                        int index=Integer.parseInt(peer.nodeId().value().substring(5))-1;var response=group.deliver(index,request);
                        if(late)clock.set(started+BUDGET);
                        else {var value=new TreeMap<>(response.value());var payload=new TreeMap<>(object(value.get("payload")));payload.put("intent","f".repeat(64));value.put("payload",payload);response=decode(encode("wire","FUTURE_RETENTION_ACK",value),"wire","FUTURE_RETENTION_ACK");}
                        return CompletableFuture.completedFuture(response);
                    }catch(Exception error){return CompletableFuture.failedFuture(error);}
                };
                try(var quorum=new MembershipFutureRetentionQuorum(group.owners.getFirst(),group.peer(),group.fixture.ballot,
                        group.owners.getFirst().pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),link,clock::get,started,BUDGET)) {
                    var error=assertThrows(IllegalArgumentException.class,quorum::record);
                    assertEquals(late?"original future quorum deadline/closed":"future acknowledgement changed intent/store",error.getMessage());
                }
            }
        }
    }
    @Test void invalidBindingsRefuseBeforeChangingFiles()throws Exception {
        try(var group=new Group(3,true)) {
            var request=group.request(1,group.intent());var before=group.files(1);
            for(String mutation:List.of("selection","certificate","lower","parent","upper","peer","root","proposer")) {
                var value=new TreeMap<>(request.value());var payload=new TreeMap<>(object(value.get("payload")));
                switch(mutation) {
                    case "selection","certificate"->payload.put(mutation,"f".repeat(64));
                    case "lower","parent","upper"->{var anchor=new TreeMap<>(object(payload.get(mutation)));anchor.put("application","f".repeat(64));payload.put(mutation,anchor);}
                    case "peer"->{var identity=new TreeMap<>(object(payload.get("peer")));identity.put("storage",UUID.randomUUID().toString());payload.put("peer",identity);}
                    case "root"->value.put("root","f".repeat(64));
                    case "proposer"->{var ballot=new TreeMap<>(object(value.get("ballot")));ballot.put("proposer","node-3");value.put("ballot",ballot);}
                    default->throw new AssertionError(mutation);
                }
                value.put("payload",payload);var invalid=decode(encode("wire","FUTURE_RETENTION_INTENT",value),"wire","FUTURE_RETENTION_INTENT");
                assertThrows(IllegalArgumentException.class,()->group.deliver(1,invalid),mutation);assertEquals(before,group.files(1),mutation);
            }
        }
    }
    @Test void delayedDuplicateAfterPublicationUsesCurrentLedgerAndNeverRegressesRealObservation()throws Exception {
        try(var group=new Group(3,true)) {
            var request=group.request(1,group.intent());group.deliver(1,request);
            var acknowledgements=group.applied.stream().map(a->a.endorsement().acknowledgement()).toList();var observed=new HashSet<MembershipContext.Owned>();
            group.applied.forEach(a->observed.add(a.endorsement().owned()));
            for(int i=0;i<3;i++)group.owners.get(i).publishCurrent(group.applied.get(i),acknowledgements,observed,List.of());
            var owner=group.owners.get(1);assertFalse(owner.futureRetentionState().pending());
            var response=group.deliver(1,request);assertEquals("CURRENT",object(response.value().get("payload")).get("storage"));
            assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(group.peer())));
            owner.retainPeerObservation(group.owners.getLast().floorCopyCurrent());var before=group.files(1);
            response=group.deliver(1,request);assertEquals("CURRENT",object(response.value().get("payload")).get("storage"));
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(group.peer())));assertEquals(before,group.files(1));
        }
    }
    @Test void earlierAmbiguityAndDifferentLowerEndpointsRequireRealCopyReconciliation()throws Exception {
        try(var group=new Group(3,true)) {
            group.deliver(1,group.request(1,group.intent()));group.publishAll();group.nextBarrier();
            var request=group.request(1,group.intent());var before=group.files(1);var response=group.deliver(1,request);
            assertEquals("REJECT",response.kind());assertEquals("CAPACITY_EXCEEDED",object(response.value().get("payload")).get("reason"));assertEquals(before,group.files(1));
            var actual=group.owners.getLast().floorCopyCurrent();group.owners.get(1).retainPeerObservation(actual);before=group.files(1);
            response=group.deliver(1,request);assertEquals("CAPACITY_EXCEEDED",object(response.value().get("payload")).get("reason"));assertEquals(before,group.files(1));
            group.owners.getFirst().retainPeerObservation(actual);var reconciled=group.request(1,group.intent());
            assertEquals("FUTURE_RETENTION_ACK",group.deliver(1,reconciled).kind());before=group.files(1);
            response=group.deliver(1,request);assertEquals("CAPACITY_EXCEEDED",object(response.value().get("payload")).get("reason"));assertEquals(before,group.files(1));
            assertEquals(1L,group.owners.get(1).futureRetentionState().peers.getFirst().lower().cut().get("index"));
        }
    }
    @Test void higherPromiseAfterForcePreventsAckWithoutDeletingDurableIntent()throws Exception {
        try(var group=new Group(3,true)) {
            var request=group.request(1,group.intent());var owner=group.owners.get(1);
            group.hooks.get(1).set(event->{if(event.equals("FUTURE_RETENTION_PARENT_FORCED"))owner.observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",group.owners.getFirst().activationIdentity().storageId().toString()));});
            assertThrows(IllegalArgumentException.class,()->group.deliver(1,request));
            var t=group.fixture.request.targets().get(1);var state=MembershipFutureRetentionFiles.decodeOwned(Files.readAllBytes(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE)),group.fixture.result.root().manifestDigest(),t.identity());
            assertTrue(state.pending());assertEquals(1,state.revision);
            assertFalse(list(group.events.get(1).get("events")).contains("FUTURE_RETENTION_ACK_BEFORE_RETURN"));
        }
    }
}
