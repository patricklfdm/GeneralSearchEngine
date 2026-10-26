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

class V53PromisedSourceTest {
    @TempDir Path temp;
    static Map<String,Object> wire(Decoded request,Decoded response) {return Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(response.bytes()));}
    static MembershipCurrentGeneration.Verifier verify(Set<Owned> observations){return (root,packet,images)->MembershipCapsule.verify(root,packet,images,observations);}
    @Test void actualTcpPromisesAndCompleteReceivedSourcesSelectTheOriginalQuorum()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-promised-source/run-"+UUID.randomUUID()));
        System.out.println("v53PromisedSourceEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;var budgets=new ArrayList<MembershipResources>();var owners=new ArrayList<MembershipGrantJournal>();
                var services=new ArrayList<AtomicReference<MembershipTransferService>>();var transports=new ArrayList<AtomicReference<MembershipTransport>>();
                var events=new TreeMap<String,List<String>>();var pulls=new ArrayList<MembershipSourcePull>();long start=System.nanoTime();
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
                                return Objects.requireNonNull(services.get(member).get()).handle(sender,request);
                            },MembershipTransport.Events.NONE,bound,budgets.get(n));transports.get(n).set(transport);
                        }
                        for(int n=1;n<=size/2;n++) {
                            var peer=group.identities.get(n);Path peerRaw=Files.createDirectory(raw.resolve(peer.nodeId().value()));
                            var request=campaign.prepare(peer);var reply=transports.getFirst().get().exchange(peer,request,"PROMISE",start+BUDGET).get(30,TimeUnit.SECONDS);
                            Files.write(peerRaw.resolve("prepare.json"),canonical(wire(request,reply),65536));var rows=new ArrayList<Map<String,Object>>();
                            var pull=new MembershipSourcePull(group.capsule,leader,peer,campaign.ballot(),UUID.randomUUID(),queue,bound,
                                (source,frame,kind,deadline)->transports.getFirst().get().exchange(source,frame,kind,deadline).thenApply(response->{rows.add(wire(frame,response));return response;}),()->owners.getFirst().checkActivation(campaign.ownSource().basis,null,false),System::nanoTime,start,BUDGET);pulls.add(pull);
                            var received=pull.fetch(temp.resolve("promised-"+size+"-"+n),(String)object(reply.value().get("payload")).get("basis"));
                            V53JournalApplicationTest.copy(temp.resolve("promised-"+size+"-"+n),peerRaw.resolve("received"));
                            campaign.promised(peer,reply,received,verify(Set.of()),List.of());events.get(leader.nodeId().value()).add("SOURCE_VERIFIED_"+peer.nodeId().value());
                            Files.write(peerRaw.resolve("source-wire.json"),canonical(rows,16*1024*1024));
                        }
                        assertEquals(MembershipActivation.State.INSTALLING,campaign.state());assertEquals(size/2+1,campaign.sources().size());
                        assertThrows(IllegalArgumentException.class,campaign::votingSelection);
                        Files.write(raw.resolve("selected.gsr"),owners.getFirst().originalSelection().orElseThrow().bytes());
                        cases.add(Map.of("size",size,"selected",campaign.sources().size(),"ready",false));
                    }
                }finally {
                    for(var pull:pulls)pull.close();for(var ref:services)if(ref.get()!=null)ref.get().close();
                    for(var transport:group.transports)transport.close();for(var owner:owners)owner.close();
                    for(var r:budgets)assertEquals(0,r.usage().leases());assertEquals(0,queue.usage().leases());
                }
                f.snapshot("selected");Files.write(raw.resolve("events.json"),canonical(events.entrySet().stream().map(row->Map.of("node",row.getKey(),"events",row.getValue())).toList(),1024*1024));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-promised-source-v1","status","PASS","cases",cases,"publicRuntime",false,"network",true,"scope","original-promise-through-network-selection"),65536));
    }
    final class Local implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture f;
        final MembershipResources leaderResources=resources(),peerResources=resources(),queue=resources();
        final MembershipGrantJournal leader,peer;
        final MembershipActivation campaign;
        final Decoded request,reply,entry;
        final MembershipTransferService service;
        final MembershipSourcePull pull;
        final MembershipSourceReceive received;
        final AtomicLong clock=new AtomicLong();
        Local(String mode)throws Exception {
            Path path=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));f=new V53BootstrapPublicationTest.Fixture(path,Files.createDirectory(path.resolve("raw")),3,false);
            Decoded carried=null;
            if(!mode.equals("genesis"))f.campaign(1);
            if(mode.equals("published"))f.publish(1,false);
            if(mode.equals("tail"))try(var owner=f.open(f.request.targets().get(1),"minority-tail")) {
                var c=owner.activationContext();carried=decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",1L,"previous",c.cut.get("entry"),"origin",f.ballot,"kind","BARRIER","payload",hash(new byte[0]))),"records","ENTRY");owner.acceptCurrent(carried,new byte[0]);
            }
            entry=carried;var first=f.request.targets().getFirst();var second=f.request.targets().get(1);
            leader=MembershipGrantJournal.openBootstrapped(first.replicaDirectory(),first.materialization().directory(),f.result.root(),first.identity(),leaderResources,verify(f.observations),MembershipGrantJournal.MAXIMUM,e->{});
            peer=MembershipGrantJournal.openBootstrapped(second.replicaDirectory(),second.materialization().directory(),f.result.root(),second.identity(),peerResources,verify(f.observations),MembershipGrantJournal.MAXIMUM,e->{});
            campaign=new MembershipActivation(leader,queue,clock::get,BUDGET);request=campaign.prepare(second.identity());
            reply=MembershipActivation.prepare(peer,first.identity(),request,leader.promised().orElseThrow()).response();
            service=new MembershipTransferService(peer,campaign.ballot(),peerResources,V53TransferServiceTest.bound(2),()->{},clock::get,0,BUDGET);
            pull=new MembershipSourcePull(campaign.ownSource().capsule,first.identity(),second.identity(),campaign.ballot(),UUID.randomUUID(),queue,V53TransferServiceTest.bound(2),
                (source,frame,kind,deadline)->{try{return CompletableFuture.completedFuture(service.handle(first.identity(),frame));}catch(Exception error){return CompletableFuture.failedFuture(error);}},()->{},clock::get,0,BUDGET);
            received=pull.fetch(path.resolve("scratch"),(String)object(reply.value().get("payload")).get("basis"));
        }
        MembershipIdentity identity(){return f.request.targets().get(1).identity();}
        void offer(MembershipCurrentGeneration.Verifier verifier)throws Exception {campaign.promised(identity(),reply,received,verifier,List.of());}
        @Override public void close()throws Exception {pull.close();service.close();campaign.close();peer.close();leader.close();assertEquals(0,queue.usage().leases());assertEquals(0,leaderResources.usage().leases());assertEquals(0,peerResources.usage().leases());}
    }
    @Test void noSelectionWithoutTheCorrelatedPromiseEvenWhenAllBytesExist()throws Exception {
        try(var l=new Local("genesis")) {
            for(var altered:List.of(V53ActivationTest.changed(l.reply,"trace",UUID.randomUUID().toString()),V53ActivationTest.changed(l.reply,"sequence",99L),V53ActivationTest.changed(l.reply,"sender",MembershipBootstrapSeed.identity(l.f.request.targets().get(2).identity()))))
                assertThrows(IllegalArgumentException.class,()->l.campaign.promised(l.identity(),altered,l.received,verify(Set.of()),List.of()));
            assertTrue(l.leader.originalSelection().isEmpty());l.offer(verify(Set.of()));assertEquals(MembershipActivation.State.INSTALLING,l.campaign.state());
        }
    }
    @Test void changedOriginalBasisAbandonsWithoutPersistingASelection()throws Exception {
        try(var l=new Local("genesis")) {
            var bad=V53ActivationTest.changed(l.reply,"payload",Map.of("basis","0".repeat(64)));
            assertThrows(IllegalArgumentException.class,()->l.campaign.promised(l.identity(),bad,l.received,verify(Set.of()),List.of()));
            assertTrue(l.leader.originalSelection().isEmpty());assertEquals(MembershipActivation.State.ABANDONED,l.campaign.state());
        }
    }
    @Test void validPromiseDoesNotInventHistoricalCheckpointObservations()throws Exception {
        try(var l=new Local("published")) {
            var error=assertThrows(IllegalArgumentException.class,()->l.offer(verify(Set.of())));
            assertTrue(error.getMessage().contains("owned applied end"));assertTrue(l.leader.originalSelection().isEmpty());assertEquals(MembershipActivation.State.ABANDONED,l.campaign.state());
        }
        try(var l=new Local("published")) {l.offer(verify(l.f.observations));assertEquals(MembershipActivation.State.INSTALLING,l.campaign.state());}
    }
    @Test void verifierCannotSubstituteEvenAnotherValidPrefix()throws Exception {
        try(var l=new Local("published")) {
            assertThrows(IllegalArgumentException.class,()->l.offer((r,p,i)->l.f.original.seed.capsule));assertTrue(l.leader.originalSelection().isEmpty());
        }
    }
    @Test void deadlineAndHigherFenceAreRecheckedAfterCapsuleVerification()throws Exception {
        for(String mode:List.of("time","fence"))try(var l=new Local("genesis")) {
            assertThrows(Exception.class,()->l.offer((r,p,i)->{
                var result=MembershipCapsule.verify(r,p,i,Set.of());
                if(mode.equals("time"))l.clock.set(BUDGET);
                else {var ballot=new TreeMap<>(l.campaign.ballot());ballot.put("counter",number(ballot.get("counter"))+1);l.leader.observeCurrent(ballot);}
                return result;
            }));
            assertTrue(l.leader.originalSelection().isEmpty());assertEquals(MembershipActivation.State.ABANDONED,l.campaign.state());
        }
    }
    @Test void closedOrChangedReceiveFilesCannotEnterSelection()throws Exception {
        for(boolean closed:List.of(false,true))try(var l=new Local("genesis")) {
            if(closed)l.received.close();
            assertThrows(Exception.class,()->l.offer((r,p,i)->{
                if(!closed)try{l.received.close();}catch(IOException error){throw new UncheckedIOException(error);}
                return MembershipCapsule.verify(r,p,i,Set.of());
            }));assertTrue(l.leader.originalSelection().isEmpty());
        }
    }
    @Test void authenticatedOriginalAcceptedTailRemainsTheFirstSelectedEntry()throws Exception {
        try(var l=new Local("tail")) {
            l.offer(verify(Set.of()));var source=l.campaign.sources().stream().filter(s->s.owner.equals(l.identity())).findFirst().orElseThrow();
            assertArrayEquals(l.entry.bytes(),source.entry.bytes());assertEquals(l.entry.digest(),l.leader.originalSelection().orElseThrow().value().get("nextEntry"));assertThrows(IllegalArgumentException.class,l.campaign::votingSelection);
        }
    }
    @Test void closingAcceptedSourceBeforeInstallationAbandonsTheCampaign()throws Exception {
        try(var l=new Local("genesis")) {
            l.offer(verify(Set.of()));var selected=l.leader.originalSelection().orElseThrow();
            var before=V53ReplayFilesTest.files(l.f.request.targets().getFirst().replicaDirectory());l.received.close();
            assertThrows(Exception.class,l.campaign::sources);assertEquals(MembershipActivation.State.ABANDONED,l.campaign.state());
            assertArrayEquals(selected.bytes(),l.leader.originalSelection().orElseThrow().bytes());
            assertEquals(before,V53ReplayFilesTest.files(l.f.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void allActualInstallationsEndTheBorrowWithoutCreatingPublicReadiness()throws Exception {
        try(var l=new Local("genesis")) {
            l.offer(verify(Set.of()));var images=l.received.images();l.campaign.installLocal(List.of(),images);
            var request=l.campaign.installation(l.identity());
            var reply=MembershipActivation.install(l.peer,l.f.request.targets().getFirst().identity(),request,l.campaign.sources(),l.campaign.ancestry(),List.of(),images);
            l.campaign.installed(l.identity(),reply);assertEquals(MembershipActivation.State.INSTALLED,l.campaign.state());
            l.received.close();assertEquals(l.leader.originalSelection().orElseThrow().digest(),l.campaign.votingSelection().digest());
        }
    }
}
