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
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53SlotEndpointTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(120);
    final class Network implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture f;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> resources=new ArrayList<>();
        final List<MembershipSlotEndpoint> endpoints=new ArrayList<>();
        final List<MembershipTransport> transports=new ArrayList<>();
        final List<AtomicReference<MembershipTransport>> links=new ArrayList<>();
        final List<AtomicReference<MembershipBallotAllocator.Cut>> hooks=new ArrayList<>();
        final List<Map<String,Object>> events=Collections.synchronizedList(new ArrayList<>()),wire=Collections.synchronizedList(new ArrayList<>());
        final List<Map<String,Object>> checkpointReceipts=Collections.synchronizedList(new ArrayList<>());
        final List<Map<String,Object>> timings=Collections.synchronizedList(new ArrayList<>());
        final AtomicBoolean noOutgoing=new AtomicBoolean();
        final AtomicReference<String> drop=new AtomicReference<>("");
        final AtomicReference<java.util.function.Consumer<Decoded>> beforeOutgoing=new AtomicReference<>(request->{});
        final AtomicReference<String> incomingFailure=new AtomicReference<>("");
        final AtomicInteger failedArrivals=new AtomicInteger();
        final AtomicReference<MembershipTransport.Reason> checkpointFailure=new AtomicReference<>();
        final AtomicInteger checkpointAttempts=new AtomicInteger();
        final AtomicReference<CountDownLatch> holdCheckpoints=new AtomicReference<>();
        final List<CompletableFuture<Decoded>> heldCheckpoints=Collections.synchronizedList(new ArrayList<>());
        final AtomicReference<Runnable> beforeWrite=new AtomicReference<>(()->{});
        final AtomicReference<Runnable> beforeClock=new AtomicReference<>(()->{});
        final AtomicLong offset=new AtomicLong();
        final Decoded entry,accept;
        final byte[] payload;
        Network(int size,boolean data)throws Exception {
            Path raw=Files.createDirectories(Path.of("target/v53-slot-endpoint/run-"+UUID.randomUUID()));System.out.println("v53SlotEndpointEvidence="+raw.toAbsolutePath());
            f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve(UUID.randomUUID().toString())),size,false));
            f.ownedHistory=true;f.nativeApplication=true;
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
            f.snapshot("retaining-genesis");f.campaign(1);if(data)f.publish(1,false);f.snapshot("before-voting");
            for(var target:f.request.targets()) {
                var budget=new MembershipResources(512*MembershipResources.MIB);resources.add(budget);
                var hook=new AtomicReference<MembershipBallotAllocator.Cut>(event->{});hooks.add(hook);links.add(new AtomicReference<>());
                owners.add(MembershipGrantJournal.openRetainingFuturePeers(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),budget,
                        MembershipGrantJournal.MAXIMUM,event->{events.add(Map.of("node",target.identity().nodeId().value(),"event",event));
                            timings.add(Map.of("node",target.identity().nodeId().value(),"event",event,"nanos",System.nanoTime()));hook.get().at(event);}));
            }
            if(data)try(var encoder=new ReplicaApplication<>(builder().configuration(),f.request.targets().getFirst().materialization(),ReplicationBounds.defaults())) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(456,"native-payload-"+"x".repeat(1024)))));
            }else payload=new byte[0];
            var context=owners.getFirst().activationContext();entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                    "index",number(context.cut.get("index"))+1,"previous",context.cut.get("entry"),"origin",f.ballot,"kind",data?"DATA":"BARRIER","payload",hash(payload))),"records","ENTRY");
            owners.getFirst().acceptCurrent(entry,payload);accept=owners.getFirst().voting(resources.getFirst()).record("ACCEPT").orElseThrow();
            Files.write(raw.resolve("entry.gsr"),entry.bytes());Files.write(raw.resolve("payload.bin"),payload);
            for(int i=0;i<size;i++) {
                int index=i;var owner=owners.get(i);var bounds=ReplicationBounds.defaults();
                var endpoint=new MembershipSlotEndpoint(owner,resources.get(i),bounds,(peer,request,kind,deadline)->{
                    if(noOutgoing.get())throw new AssertionError("completed duplicate must not reacquire sources");
                    beforeOutgoing.get().accept(request);
                    if(index==size-1 && request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1) {
                        var hold=holdCheckpoints.get();if(hold!=null){var pending=new CompletableFuture<Decoded>();heldCheckpoints.add(pending);hold.countDown();return pending;}
                        var failure=checkpointFailure.get();if(peer.nodeId().value().equals("node-1") && failure!=null) {
                            checkpointAttempts.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(failure,"injected checkpoint owner failure",null));
                        }
                    }
                    return links.get(index).get().exchange(peer,request,kind,deadline);
                },()->{beforeClock.get().run();return System.nanoTime()+offset.get();},System.nanoTime(),BUDGET,builder().configuration(),f.request.targets().get(i).materialization(),
                (event,statement,ack)->checkpointReceipts.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event",event,"statement",HexFormat.of().formatHex(statement.bytes()),"ack",HexFormat.of().formatHex(ack.bytes()))));endpoints.add(endpoint);
                var transport=new MembershipTransport(owner.activationCapsule(),owner.activationIdentity(),bounds,resources.get(i),(sender,request)->{
                    if(index==size-1 && request.kind().equals("ACCEPT") && !incomingFailure.get().isEmpty()) {
                        failedArrivals.incrementAndGet();if(incomingFailure.get().equals("IO"))throw new IOException("injected unavailable receiver");
                        var wrong=new TreeMap<>(request.value());wrong.put("sender",request.value().get("recipient"));wrong.put("recipient",request.value().get("sender"));
                        wrong.put("payload",Map.of("entry","0".repeat(64),"receipt","0".repeat(64)));return decode(encode("wire","ACCEPT_ACK",wrong),"wire","ACCEPT_ACK");
                    }
                    return endpoint.handle(sender,request);
                },(event,request,response)->{
                    timings.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event",event,"kind",request.kind(),"nanos",System.nanoTime()));
                    if(event.equals("BEFORE_REQUEST_WRITE") && request.kind().equals("ACCEPT"))beforeWrite.get().run();
                    if(event.equals("BEFORE_REQUEST_WRITE") && request.kind().equals("PUBLISH"))events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","PUBLICATION_SEND_BOUNDARY","request",request.digest()));
                    if(event.equals("AFTER_RESPONSE_READ"))events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest()));
                    if(event.equals("BEFORE_RESPONSE_WRITE")) {
                        String pending=drop.get();boolean lost=pending.equals(response.kind()) && drop.compareAndSet(pending,"");var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",lost);wire.add(row);
                        events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest()));
                        if(lost)throw new IOException("lost completed slot response");
                    }
                });transports.add(transport);links.get(i).set(transport);
            }
        }
        Decoded request(int index,String kind,Map<String,Object> payload)throws Exception {
            return MembershipActivation.frame(kind,owners.getFirst().activationContext(),owners.getFirst().activationIdentity(),owners.get(index).activationIdentity(),f.ballot,UUID.randomUUID(),1,payload);
        }
        Decoded send(int index,Decoded request)throws Exception {
            timings.add(Map.of("node","node-1","event","CONTROL_START","kind",request.kind(),"nanos",System.nanoTime()));
            try {
            if(Set.of("ACCEPT","PROOF","APPLY").contains(request.kind()))return MembershipSlotDelivery.deliver(owners.getFirst(),owners.get(index).activationIdentity(),request,
                    resources.getFirst(),transports.getFirst(),System::nanoTime,System.nanoTime(),BUDGET);
            return transports.getFirst().exchange(owners.get(index).activationIdentity(),request,request.kind()+"_ACK",System.nanoTime()+BUDGET).get(120,TimeUnit.SECONDS);
            }finally{timings.add(Map.of("node","node-1","event","CONTROL_END","kind",request.kind(),"nanos",System.nanoTime()));}
        }
        MembershipContext.Owned observation(int index,Decoded record)throws Exception {
            if(index==0)return owners.getFirst().voting(resources.getFirst()).observation(record);
            try(var pull=new MembershipSourcePull(owners.getFirst().activationCapsule(),owners.getFirst().activationIdentity(),owners.get(index).activationIdentity(),f.ballot,UUID.randomUUID(),
                    resources.getFirst(),ReplicationBounds.defaults(),transports.getFirst()::exchange,()->owners.getFirst().voting(resources.getFirst()).check(),System::nanoTime,System.nanoTime(),BUDGET)) {
                return pull.fetchVoteObservation(record);
            }
        }
        Decoded applyAll()throws Exception {
            int size=owners.size();for(int i=1;i<size;i++)send(i,request(i,"ACCEPT",Map.of("acceptance",accept.digest())));
            f.snapshot("after-accept");var accepts=new HashSet<MembershipContext.Owned>();for(int i=0;i<size;i++)accepts.add(observation(i,accept));
            var fields=new TreeMap<>(accept.value());fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",accept,accepts));
            var proof=decode(encode("records","PROOF",fields),"records","PROOF");owners.getFirst().proveCurrent(proof,accepts);
            for(int i=1;i<size;i++)send(i,request(i,"PROOF",Map.of("proof",proof.digest())));f.snapshot("after-proof");
            var proofs=new HashSet<MembershipContext.Owned>();for(int i=0;i<size;i++)proofs.add(observation(i,proof));
            fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");accepts.addAll(proofs);owners.getFirst().certifyCurrent(certificate,accepts);
            owners.getFirst().applyCurrent(builder().configuration(),f.request.targets().getFirst().materialization());
            for(int i=1;i<size;i++)send(i,request(i,"APPLY",Map.of("certificate",certificate.digest(),"selection",owners.getFirst().originalSelection().orElseThrow().digest())));
            for(int i=0;i<size;i++)V53JournalApplicationTest.copy(f.request.targets().get(i).replicaDirectory().resolve("applied-end"),f.raw.resolve("end-node-"+(i+1)));
            Files.write(f.raw.resolve("proof.gsr"),proof.bytes());Files.write(f.raw.resolve("certificate.gsr"),certificate.bytes());f.snapshot("after-application");return certificate;
        }
        Decoded publish(int index)throws Exception {
            var local=owners.getFirst();var applied=local.voting(resources.getFirst()).application().orElseThrow();
            var recording=new ArrayList<CompletableFuture<Decoded>>();
            try(var quorum=new MembershipFutureRetentionQuorum(local,owners.get(index).activationIdentity(),f.ballot,local.pendingPublication(applied),resources.getFirst(),(peer,request,kind,deadline)->{
                    var future=transports.getFirst().exchange(peer,request,kind,deadline);recording.add(future);
                    // Retain an observation of the original bounded exchange even
                    // when the collector cancels its no-longer-needed waiter.
                    return future.thenApply(value->value);
                },System::nanoTime,System.nanoTime(),BUDGET)) {
                var ready=quorum.record();events.add(Map.of("node","node-1","event","FUTURE_QUORUM_COMPLETE","voters",ready.voters().stream().sorted().toList()));
                // Freeze the physical observation only after healthy in-flight
                // requests settle; this does not add voters to the recorded quorum.
                for(var future:recording)future.get(20,TimeUnit.SECONDS);
                f.snapshot("recorded-quorum");
                return ready.dispatch(transports.getFirst());
            }
        }
        @Override public void close()throws Exception {
            for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();for(var owner:owners)owner.close();
            for(var budget:resources)assertEquals(0,budget.usage().leases());
            Files.write(f.raw.resolve("wire.json"),canonical(wire,16*1024*1024));Files.write(f.raw.resolve("events.json"),canonical(events,8*1024*1024));
            Files.write(f.raw.resolve("checkpoint-receipts.json"),canonical(checkpointReceipts,1024*1024));f.snapshot("after-slot");V53NativeApplicationTest.save(f);
            Files.write(f.raw.resolve("timings.json"),canonical(timings,8*1024*1024));
        }
    }
    @Test void sameListenerReceivesNativeVotesApplicationAndPublication()throws Exception {
        for(int size:List.of(3,4,5))for(boolean data:List.of(false,true))try(var n=new Network(size,data)) {
            var cert=n.applyAll();var ack=n.publish(size-1);assertEquals("PUBLISH_ACK",ack.kind());
            assertEquals(data?2L:1L,n.owners.getLast().activationContext().cut.get("index"));assertEquals(data?1L:0L,n.owners.getFirst().activationContext().cut.get("index"));
            assertFalse(n.owners.getLast().futureRetentionState().pending());assertTrue(n.owners.getFirst().futureRetentionState().pending());
            Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","size",size,"kind",data?"DATA":"BARRIER","certificate",cert.digest()),4096));
        }
    }
    @Test void independentCheckpointOwnersStartTogetherUnderUnchangedRequestBounds()throws Exception {
        try(var n=new Network(4,true)) {
            n.applyAll();var both=new CountDownLatch(2);var waiting=new AtomicInteger();
            n.beforeOutgoing.set(request->{if(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                    && object(request.value().get("sender")).get("node").equals("node-4") && waiting.getAndIncrement()<2) {
                both.countDown();try{assertTrue(both.await(4,TimeUnit.SECONDS),"independent original owners must start concurrently");}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError(error);}
            }});
            assertEquals("PUBLISH_ACK",n.publish(3).kind());assertEquals(0,both.getCount());
        }
    }
    @Test void parallelCheckpointFallbackCountsOnlyActualOriginalReceipts()throws Exception {
        try(var n=new Network(4,false)) {
            n.applyAll();n.checkpointFailure.set(MembershipTransport.Reason.IO);
            assertEquals("PUBLISH_ACK",n.publish(3).kind());assertEquals(3,n.checkpointAttempts.get());
            assertEquals(Set.of("node-2","node-3"),n.checkpointReceipts.stream().map(row->
                    (String)decode(HexFormat.of().parseHex((String)row.get("ack")),"records","CHECKPOINT_ACK").value().get("voter")).collect(java.util.stream.Collectors.toSet()));
        }
    }
    @Test void parallelCheckpointProtocolFailureDoesNotFallBackOrPublish()throws Exception {
        try(var n=new Network(4,false)) {
            n.applyAll();n.checkpointFailure.set(MembershipTransport.Reason.PROTOCOL);
            assertThrows(MembershipTransport.Failure.class,()->n.publish(3));assertEquals(1,n.checkpointAttempts.get());
            assertEquals(0L,n.owners.getLast().activationContext().cut.get("index"));assertTrue(n.checkpointReceipts.isEmpty());
            assertTrue(n.events.stream().noneMatch(row->row.get("event").equals("PUBLICATION_SELECTOR_FORCED")));
        }
    }
    @Test void closeCancelsBothParallelCheckpointWaitersAndDrainsTheControl()throws Exception {
        try(var n=new Network(4,false)) {
            n.applyAll();var hold=new CountDownLatch(2);n.holdCheckpoints.set(hold);
            var call=CompletableFuture.supplyAsync(()->{try{return n.publish(3);}catch(Exception error){throw new CompletionException(error);}});
            assertTrue(hold.await(10,TimeUnit.SECONDS));n.endpoints.getLast().close();
            assertThrows(ExecutionException.class,()->call.get(20,TimeUnit.SECONDS));
            assertEquals(2,n.heldCheckpoints.size());assertTrue(n.heldCheckpoints.stream().allMatch(CompletableFuture::isCancelled));
            assertEquals(0L,n.owners.getLast().activationContext().cut.get("index"));
            assertTrue(n.events.stream().noneMatch(row->row.get("event").equals("PUBLICATION_SELECTOR_FORCED")));
        }
    }
    @Test void prematurePublishCannotAdvancePhaseAndCompletedDuplicatesDoNotReapply()throws Exception {
        try(var n=new Network(3,false)) {
            var early=n.request(2,"PUBLISH",Map.of("certificate","0".repeat(64)));var before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());
            assertThrows(Exception.class,()->n.send(2,early));assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
            var cert=n.applyAll();n.drop.set("PUBLISH_ACK");var ack=n.publish(2);assertEquals("",n.drop.get());
            var duplicate=n.request(2,"PUBLISH",Map.of("certificate",cert.digest()));n.noOutgoing.set(true);
            before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());assertEquals(ack.value().get("payload"),n.send(2,duplicate).value().get("payload"));
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
            assertThrows(Exception.class,()->n.send(2,n.request(2,"ACCEPT",Map.of("acceptance",n.accept.digest()))));
        }
    }
    @Test void nativeDeliveryRetriesLostRepliesWithIdenticalBytes()throws Exception {
        try(var n=new Network(3,false)) {
            n.drop.set("ACCEPT_ACK");var request=n.request(2,"ACCEPT",Map.of("acceptance",n.accept.digest()));
            assertEquals("ACCEPT_ACK",n.send(2,request).kind());assertEquals("",n.drop.get());
            var attempts=n.wire.stream().filter(row->Arrays.equals(request.bytes(),Base64.getDecoder().decode((String)row.get("request")))).toList();
            assertEquals(2,attempts.size());assertEquals(true,attempts.getFirst().get("withheld"));assertEquals(false,attempts.getLast().get("withheld"));
            assertEquals(1,n.events.stream().filter(row->row.get("node").equals("node-3") && row.get("event").equals("ACCEPT_PARENT_FORCED")).count());
        }
    }
    @Test void nativeDeliveryExhaustsExactlyThreeIoAttemptsAndDoesNotRetryAnInvalidAck()throws Exception {
        try(var n=new Network(3,false)) {
            var request=n.request(2,"ACCEPT",Map.of("acceptance",n.accept.digest()));n.incomingFailure.set("IO");
            assertThrows(MembershipTransport.Failure.class,()->n.send(2,request));assertEquals(3,n.failedArrivals.get());
            n.incomingFailure.set("BAD_ACK");n.failedArrivals.set(0);
            assertEquals("slot delivery exact acknowledgement",assertThrows(IllegalArgumentException.class,()->n.send(2,request)).getMessage());
            assertEquals(1,n.failedArrivals.get());assertTrue(n.owners.get(2).voting(n.resources.get(2)).record("ACCEPT").isEmpty());
        }
    }
    @Test void nativeDeliveryChecksTheFenceAgainAtTheActualSocketWrite()throws Exception {
        try(var n=new Network(3,false)) {
            var request=n.request(2,"ACCEPT",Map.of("acceptance",n.accept.digest()));
            n.beforeWrite.set(()->n.owners.getFirst().observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",n.owners.getFirst().activationIdentity().storageId().toString())));
            assertThrows(IllegalArgumentException.class,()->n.send(2,request));
            assertTrue(n.owners.get(2).voting(n.resources.get(2)).record("ACCEPT").isEmpty());
            assertTrue(n.wire.stream().noneMatch(row->MembershipWire.decode(Base64.getDecoder().decode((String)row.get("request")),FRAME).kind().equals("ACCEPT")));
        }
    }
    @Test void higherBallotAndOriginalDeadlineFenceEveryStage()throws Exception {
        try(var n=new Network(3,false)) {
            n.applyAll();var target=n.owners.get(2);target.observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",n.owners.getFirst().activationIdentity().storageId().toString()));
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(2).handle(n.owners.getFirst().activationIdentity(),n.request(2,"PUBLISH",Map.of("certificate",target.currentCertificate().orElseThrow().digest()))));
            assertEquals(0L,target.activationContext().cut.get("index"));
            n.offset.set(BUDGET);assertFalse(n.endpoints.get(1).poll());
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(1).handle(n.owners.getFirst().activationIdentity(),n.request(1,"ACCEPT",Map.of("acceptance",n.accept.digest()))));
        }
    }
    @Test void higherObservationDoesNotWaitOnTheForceHeldWriter()throws Exception {
        try(var n=new Network(3,false)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            n.hooks.get(2).set(event->{if(event.equals("ACCEPT_CANDIDATE_FORCED")){entered.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new IOException("test latch timeout");}catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}}});
            var request=n.request(2,"ACCEPT",Map.of("acceptance",n.accept.digest()));
            var first=n.transports.getFirst().exchange(n.owners.get(2).activationIdentity(),request,"ACCEPT_ACK",System.nanoTime()+BUDGET);
            assertTrue(entered.await(10,TimeUnit.SECONDS));
            try {
                // A higher observation cannot wait on the force-held journal lock.
                n.owners.get(2).observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",n.owners.getFirst().activationIdentity().storageId().toString()));
            }finally{release.countDown();}
            assertThrows(ExecutionException.class,()->first.get(20,TimeUnit.SECONDS));
            assertArrayEquals(Files.readAllBytes(n.f.raw.resolve("before-voting/node-3/selector.gsr")),Files.readAllBytes(n.f.request.targets().get(2).replicaDirectory().resolve("selector.gsr")));
        }
    }
    @Test void overlappingDifferentControlRejectsWhileExactDuplicateSharesTheWork()throws Exception {
        try(var n=new Network(3,false)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var once=new AtomicBoolean();
            n.beforeOutgoing.set(request->{if(once.compareAndSet(false,true)){entered.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("test latch timeout");}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError(error);}}});
            var request=n.request(2,"ACCEPT",Map.of("acceptance",n.accept.digest()));
            var first=CompletableFuture.supplyAsync(()->{try{return n.endpoints.get(2).handle(n.owners.getFirst().activationIdentity(),request);}catch(IOException error){throw new CompletionException(error);}});
            assertTrue(entered.await(10,TimeUnit.SECONDS));
            try {
                var failure=assertThrows(MembershipTransport.Failure.class,()->n.endpoints.get(2).handle(n.owners.getFirst().activationIdentity(),n.request(2,"PUBLISH",Map.of("certificate","0".repeat(64)))));
                assertEquals(MembershipTransport.Reason.CAPACITY,failure.reason);
            }finally{release.countDown();}
            var duplicate=n.endpoints.get(2).handle(n.owners.getFirst().activationIdentity(),request);
            assertArrayEquals(first.get(20,TimeUnit.SECONDS).bytes(),duplicate.bytes());
            assertEquals(1,n.events.stream().filter(row->row.get("node").equals("node-3") && row.get("event").equals("ACCEPT_PARENT_FORCED")).count());
        }
    }
    @Test void sharedTransferStillChecksActualOwnerBytesBeforeServingAnOffer()throws Exception {
        try(var n=new Network(3,false)) {
            var target=n.owners.get(2);var trace=UUID.randomUUID();
            var offer=MembershipActivation.frame("CHUNK",n.owners.getFirst().activationContext(),n.owners.getFirst().activationIdentity(),target.activationIdentity(),n.f.ballot,trace,1,
                    Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest",n.accept.digest(),"bytes",""));
            Path file=n.f.request.targets().get(2).replicaDirectory().resolve("pending.accept");byte[] original=Files.readAllBytes(file);
            try {
                Files.write(file,new byte[]{1});
                assertThrows(Exception.class,()->n.endpoints.get(2).handle(n.owners.getFirst().activationIdentity(),offer));
            }finally{Files.write(file,original);}
            assertTrue(n.wire.isEmpty());
        }
    }
    @Test void checkpointTransferSessionSurvivesPublicationWithoutRegistryReplacement()throws Exception {
        try(var n=new Network(3,false)) {
            n.applyAll();var target=n.owners.get(2);var actual=target.voting(n.resources.get(2)).application().orElseThrow().endorsement().acknowledgement();
            var context=n.owners.getFirst().activationContext();var trace=UUID.randomUUID();var id=UUID.randomUUID().toString();
            var offer=MembershipActivation.frame("CHUNK",context,n.owners.getFirst().activationIdentity(),target.activationIdentity(),n.f.ballot,trace,1,
                    Map.of("id",id,"action","REQUEST","offset",0L,"digest",actual.digest(),"bytes",""));
            var reply=n.transports.getFirst().exchange(target.activationIdentity(),offer,"SOURCE_OFFER",System.nanoTime()+BUDGET).get(20,TimeUnit.SECONDS);
            assertEquals(actual.digest(),object(reply.value().get("payload")).get("digest"));n.publish(2);
            var chunk=MembershipActivation.frame("CHUNK",context,n.owners.getFirst().activationIdentity(),target.activationIdentity(),n.f.ballot,trace,2,
                    Map.of("id",id,"action","REQUEST","offset",0L,"digest",actual.digest(),"bytes",""));
            var bytes=n.transports.getFirst().exchange(target.activationIdentity(),chunk,"CHUNK",System.nanoTime()+BUDGET).get(20,TimeUnit.SECONDS);
            assertArrayEquals(actual.bytes(),Base64.getDecoder().decode((String)object(bytes.value().get("payload")).get("bytes")));
            var commit=MembershipActivation.frame("TRANSFER_COMMIT",context,n.owners.getFirst().activationIdentity(),target.activationIdentity(),n.f.ballot,trace,3,Map.of("id",id,"digest",actual.digest()));
            var complete=n.transports.getFirst().exchange(target.activationIdentity(),commit,"TRANSFER_COMMIT",System.nanoTime()+BUDGET).get(20,TimeUnit.SECONDS);
            assertEquals(commit.value().get("payload"),complete.value().get("payload"));
            assertThrows(Exception.class,()->n.transports.getFirst().exchange(target.activationIdentity(),offer,"SOURCE_OFFER",System.nanoTime()+BUDGET).get(20,TimeUnit.SECONDS));
            assertThrows(Exception.class,()->n.transports.getFirst().exchange(target.activationIdentity(),commit,"TRANSFER_COMMIT",System.nanoTime()+BUDGET).get(20,TimeUnit.SECONDS));
        }
    }
}
