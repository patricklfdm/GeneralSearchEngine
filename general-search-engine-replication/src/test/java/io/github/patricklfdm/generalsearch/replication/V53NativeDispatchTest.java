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

/** The receiver owns activation-to-slot handoff. Outgoing orchestration is explicit. */
class V53NativeDispatchTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(180);
    @FunctionalInterface interface Preparation {void prepare(V53BootstrapPublicationTest.Fixture fixture)throws Exception;}
    final class Network implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture f;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> resources=new ArrayList<>();
        final List<MembershipActivationEndpoint> endpoints=new ArrayList<>();
        final List<MembershipTransport> transports=new ArrayList<>();
        final List<AtomicReference<MembershipTransport>> links=new ArrayList<>();
        V53PublicationResourceCapture publicationResources;
        private V53ProcessTrace processTrace;
        volatile V53RestartLifecycleCapture restartLifecycleCapture;
        final List<Map<String,Object>> wire=Collections.synchronizedList(new ArrayList<>()),events=Collections.synchronizedList(new ArrayList<>() {
            @Override public boolean add(Map<String,Object> event) {
                if(processTrace!=null)processTrace.add(event);
                if(restartLifecycleCapture!=null)restartLifecycleCapture.event(size(),event);
                return super.add(event);
            }
        });
        void recordProcesses(Path path)throws IOException {
            synchronized(events) {
                if(processTrace!=null)throw new IllegalStateException("process trace already bound");
                var recorder=new V53ProcessTrace(path,"parent",true);
                for(var event:events)recorder.add(event);
                processTrace=recorder;
            }
        }
        final List<Map<String,Object>> failures=Collections.synchronizedList(new ArrayList<>());
        final boolean diagnose=Boolean.getBoolean("v53.transport.diagnostics");
        final List<Map<String,Object>> diagnostics=Collections.synchronizedList(new ArrayList<>());
        void diagnostic(String node,String event,Decoded request,Throwable error) {
            if(!diagnose)return;
            var row=new TreeMap<String,Object>();row.put("node",node);row.put("event",event);row.put("nanoTime",System.nanoTime());
            row.put("request",request.digest());row.put("kind",request.kind());
            var counts=new ArrayList<Map<String,Object>>();
            for(int i=0;i<resources.size();i++){var use=resources.get(i).usage();counts.add(Map.of("node","node-"+(i+1),"control",use.counts().getOrDefault(MembershipResources.Unit.CONTROL,0),"queued",use.queued()));}
            row.put("resources",counts);
            if(error!=null){var out=new StringWriter();error.printStackTrace(new PrintWriter(out));row.put("failure",out.toString());}
            diagnostics.add(row);
        }
        final AtomicLong offset=new AtomicLong();
        final AtomicReference<String> drop=new AtomicReference<>("");
        final AtomicReference<java.util.function.BiFunction<Decoded,Decoded,Decoded>> response=new AtomicReference<>((request,reply)->reply);
        final AtomicReference<java.util.function.Consumer<Decoded>> beforeSend=new AtomicReference<>(request->{});
        volatile boolean observeRequests;
        volatile V53GrantCapture grantCapture;
        volatile V53SourceRetirementCapture retirementCapture;
        volatile V53RemoveRetirementCapture removeRetirementCapture;
        final AtomicReference<MembershipBallotAllocator.Cut> hook=new AtomicReference<>(event->{});
        final AtomicBoolean holdNextQuery=new AtomicBoolean();
        final CountDownLatch queryEntered=new CountDownLatch(1);
        final CompletableFuture<Decoded> heldQuery=new CompletableFuture<>();
        MembershipActivationDriver driver;
        final ReplicationBounds bounds;
        Decoded selected;
        Map<String,Object> ballot;
        List<Integer> voters;
        Network()throws Exception {this(3);}
        Network(int size)throws Exception {this(size,ReplicationBounds.defaults());}
        Network(int size,ReplicationBounds bounds)throws Exception {this(size,bounds,f->{});}
        Network(int size,ReplicationBounds bounds,Preparation preparation)throws Exception {
            this(size,bounds,BUDGET,preparation);
        }
        Network(int size,ReplicationBounds bounds,long endpointBudget,Preparation preparation)throws Exception {
            this(size,bounds,endpointBudget,preparation,false);
        }
        Network(int size,ReplicationBounds bounds,long endpointBudget,Preparation preparation,boolean liveDirectory)throws Exception {
            this.bounds=bounds;
            Path raw=Files.createDirectories(Path.of("target/v53-native-dispatch/run-"+UUID.randomUUID()));
            System.out.println("v53NativeDispatchEvidence="+raw.toAbsolutePath());
            f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve(UUID.randomUUID().toString())),size,false));
            f.ownedHistory=true;f.nativeApplication=true;
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
            preparation.prepare(f);
            openActors(endpointBudget,liveDirectory);
        }
        Network(V53BootstrapPublicationTest.Fixture retained,ReplicationBounds bounds,long endpointBudget)throws Exception {
            this.bounds=bounds;f=retained;openActors(endpointBudget,false);
        }
        private void openActors(long endpointBudget,boolean liveDirectory)throws Exception {
            if(Boolean.getBoolean("v53.publication.resources"))publicationResources=new V53PublicationResourceCapture(f.raw);
            f.snapshot("before-network");
            for(var target:f.request.targets()) {
                var budget=new MembershipResources(512*MembershipResources.MIB);resources.add(budget);links.add(new AtomicReference<>());
                owners.add(MembershipGrantJournal.openRetainingFuturePeers(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),budget,
                        MembershipGrantJournal.MAXIMUM,event->{
                            int eventIndex;synchronized(events){eventIndex=events.size();events.add(Map.of("node",target.identity().nodeId().value(),"event",event));}
                            var remove=removeRetirementCapture;if(remove!=null)remove.at(target.identity().nodeId().value(),target.replicaDirectory(),event,eventIndex);
                            var capture=grantCapture;if(capture!=null)capture.at(target.identity().nodeId().value(),"network-owner",target.replicaDirectory(),event);
                            var retirement=retirementCapture;if(retirement!=null)retirement.at(target.identity().nodeId().value(),"network-owner",target.replicaDirectory(),event);
                            if(publicationResources!=null)publicationResources.at(target.identity().nodeId().value(),"",target.replicaDirectory(),budget,event,eventIndex);
                            if(target.identity().nodeId().value().equals("node-2"))hook.get().at(event);}));
            }
            for(int i=0;i<f.request.targets().size();i++) {
                int index=i;var owner=owners.get(i);
                var endpoint=new MembershipActivationEndpoint(owner,resources.get(i),bounds,
                        (peer,request,kind,deadline)->{
                            if(index==1 && request.kind().equals("STATUS_PROBE") && holdNextQuery.compareAndSet(true,false)) {
                                queryEntered.countDown();return heldQuery;
                            }
                            var pending=links.get(index).get().exchange(peer,request,kind,deadline);
                            if(diagnose)pending.whenComplete((reply,error)->{
                                if(error!=null)diagnostic(owner.activationIdentity().nodeId().value(),"EXCHANGE_FAILED",request,error);
                            });
                            return pending;
                        },List.of(),List.of(),
                        temp.resolve("incoming-"+UUID.randomUUID()),()->System.nanoTime()+offset.get(),endpointBudget,
                        builder().configuration(),f.request.targets().get(i).materialization());endpoints.add(endpoint);
                MembershipTransport.Handler handler=(sender,request)->{
                            try{return response.get().apply(request,endpoint.handle(sender,request));}catch(IOException|RuntimeException error){
                                diagnostic(owner.activationIdentity().nodeId().value(),"HANDLER_FAILED",request,error);
                                failures.add(Map.of("node",owner.activationIdentity().nodeId().value(),"kind",request.kind(),"request",request.digest(),"failure",error.toString()));throw error;}
                        };
                MembershipTransport.Events transportEvents=V53JoiningTrace.withFailures(owner.activationIdentity().nodeId().value(),null,events,
                        ()->observeRequests,(event,request,response)->{
                            if(restartLifecycleCapture!=null)restartLifecycleCapture.incoming(owner.activationIdentity().nodeId().value(),event,request);
                            diagnostic(owner.activationIdentity().nodeId().value(),event,request,null);
                            if(event.equals("BEFORE_REQUEST_WRITE"))beforeSend.get().accept(request);
                            if(observeRequests)V53JoiningTrace.requestObservation(events,owner.activationIdentity().nodeId().value(),event,request);
                            if(event.equals("BEFORE_REQUEST_WRITE") && request.kind().equals("PUBLISH"))events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","PUBLICATION_SEND_BOUNDARY","request",request.digest()));
                            if(event.equals("AFTER_RESPONSE_READ"))events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest()));
                            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                String expected=drop.get();boolean lost=expected.equals(response.kind()) && drop.compareAndSet(expected,"");
                                var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",lost);wire.add(row);
                                events.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest()));
                                if(lost)throw new IOException("lost native dispatch reply");
                            }
                        });
                var transport=liveDirectory?new MembershipTransport(owner,bounds,resources.get(i),handler,transportEvents):
                        new MembershipTransport(owner.activationCapsule(),owner.activationIdentity(),bounds,resources.get(i),handler,transportEvents);
                transports.add(transport);links.get(i).set(transport);
            }
        }
        void activate()throws Exception {
            driver=new MembershipActivationDriver(owners.getFirst(),endpoints.getFirst(),resources.getFirst(),bounds,transports.getFirst()::exchange,
                    List.of(),List.of(),temp.resolve("outgoing-"+UUID.randomUUID()),System::nanoTime,BUDGET,2);
            selected=driver.run();ballot=object(selected.value().get("ballot"));assertEquals(1,driver.campaigns());
            voters=list(selected.value().get("sources")).stream().map(v->Integer.parseInt(((String)object(v).get("voter")).substring(5))-1).sorted().toList();
            assertEquals(java.util.stream.IntStream.range(0,f.request.targets().size()/2+1).boxed().toList(),voters);f.snapshot("installed");Files.write(f.raw.resolve("selected.gsr"),selected.bytes());
            System.out.println("v53NativeDispatchStage=installed");
        }
        Decoded request(int index,String kind,Map<String,Object> payload)throws Exception {
            return MembershipActivation.frame(kind,owners.getFirst().activationContext(),owners.getFirst().activationIdentity(),owners.get(index).activationIdentity(),
                    ballot,UUID.randomUUID(),1,payload);
        }
        Decoded send(int index,Decoded request)throws Exception {
            return MembershipSlotDelivery.deliver(owners.getFirst(),owners.get(index).activationIdentity(),request,resources.getFirst(),transports.getFirst(),
                    System::nanoTime,System.nanoTime(),BUDGET);
        }
        MembershipContext.Owned observation(int index,Decoded record)throws Exception {
            var own=owners.getFirst();if(index==0)return own.voting(resources.getFirst()).observation(record);
            try(var pull=new MembershipSourcePull(own.activationCapsule(),own.activationIdentity(),owners.get(index).activationIdentity(),ballot,UUID.randomUUID(),resources.getFirst(),
                    ReplicationBounds.defaults(),transports.getFirst()::exchange,()->own.voting(resources.getFirst()).check(),System::nanoTime,System.nanoTime(),BUDGET)) {
                return pull.fetchVoteObservation(record);
            }
        }
        Decoded begin(boolean data)throws Exception {
            events.add(Map.of("node","node-1","event","SLOT_BEGIN","index",data?2:1));
            endpoints.getFirst().maintainInstalled();var own=owners.getFirst();var context=own.activationContext();byte[] payload=new byte[0];
            if(data)try(var encoder=new ReplicaApplication<>(builder().configuration(),f.request.targets().getFirst().materialization(),ReplicationBounds.defaults())) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(100,"next-slot"))));
            }
            var entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),"index",number(context.cut.get("index"))+1,
                    "previous",context.cut.get("entry"),"origin",ballot,"kind",data?"DATA":"BARRIER","payload",hash(payload))),"records","ENTRY");
            own.acceptCurrent(entry,payload);return own.voting(resources.getFirst()).record("ACCEPT").orElseThrow();
        }
        Decoded apply(Decoded accept)throws Exception {
            var own=owners.getFirst();for(int i:voters)if(i!=0)send(i,request(i,"ACCEPT",Map.of("acceptance",accept.digest())));
            var accepts=new HashSet<MembershipContext.Owned>();for(int i:voters)accepts.add(observation(i,accept));
            var values=new TreeMap<>(accept.value());values.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",accept,accepts));
            var proof=decode(encode("records","PROOF",values),"records","PROOF");own.proveCurrent(proof,accepts);
            for(int i:voters)if(i!=0)send(i,request(i,"PROOF",Map.of("proof",proof.digest())));
            var proofs=new HashSet<MembershipContext.Owned>();for(int i:voters)proofs.add(observation(i,proof));
            values=new TreeMap<>(proof.value());values.put("proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",values),"records","CERTIFICATE");accepts.addAll(proofs);own.certifyCurrent(certificate,accepts);
            own.applyCurrent(builder().configuration(),f.request.targets().getFirst().materialization());
            for(int i:voters)if(i!=0)send(i,request(i,"APPLY",Map.of("certificate",certificate.digest(),"selection",selected.digest())));
            f.snapshot("applied-"+certificate.value().get("index"));return certificate;
        }
        void publish(Decoded certificate)throws Exception {
            var own=owners.getFirst();var applied=own.voting(resources.getFirst()).application().orElseThrow();
            // Match the slot driver: record every target while all governing
            // voters still have the old view. Publishing one target first can
            // destroy the recording quorum for the next target at INTENT.
            var recordings=new ArrayList<MembershipFutureRetentionQuorum>();
            var ready=new ArrayList<MembershipFutureRetentionQuorum.Recorded>();
            try {
                for(int voter:voters)if(voter!=0) {
                    var remote=new MembershipFutureRetentionQuorum(own,owners.get(voter).activationIdentity(),ballot,own.pendingPublication(applied),resources.getFirst(),
                            transports.getFirst()::exchange,System::nanoTime,System.nanoTime(),BUDGET);
                    recordings.add(remote);var recorded=remote.record();ready.add(recorded);
                    events.add(Map.of("node","node-1","event","FUTURE_QUORUM_COMPLETE","index",certificate.value().get("index"),"voters",recorded.voters().stream().sorted().toList()));
                }
                for(var recorded:ready)assertEquals("PUBLISH_ACK",recorded.dispatch(transports.getFirst()).kind());
            }finally{for(var recording:recordings)recording.close();}
            assertEquals("PUBLISH_ACK",endpoints.getFirst().handle(own.activationIdentity(),request(0,"PUBLISH",Map.of("certificate",certificate.digest()))).kind());
            for(int i:voters)assertEquals(certificate.value().get("index"),owners.get(i).activationContext().cut.get("index"));
            f.snapshot("published-"+certificate.value().get("index"));
            System.out.println("v53NativeDispatchStage=published-"+certificate.value().get("index"));
        }
        @Override public void close()throws Exception {
            hook.set(event->{});if(driver!=null)driver.close();for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();
            for(var owner:owners)owner.close();for(var budget:resources)assertEquals(0,budget.usage().leases());
            Files.write(f.raw.resolve("wire.json"),V53EvidenceArray.encode(wire,V53EvidenceArray.WIRE_BYTES));Files.write(f.raw.resolve("events.json"),V53EvidenceArray.encode(events,V53EvidenceArray.EVENT_BYTES));
            Files.write(f.raw.resolve("failures.json"),V53EvidenceArray.encode(failures,1024*1024));
            f.snapshot("after-close");V53NativeApplicationTest.save(f);
            if(publicationResources!=null)publicationResources.save();
            if(diagnose)try(var writer=Files.newBufferedWriter(Files.createDirectories(Path.of("target/v53-native-dispatch-diagnostics")).resolve(f.raw.getFileName()+".jsonl"))) {
                for(var row:diagnostics){writer.write(new String(canonical(row,65536),java.nio.charset.StandardCharsets.UTF_8));writer.newLine();}
            }
        }
    }
    @Test void nativeActivationReceivesAndPublishesTwoStableSlotsOnOneListener()throws Exception {
        try(var n=new Network()) {
            n.activate();n.publish(n.apply(n.begin(false)));n.publish(n.apply(n.begin(true)));
            assertEquals(0L,n.owners.get(2).activationContext().cut.get("index"));
            Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","slots",2,"network",true,"autonomous",false),4096));
        }
    }
    @Test void lostAcceptReplyDoesNotRecreateSlotOrVote()throws Exception {
        try(var n=new Network()) {
            n.activate();var accepted=n.begin(false);n.drop.set("ACCEPT_ACK");var request=n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest()));
            assertEquals("ACCEPT_ACK",n.send(1,request).kind());assertEquals("",n.drop.get());
            assertEquals(1,n.events.stream().filter(v->v.get("node").equals("node-2") && v.get("event").equals("ACCEPT_PARENT_FORCED")).count());
        }
    }
    @Test void expiredGrantCannotBeRevivedByFirstSlotControl()throws Exception {
        try(var n=new Network()) {
            n.activate();var accepted=n.begin(false);var request=n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest()));
            var before=V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory());n.offset.set(BUDGET);
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(1).handle(n.owners.getFirst().activationIdentity(),request));
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
        }
    }
    @Test void endedLocalCampaignCannotOpenANewSlot()throws Exception {
        try(var n=new Network()) {
            n.activate();var accepted=n.begin(false);n.endpoints.get(1).abandon(n.ballot);
            var request=n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest()));
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(1).handle(n.owners.getFirst().activationIdentity(),request));
            assertTrue(n.owners.get(1).voting(n.resources.get(1)).record("ACCEPT").isEmpty());
        }
    }
    @Test void aPoisonedActivationTraceStaysFailedAfterSlotCreation()throws Exception {
        try(var n=new Network()) {
            n.activate();var sender=n.owners.getFirst().activationIdentity();
            var first=n.wire.stream().map(row->MembershipWire.decode(Base64.getDecoder().decode((String)row.get("request")),FRAME))
                    .filter(r->r.kind().equals("CHUNK") && number(r.value().get("sequence"))==1
                            && object(r.value().get("sender")).get("node").equals("node-1")
                            && object(r.value().get("recipient")).get("node").equals("node-2")).findFirst().orElseThrow();
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(1).handle(sender,first));
            var accept=n.begin(false);assertEquals("ACCEPT_ACK",n.send(1,n.request(1,"ACCEPT",Map.of("acceptance",accept.digest()))).kind());
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(1).handle(sender,first));
        }
    }
    @Test void closeCancelsNativeMaintenanceBeforeAnAcceptCanBeForced()throws Exception {
        try(var n=new Network()) {
            n.activate();var accepted=n.begin(false);n.holdNextQuery.set(true);
            var call=n.transports.getFirst().exchange(n.owners.get(1).activationIdentity(),n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest())),"ACCEPT_ACK",System.nanoTime()+BUDGET);
            assertTrue(n.queryEntered.await(10,TimeUnit.SECONDS));n.endpoints.get(1).close();
            assertTrue(n.heldQuery.isCancelled());assertThrows(ExecutionException.class,()->call.get(10,TimeUnit.SECONDS));
            assertTrue(n.owners.get(1).voting(n.resources.get(1)).record("ACCEPT").isEmpty());
        }
    }
    @Test void higherPrepareFencesAndCancelsNativeMaintenance()throws Exception {
        try(var n=new Network()) {
            n.activate();var accepted=n.begin(false);n.holdNextQuery.set(true);
            var call=n.transports.getFirst().exchange(n.owners.get(1).activationIdentity(),n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest())),"ACCEPT_ACK",System.nanoTime()+BUDGET);
            assertTrue(n.queryEntered.await(10,TimeUnit.SECONDS));
            var values=new TreeMap<>(n.request(1,"PREPARE",Map.of("promise","0".repeat(64))).value());var higher=new TreeMap<>(n.ballot);
            higher.put("counter",number(higher.get("counter"))+1);values.put("ballot",higher);var request=decode(encode("wire","PREPARE",values),"wire","PREPARE");
            try{assertEquals("REJECT",n.endpoints.get(1).handle(n.owners.getFirst().activationIdentity(),request).kind());}
            catch(IOException|IllegalArgumentException expected) { /* No original higher promise is available. */ }
            assertTrue(n.heldQuery.isCancelled());assertThrows(ExecutionException.class,()->call.get(10,TimeUnit.SECONDS));
            assertTrue(n.events.stream().noneMatch(v->v.get("node").equals("node-2") && v.get("event").equals("ACCEPT_PARENT_FORCED")));
            assertThrows(IllegalArgumentException.class,()->n.owners.get(1).voting(n.resources.get(1)));
        }
    }
}
