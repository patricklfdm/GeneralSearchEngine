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

class V53SelectedPullTest {
    @TempDir Path temp;
    static Map<String,Object> wire(Decoded request,Decoded response) {return Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(response.bytes()));}
    static MembershipCurrentGeneration.Verifier verify(Set<Owned> observations){return (root,packet,images)->MembershipCapsule.verify(root,packet,images,observations);}
    @Test void actualTcpSelectedReceiversFetchEveryOriginalBeforeInstallation()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-selected-pull/run-"+UUID.randomUUID()));
        System.out.println("v53SelectedPullEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path profile=Files.createDirectory(evidence.resolve("stable-"+size));Path raw=Files.createDirectory(profile.resolve("selection"));Path installation=Files.createDirectory(profile.resolve("activation"));Path receivedRaw=Files.createDirectory(profile.resolve("install-pulls"));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;var budgets=new ArrayList<MembershipResources>();var owners=new ArrayList<MembershipGrantJournal>();
                var services=new ArrayList<AtomicReference<MembershipTransferService>>();var transports=new ArrayList<AtomicReference<MembershipTransport>>();
                var events=new TreeMap<String,List<String>>();var pulls=new ArrayList<MembershipSourcePull>();var imageBytes=new TreeMap<String,byte[]>();var controlWire=new ArrayList<Map<String,Object>>();long start=System.nanoTime();
                var queue=resources();var bound=V53TransferServiceTest.bound(2);
                try {
                    for(var target:f.request.targets()) {
                        var r=resources();budgets.add(r);var steps=Collections.synchronizedList(new ArrayList<String>());events.put(target.identity().nodeId().value(),steps);
                        owners.add(MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),r,verify(Set.of()),MembershipGrantJournal.MAXIMUM,steps::add));
                        services.add(new AtomicReference<>());transports.add(new AtomicReference<>());
                    }
                    var leader=group.identities.getFirst();
                    try(var campaign=new MembershipActivation(owners.getFirst(),queue,System::nanoTime,BUDGET)) {
                        services.getFirst().set(new MembershipTransferService(owners.getFirst(),campaign.ballot(),budgets.getFirst(),bound,()->owners.getFirst().checkActivation(campaign.ownSource().basis,null,false),System::nanoTime,start,BUDGET));
                        for(int n=0;n<size;n++) {
                            int member=n;var local=group.identities.get(n);
                            var transport=group.start(n,(sender,request)->{
                                if(request.kind().equals("PREPARE")) {
                                    Path peerRaw=raw.resolve(local.nodeId().value());var rows=new ArrayList<Map<String,Object>>();
                                    try(var pull=new MembershipSourcePull(group.capsule,local,sender,object(request.value().get("ballot")),UUID.randomUUID(),budgets.get(member),bound,
                                        (peer,frame,kind,deadline)->transports.get(member).get().exchange(peer,frame,kind,deadline).thenApply(reply->{rows.add(wire(frame,reply));return reply;}),()->{},System::nanoTime,start,BUDGET)) {
                                        var original=pull.fetchRecord((String)object(request.value().get("payload")).get("promise"),"PROMISE",v->V53RecordExchangeTest.promise(v,group.capsule.context,campaign.ballot()));
                                        events.get(local.nodeId().value()).add("PROPOSER_RECORD_VALIDATED");
                                        var reply=MembershipActivation.prepare(owners.get(member),sender,request,original).response();
                                        services.get(member).set(new MembershipTransferService(owners.get(member),campaign.ballot(),budgets.get(member),bound,()->owners.get(member).checkActivation(owners.get(member).originalBasis().orElseThrow(),null,false),System::nanoTime,start,BUDGET));
                                        Files.write(peerRaw.resolve("proposer-wire.json"),canonical(rows,1024*1024));events.get(local.nodeId().value()).add("PROMISE_REPLIED");return reply;
                                    }
                                }
                                if(request.kind().equals("SELECTED")) {
                                    var rows=new ArrayList<Map<String,Object>>();Path retained=Files.createDirectory(receivedRaw.resolve(local.nodeId().value()));Path scratch=temp.resolve("install-"+size+"-"+member);
                                    try(var incoming=new MembershipSelectedPull(owners.get(member),sender,request,budgets.get(member),bound,
                                        (source,frame,kind,deadline)->transports.get(member).get().exchange(source,frame,kind,deadline).thenApply(reply->{rows.add(wire(frame,reply));return reply;}),
                                        verify(Set.of()),List.of(),List.of(),scratch,()->{},System::nanoTime,start,BUDGET)) {
                                        V53JournalApplicationTest.copy(scratch,retained.resolve("received"));var reply=incoming.install();
                                        Files.write(retained.resolve("wire.json"),canonical(rows,16*1024*1024));events.get(local.nodeId().value()).add("INSTALL_REPLIED");return reply;
                                    }
                                }
                                return Objects.requireNonNull(services.get(member).get()).handle(sender,request);
                            },MembershipTransport.Events.NONE,bound,budgets.get(n));transports.get(n).set(transport);
                        }
                        for(int n=1;n<=size/2;n++) {
                            var peer=group.identities.get(n);Path peerRaw=Files.createDirectory(raw.resolve(peer.nodeId().value()));
                            var request=campaign.prepare(peer);var reply=transports.getFirst().get().exchange(peer,request,"PROMISE",start+BUDGET).get(30,TimeUnit.SECONDS);
                            controlWire.add(wire(request,reply));Files.write(peerRaw.resolve("prepare.json"),canonical(wire(request,reply),65536));var rows=new ArrayList<Map<String,Object>>();
                            var pull=new MembershipSourcePull(group.capsule,leader,peer,campaign.ballot(),UUID.randomUUID(),queue,bound,
                                (source,frame,kind,deadline)->transports.getFirst().get().exchange(source,frame,kind,deadline).thenApply(response->{rows.add(wire(frame,response));return response;}),()->owners.getFirst().checkActivation(campaign.ownSource().basis,null,false),System::nanoTime,start,BUDGET);pulls.add(pull);
                            var received=pull.fetch(temp.resolve("promised-"+size+"-"+n),(String)object(reply.value().get("payload")).get("basis"));
                            V53JournalApplicationTest.copy(temp.resolve("promised-"+size+"-"+n),peerRaw.resolve("received"));
                            imageBytes.putAll(received.images());campaign.promised(peer,reply,received,verify(Set.of()),List.of());events.get(leader.nodeId().value()).add("SOURCE_VERIFIED_"+peer.nodeId().value());
                            Files.write(peerRaw.resolve("source-wire.json"),canonical(rows,16*1024*1024));
                        }
                        assertEquals(MembershipActivation.State.INSTALLING,campaign.state());assertEquals(size/2+1,campaign.sources().size());
                        assertThrows(IllegalArgumentException.class,campaign::votingSelection);
                        Files.write(raw.resolve("selected.gsr"),owners.getFirst().originalSelection().orElseThrow().bytes());
                        f.snapshot("selected");Files.write(raw.resolve("events.json"),canonical(events.entrySet().stream().map(row->Map.of("node",row.getKey(),"events",row.getValue())).toList(),1024*1024));
                        campaign.installLocal(List.of(),imageBytes);
                        for(int n=1;n<=size/2;n++) {
                            var peer=group.identities.get(n);var request=campaign.installation(peer);
                            var reply=transports.getFirst().get().exchange(peer,request,"INSTALL_ACK",start+BUDGET).get(30,TimeUnit.SECONDS);
                            controlWire.add(wire(request,reply));campaign.installed(peer,reply);
                        }
                        assertEquals(MembershipActivation.State.INSTALLED,campaign.state());assertEquals(owners.getFirst().originalSelection().orElseThrow().digest(),campaign.votingSelection().digest());
                        f.snapshot("installed");Files.move(raw.resolve("installed"),installation.resolve("installed"));
                        V53JournalApplicationTest.copy(raw.resolve("initial"),installation.resolve("initial"));
                        for(String file:List.of("original-plan.gsbp","original-application.image","selected.gsr"))Files.copy(raw.resolve(file),installation.resolve(file));
                        Files.write(installation.resolve("wire.json"),canonical(controlWire,1024*1024));
                        Files.write(installation.resolve("events.json"),canonical(events.entrySet().stream().map(row->Map.of("node",row.getKey(),"events",row.getValue())).toList(),1024*1024));
                        cases.add(Map.of("size",size,"selected",campaign.sources().size(),"installed",campaign.sources().size(),"ready",false));
                    }
                }finally {
                    for(var pull:pulls)pull.close();for(var ref:services)if(ref.get()!=null)ref.get().close();
                    for(var transport:group.transports)transport.close();for(var owner:owners)owner.close();
                    for(var r:budgets)assertEquals(0,r.usage().leases());assertEquals(0,queue.usage().leases());
                }
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-selected-pull-v1","status","PASS","cases",cases,"publicRuntime",false,"network",true,"scope","original-network-selection-through-all-selected-installations"),65536));
    }
    final class Local implements AutoCloseable {
        final V53PromisedSourceTest.Local base;
        final MembershipTransferService service;
        final Decoded request;
        final List<Map<String,Object>> wire=new ArrayList<>();
        Local(String mode)throws Exception {
            var helper=new V53PromisedSourceTest();helper.temp=temp;base=helper.new Local(mode);base.offer(verify(base.f.observations));
            service=new MembershipTransferService(base.leader,base.campaign.ballot(),base.leaderResources,V53TransferServiceTest.bound(2),()->{},base.clock::get,0,BUDGET);
            request=base.campaign.installation(base.identity());
        }
        CompletableFuture<Decoded> exchange(MembershipIdentity peer,Decoded request,String kind,long deadline) {
            assertEquals(base.f.request.targets().getFirst().identity(),peer);assertEquals(BUDGET,deadline);
            try {var reply=service.handle(base.identity(),request);wire.add(V53PromisedSourceTest.wire(request,reply));return CompletableFuture.completedFuture(reply);}
            catch(Exception error){return CompletableFuture.failedFuture(error);}
        }
        MembershipSelectedPull receive(Path scratch,MembershipSourcePull.Link link,MembershipCurrentGeneration.Verifier verifier,MembershipSourcePull.Guard guard)throws Exception {
            return new MembershipSelectedPull(base.peer,base.f.request.targets().getFirst().identity(),request,base.peerResources,V53TransferServiceTest.bound(2),link,verifier,
                List.of(),List.of(),scratch,guard,base.clock::get,0,BUDGET);
        }
        @Override public void close()throws Exception {service.close();base.close();}
    }
    @Test void lostChunkRepliesRetryExactBytesAndRepeatedInstallationIsIdempotent()throws Exception {
        try(var l=new Local("genesis")) {
            var lost=new AtomicBoolean();var attempts=new ArrayList<byte[]>();Path scratch=temp.resolve("retry");
            try(var received=l.receive(scratch,(peer,request,kind,deadline)->{
                var future=l.exchange(peer,request,kind,deadline);
                if(kind.equals("CHUNK") && !lost.getAndSet(true)){attempts.add(request.bytes());return CompletableFuture.failedFuture(V53SourceExchangeTest.lost());}
                if(!attempts.isEmpty() && attempts.size()==1)attempts.add(request.bytes());return future;
            },verify(Set.of()),()->{})) {
                assertArrayEquals(attempts.getFirst(),attempts.get(1));var reply=received.install();
                var before=V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory());assertArrayEquals(reply.bytes(),received.install().bytes());
                assertEquals(before,V53ReplayFilesTest.files(l.base.f.request.targets().get(1).replicaDirectory()));l.base.campaign.installed(l.base.identity(),reply);
                assertEquals(MembershipActivation.State.INSTALLING,l.base.campaign.state()); // proposer still must install
            }
            assertFalse(Files.exists(scratch));
        }
    }
    @Test void invalidHistoricalEvidenceAndSubstitutedVerifierNeverSelect()throws Exception {
        for(String mode:List.of("missing","substitution"))try(var l=new Local("published")) {
            Path scratch=temp.resolve(mode);
            assertThrows(Exception.class,()->l.receive(scratch,l::exchange,mode.equals("missing")?verify(Set.of()):(r,p,i)->l.base.f.original.seed.capsule,()->{}));
            assertTrue(l.base.peer.originalSelection().isEmpty());assertFalse(Files.exists(scratch));
        }
    }
    @Test void retainedTailAndProgressedPrefixInstallTheirExactOriginal()throws Exception {
        for(String mode:List.of("tail","published"))try(var l=new Local(mode)) {
            System.out.println("v53SelectedContinuation="+mode+" usage="+l.base.peerResources.usage());
            try(var incoming=l.receive(temp.resolve(mode),l::exchange,verify(l.base.f.observations),()->{})) {
                var reply=incoming.install();var selected=l.base.peer.originalSelection().orElseThrow();
                assertEquals(selected.digest(),object(reply.value().get("payload")).get("selection"));
                l.base.peer.checkActivation(l.base.peer.originalBasis().orElseThrow(),selected,true);
                if(mode.equals("tail"))assertEquals(l.base.entry.digest(),selected.value().get("nextEntry"));
                else assertTrue(number(object(selected.value().get("cut")).get("index"))>0);
            }
        }
    }
    @Test void deadlineAfterActualForceWithholdsAckButRetainsInstalledState()throws Exception {
        try(var l=new Local("genesis")) {
            try(var incoming=l.receive(temp.resolve("after-force"),l::exchange,verify(Set.of()),()->{
                if(l.base.peer.originalSelection().isPresent())l.base.clock.set(BUDGET);
            })) {
                assertThrows(Exception.class,incoming::install);
                l.base.peer.checkActivation(l.base.peer.originalBasis().orElseThrow(),l.base.peer.originalSelection().orElseThrow(),true);
            }
        }
    }
    @Test void higherPromiseOrDeadlineAfterReceptionPreventsInstallation()throws Exception {
        for(boolean fence:List.of(false,true))try(var l=new Local("genesis")) {
            Path scratch=temp.resolve("end-"+fence);
            try(var received=l.receive(scratch,l::exchange,verify(Set.of()),()->{})) {
                if(fence){var ballot=new TreeMap<>(l.base.campaign.ballot());ballot.put("counter",99L);l.base.peer.observeCurrent(ballot);}else l.base.clock.set(BUDGET);
                assertThrows(Exception.class,received::install);assertTrue(l.base.peer.originalSelection().isEmpty());
            }
            assertFalse(Files.exists(scratch));
        }
    }
    @Test void changedReceivedPacketCannotInstallAndClosedAssemblyCannotAck()throws Exception {
        try(var l=new Local("genesis")) {
            Path scratch=temp.resolve("changed");var incoming=l.receive(scratch,l::exchange,verify(Set.of()),()->{});
            Path image;try(var paths=Files.walk(scratch)){image=paths.filter(p->p.toString().endsWith(".gscp")).findFirst().orElseThrow();}
            byte[] original=Files.readAllBytes(image);var changed=original.clone();changed[0]^=1;Files.write(image,changed);
            assertThrows(Exception.class,incoming::install);assertTrue(l.base.peer.originalSelection().isEmpty());Files.write(image,original);
            incoming.close();assertThrows(Exception.class,incoming::install);assertFalse(Files.exists(scratch));
        }
    }
    @Test void foreignScratchEntrySurvivesFailedCleanupAndCleanupCanResume()throws Exception {
        try(var l=new Local("genesis")) {
            Path scratch=temp.resolve("cleanup");var incoming=l.receive(scratch,l::exchange,verify(Set.of()),()->{});
            Path foreign=scratch.resolve("foreign");Files.writeString(foreign,"preserve");
            assertThrows(IOException.class,incoming::close);assertEquals("preserve",Files.readString(foreign));
            assertThrows(Exception.class,incoming::install);Files.delete(foreign);incoming.close();assertFalse(Files.exists(scratch));
        }
    }
    @Test void pinnedImagesUseTheirExistingReservationAndChangedBytesCannotAuthorizeAnAck()throws Exception {
        try(var l=new Local("genesis")) {
            int before=l.base.peerResources.usage().counts().get(MembershipResources.Unit.APPLICATION);Path scratch=temp.resolve("pinned");
            try(var incoming=l.receive(scratch,l::exchange,verify(Set.of()),()->{})) {
                assertEquals(before,l.base.peerResources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                try(var files=Files.walk(scratch)){assertFalse(files.anyMatch(p->p.toString().endsWith(".image")));}
                Path source=l.base.f.request.targets().get(1).replicaDirectory().resolve("sources").resolve((String)l.base.peer.originalBasis().orElseThrow().value().get("basisId"));
                Path image;try(var files=Files.list(source)){image=files.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}
                byte[] original=Files.readAllBytes(image);byte[] altered=original.clone();altered[0]^=1;Files.write(image,altered);
                try{assertThrows(Exception.class,incoming::install);assertTrue(l.base.peer.originalSelection().isEmpty());}
                finally{Files.write(image,original);}
            }
            assertFalse(Files.exists(scratch));
        }
    }
    @Test void anUnavailableSourceDoesNotSpendNewDeadlinesOrPersistSelection()throws Exception {
        try(var l=new Local("genesis")) {
            var calls=new AtomicInteger();Path scratch=temp.resolve("unavailable");
            assertThrows(Exception.class,()->l.receive(scratch,(peer,request,kind,deadline)->{
                calls.incrementAndGet();assertEquals(BUDGET,deadline);return CompletableFuture.failedFuture(V53SourceExchangeTest.lost());
            },verify(Set.of()),()->{}));
            assertEquals(3,calls.get());assertTrue(l.base.peer.originalSelection().isEmpty());assertFalse(Files.exists(scratch));
        }
    }
    @Test void foreignRequestAndIncompleteExchangeCannotAuthorizeInstallation()throws Exception {
        try(var l=new Local("genesis")) {
            var bad=V53ActivationTest.changed(l.request,"sender",MembershipBootstrapSeed.identity(l.base.f.request.targets().get(2).identity()));
            assertThrows(Exception.class,()->new MembershipSelectedPull(l.base.peer,l.base.f.request.targets().getFirst().identity(),bad,l.base.peerResources,V53TransferServiceTest.bound(2),l::exchange,verify(Set.of()),List.of(),List.of(),temp.resolve("bad"),()->{},l.base.clock::get,0,BUDGET));
            assertTrue(l.wire.isEmpty());assertFalse(Files.exists(temp.resolve("bad")));
            try(var pull=new MembershipSourcePull(l.base.campaign.ownSource().capsule,l.base.identity(),l.base.campaign.ownSource().owner,l.base.campaign.ballot(),UUID.randomUUID(),l.base.peerResources,V53TransferServiceTest.bound(2),l::exchange,()->{},l.base.clock::get,0,BUDGET)) {
                assertThrows(IllegalArgumentException.class,()->pull.verifiedOriginalSource(verify(Set.of())));
            }
            assertTrue(l.base.peer.originalSelection().isEmpty());
        }
    }
}
