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
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53CheckpointPullTest {
    @TempDir Path temp;
    static ReplicationBounds bound(){return V53TransferServiceTest.bound(2);}
    final class Local implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture f;
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipTransferService> services=new ArrayList<>();
        final MembershipCapsule higher;
        final MembershipCapsule.Anchor lower;
        final MembershipSelection.Bridge original;
        final AtomicLong clock=new AtomicLong();
        final List<Map<String,Object>> wire=new ArrayList<>();
        Local()throws Exception {
            Path root=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            f=new V53BootstrapPublicationTest.Fixture(root,Files.createDirectory(root.resolve("raw")),3,false);
            f.campaign(1);f.publish(1,false);
            try(var owner=f.open(f.request.targets().getFirst(),"lower")){lower=owner.floorCopyCurrent().capsule.terminal();}
            f.publish(2,true);original=f.bridges.stream().filter(b->b.statement.value().get("start").equals(lower.cut())).findFirst().orElseThrow();
            for(var t:f.request.targets()) {
                var budget=resources();budgets.add(budget);
                var owner=MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),budget,
                        (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,event->{});owners.add(owner);
                services.add(new MembershipTransferService(owner,f.ballot,budget,bound(),()->{},clock::get,0,BUDGET));
            }
            higher=owners.getFirst().floorCopyCurrent().capsule;assertNull(higher.anchor(1));
        }
        MembershipIdentity peer(int n){return f.request.targets().get(n).identity();}
        MembershipSourcePull.Link link(int reader){return (peer,request,kind,deadline)->{
            try {
                assertEquals(BUDGET,deadline);var reply=services.get(f.request.targets().stream().map(MembershipBootstrapTarget::identity).toList().indexOf(peer)).handle(peer(reader),request);
                wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));
                return CompletableFuture.completedFuture(reply);
            }catch(Exception error){return CompletableFuture.failedFuture(error);}
        };}
        MembershipSourcePull record(int reader,int source,MembershipSourcePull.Link link){return new MembershipSourcePull(higher,peer(reader),peer(source),f.ballot,UUID.randomUUID(),budgets.get(reader),bound(),link,()->{},clock::get,0,BUDGET);}
        MembershipCheckpointPull pull(int reader,MembershipSourcePull.Link link,MembershipSourcePull.Guard guard){return new MembershipCheckpointPull(owners.get(reader),higher,lower,f.ballot,budgets.get(reader),bound(),link,guard,clock::get,0,BUDGET);}
        @Override public void close()throws Exception {
            for(var service:services)service.close();for(var owner:owners)owner.close();for(var budget:budgets)assertEquals(0,budget.usage().leases());
        }
    }
    @Test void networkAncestryAtEveryStableSizeUsesOriginalOwnersAndWritesNoAuthority()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-checkpoint-pull/run-"+UUID.randomUUID()));
        System.out.println("v53CheckpointPullEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;f.campaign(1);f.publish(1,false);MembershipCapsule.Anchor lower;
                try(var owner=f.open(f.request.targets().getFirst(),"lower")){lower=owner.floorCopyCurrent().capsule.terminal();}
                f.publish(2,true);var original=f.bridges.stream().filter(b->b.statement.value().get("start").equals(lower.cut())).findFirst().orElseThrow();
                var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();var services=new ArrayList<MembershipTransferService>();
                var wire=new ArrayList<Map<String,Object>>();int count=size/2+1;long start=System.nanoTime();
                try {
                    for(var target:f.request.targets()) {
                        var budget=resources();budgets.add(budget);
                        var owner=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),budget,
                                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,event->{});owners.add(owner);
                        var service=new MembershipTransferService(owner,f.ballot,budget,bound(),()->{},System::nanoTime,start,BUDGET);services.add(service);
                        group.start(owners.size()-1,service,MembershipTransport.Events.NONE,bound(),budget);
                    }
                    var higher=owners.getLast().floorCopyCurrent().capsule;assertNull(higher.anchor(1));
                    var transport=group.transports.getLast();MembershipSourcePull.Link link=(peer,request,kind,deadline)->transport.exchange(peer,request,kind,deadline).thenApply(reply->{
                        wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));return reply;});
                    try(var pull=new MembershipCheckpointPull(owners.getLast(),higher,lower,f.ballot,budgets.getLast(),bound(),link,()->{},System::nanoTime,start,BUDGET)) {
                        var fetched=pull.fetch(group.identities.getFirst(),original.statement,original.acknowledgements.subList(0,count));
                        fetched.verify(higher,lower);assertSame(fetched,pull.bridge());
                        assertEquals(new HashSet<>(original.owned.stream().filter(o->original.acknowledgements.subList(0,count).stream().anyMatch(a->a.digest().equals(o.record()))).toList()),fetched.owned);
                        Files.write(raw.resolve("received-ancestry.gsr"),MembershipGenerationPlan.ancestry(List.of(fetched)));
                        Files.write(raw.resolve("received-observations.json"),canonical(V53JournalApplicationTest.observations(fetched.owned),65536));
                    }
                }finally {
                    for(var transport:group.transports)transport.close();for(var service:services)service.close();for(var owner:owners)owner.close();
                    for(var budget:budgets)assertEquals(0,budget.usage().leases());
                }
                f.snapshot("after");Files.write(raw.resolve("wire.json"),canonical(wire,4*1024*1024));
                cases.add(Map.of("size",size,"owners",count,"exchanges",wire.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-checkpoint-pull-v1","status","PASS","cases",cases,
                "network",true,"publicRuntime",false,"scope","original-compacted-ancestry"),65536));
    }
    @Test void copiedRemoteAcknowledgementCannotBecomeTheServingNodesObservation()throws Exception {
        try(var l=new Local();var pull=l.record(2,0,l.link(2))) {
            // Node 1 physically retains node 2's ACK, but is not its original owner.
            var ack=l.original.acknowledgements.get(1);
            assertThrows(IllegalArgumentException.class,()->pull.fetchCheckpointAcknowledgement(l.original.statement,ack));assertTrue(l.wire.isEmpty());
        }
    }
    @Test void actualPublishedAndSupplementalAcknowledgementsAreServedByTheirOwners()throws Exception {
        try(var l=new Local()) {
            var item=object(list(l.higher.packet.capsule().value().get("items")).getFirst());
            var statement=l.higher.context.record((String)item.get("statement"),"CHECKPOINT");
            var ack=l.higher.context.record((String)list(item.get("endorsements")).getFirst(),"CHECKPOINT_ACK");
            for(var records:List.of(List.of(statement,ack),List.of(l.original.statement,l.original.acknowledgements.getFirst())))
                try(var pull=l.record(2,0,l.link(2))) {
                    var receipt=pull.fetchCheckpointAcknowledgement(records.getFirst(),records.getLast());
                    assertTrue(l.f.observations.contains(receipt.owned()));assertArrayEquals(records.getLast().bytes(),receipt.acknowledgement().bytes());
                }
        }
    }
    @Test void mixedLocalAndRemoteQuorumUsesOriginalLocalStorage()throws Exception {
        try(var l=new Local();var pull=l.pull(0,l.link(0),()->{})) {
            var bridge=pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2));bridge.verify(l.higher,l.lower);
            assertEquals(2,bridge.owned.size());assertTrue(l.wire.stream().allMatch(row->object(object(parse(Arrays.copyOfRange(Base64.getDecoder().decode((String)row.get("request")),HEADER,Base64.getDecoder().decode((String)row.get("request")).length),FRAME)).get("recipient")).get("node").equals("node-2")));
        }
    }
    @Test void duplicateOwnersWrongEndpointsAndInsufficientQuorumFailBeforeTransfer()throws Exception {
        try(var l=new Local()) {
            var badStatement=new TreeMap<>(l.original.statement.value());badStatement.put("applicationBefore","a".repeat(64));
            for(String mode:List.of("duplicate","endpoint","quorum","foreign"))try(var pull=l.pull(2,l.link(2),()->{})) {
                var statement=mode.equals("endpoint")?decode(encode("records","CHECKPOINT",badStatement),"records","CHECKPOINT"):l.original.statement;
                var acks=mode.equals("duplicate")?List.of(l.original.acknowledgements.getFirst(),l.original.acknowledgements.getFirst()):
                        mode.equals("quorum")?List.of(l.original.acknowledgements.getFirst()):l.original.acknowledgements.subList(0,2);
                var source=mode.equals("foreign")?new MembershipIdentity(l.peer(0).nodeId(),UUID.randomUUID(),l.peer(0).endpoint()):l.peer(0);
                assertThrows(IllegalArgumentException.class,()->pull.fetch(source,statement,acks));assertTrue(l.wire.isEmpty());
            }
        }
    }
    @Test void wrongStatementAndIncarnationCannotCountAsAnOriginalAck()throws Exception {
        try(var l=new Local()) {
            var original=l.original.acknowledgements.getFirst();
            for(String mode:List.of("statement","incarnation"))try(var pull=l.record(2,0,l.link(2))) {
                var fields=new TreeMap<>(original.value());fields.put(mode,mode.equals("incarnation")?UUID.randomUUID().toString():"a".repeat(64));
                var changed=decode(encode("records","CHECKPOINT_ACK",fields),"records","CHECKPOINT_ACK");
                assertThrows(IllegalArgumentException.class,()->pull.fetchCheckpointAcknowledgement(l.original.statement,changed));assertTrue(l.wire.isEmpty());
            }
        }
    }
    @Test void originalDeadlineAndFencingCoverAllRecordsWithoutRenewal()throws Exception {
        for(String mode:List.of("deadline","fence"))try(var l=new Local()) {
            var fenced=new AtomicBoolean();
            {
                var calls=new AtomicInteger();
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->l.link(2).exchange(peer,request,kind,deadline).thenApply(reply->{
                    if(request.kind().equals("TRANSFER_COMMIT") && calls.incrementAndGet()==1){if(mode.equals("deadline"))l.clock.set(BUDGET);else fenced.set(true);}return reply;});
                try(var pull=l.pull(2,link,()->{if(fenced.get())throw new IOException("higher promise");})) {
                    assertThrows(Exception.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));
                    assertThrows(Exception.class,pull::bridge);assertEquals(1,calls.get());
                    assertEquals(1,l.budgets.get(2).usage().counts().get(MembershipResources.Unit.CONTROL)); // only its serving scope remains
                }
            }
        }
    }
    @Test void cancellationDrainsPendingFetchAndCannotReturnAPartialBridge()throws Exception {
        try(var l=new Local()) {
            var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            try(var pull=l.pull(2,(peer,request,kind,deadline)->{entered.countDown();return pending;},()->{})) {
                var work=CompletableFuture.runAsync(()->{assertThrows(IOException.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));});
                assertTrue(entered.await(5,TimeUnit.SECONDS));pull.close();work.get(5,TimeUnit.SECONDS);
                assertTrue(pending.isCancelled());assertThrows(IllegalArgumentException.class,pull::bridge);
            }
        }
    }
    @Test void lostCommitRetriesIdenticalRequestAndDoesNotMintExtraOwners()throws Exception {
        try(var l=new Local()) {
            var lost=new AtomicBoolean();var retries=new ArrayList<String>();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                var reply=l.link(2).exchange(peer,request,kind,deadline);
                if(request.kind().equals("TRANSFER_COMMIT")){retries.add(request.digest());if(lost.compareAndSet(false,true))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost ACK",null));}
                return reply;
            };
            try(var pull=l.pull(2,link,()->{})) {
                var bridge=pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2));
                assertEquals(2,bridge.owned.size());assertEquals(4,retries.size());assertEquals(retries.get(0),retries.get(1));
            }
        }
    }
    @Test void permanentlyUnavailableOwnerFailsAfterBoundedRetries()throws Exception {
        try(var l=new Local()) {
            var calls=new AtomicInteger();
            try(var pull=l.pull(2,(peer,request,kind,deadline)->{calls.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"unavailable",null));},()->{})) {
                assertThrows(MembershipTransport.Failure.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));
                assertEquals(Math.min(3,bound().maxRetryAttempts()),calls.get());assertThrows(IllegalArgumentException.class,pull::bridge);
            }
        }
    }
    @Test void closedOrReplacedPhysicalOwnerRevokesCheckpointExport()throws Exception {
        for(String mode:List.of("closed","replaced"))try(var l=new Local()) {
            var ack=l.original.acknowledgements.getFirst();
            try(var export=l.owners.getFirst().exportRecord(ack.digest(),"CHECKPOINT_ACK",l.f.ballot,l.clock::get,0,BUDGET)) {
                if(mode.equals("closed"))l.owners.getFirst().close();
                else {
                    Path path;
                    try(var paths=Files.walk(l.f.request.targets().getFirst().replicaDirectory())){path=paths.filter(p->p.getFileName().toString().equals("ancestry.gsr")).findFirst().orElseThrow();}
                    Path replacement=temp.resolve("replacement-"+UUID.randomUUID());Files.copy(path,replacement);Files.move(replacement,path,StandardCopyOption.REPLACE_EXISTING);
                }
                assertThrows(Exception.class,()->export.read(ack.digest(),0,4096));
            }
        }
    }
    @Test void unusedPacketCheckpointExtrasCannotBeExportedAsObservations()throws Exception {
        // Adversarial byte/storage fixture only; its model observations are not network evidence.
        var capsule=new V53CapsuleFixture(3,"REPLACE",1);var item=object(list(capsule.capsule.get("items")).getFirst());
        var value=new TreeMap<>(decode(capsule.objects.get(item.get("statement")),"records","CHECKPOINT").value());value.put("applicationBefore","a".repeat(64));
        var extra=decode(encode("records","CHECKPOINT",value),"records","CHECKPOINT");capsule.objects.put(extra.digest(),extra.bytes());
        var ack=decode(encode("records","CHECKPOINT_ACK",Map.of("root",value.get("root"),"statement",extra.digest(),"cut",value.get("end"),
                "voter","node-1","incarnation",V53DeclarationsTest.node(1).storageId().toString())),"records","CHECKPOINT_ACK");capsule.objects.put(ack.digest(),ack.bytes());
        var fixture=new V53CurrentGenerationFixture(3,capsule);Path path=temp.resolve("unused-extras");fixture.provision(path);var resources=resources();
        try(var owner=MembershipGrantJournal.openGenerations(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,event->{})) {
            var before=V53ReplayFilesTest.files(path);var ballot=capsule.source.ballot(10);
            var valid=fixture.admitted.context.record((String)list(item.get("endorsements")).getFirst(),"CHECKPOINT_ACK");
            try(var exported=owner.exportRecord(valid.digest(),valid.kind(),ballot,()->0,0,BUDGET)){assertArrayEquals(valid.bytes(),exported.read(valid.digest(),0,4096));}
            for(var record:List.of(extra,ack)) {
                assertTrue(fixture.admitted.packet.objectNames().contains(record.digest()));
                assertEquals("original forced record unavailable",assertThrows(IllegalArgumentException.class,
                        ()->owner.exportRecord(record.digest(),record.kind(),ballot,()->0,0,BUDGET)).getMessage());
                assertEquals("original forced record unavailable",assertThrows(IllegalArgumentException.class,
                        ()->owner.exportTransfer(record.digest(),fixture.admitted.context.authority(),ballot,()->0,0,BUDGET)).getMessage());
            }
            assertEquals(before,V53ReplayFilesTest.files(path));
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void capacityRejectionDoesNotRetryAndAllReceivingLeasesAreReleased()throws Exception {
        try(var l=new Local()) {
            var calls=new AtomicInteger();
            try(var pull=l.pull(2,(peer,request,kind,deadline)->{calls.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"full",null));},()->{})) {
                assertThrows(MembershipTransport.Failure.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));
                assertEquals(1,calls.get());assertEquals(1,l.budgets.get(2).usage().counts().get(MembershipResources.Unit.CONTROL));
            }
            var held=new ArrayList<MembershipResources.Lease>();
            try {
                while(l.budgets.get(2).usage().counts().get(MembershipResources.Unit.CONTROL)<MembershipResources.Unit.CONTROL.count)
                    held.add(l.budgets.get(2).reserve(MembershipResources.Unit.CONTROL,"pressure-"+held.size(),1));
                try(var pull=l.pull(2,l.link(2),()->{})){assertThrows(IllegalArgumentException.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));}
                assertTrue(l.wire.isEmpty());
            }finally{for(var lease:held)lease.close();}
        }
    }
    @Test void resultCannotBeReusedAfterCloseOrASecondInvocation()throws Exception {
        try(var l=new Local();var pull=l.pull(2,l.link(2),()->{})) {
            pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2));
            assertThrows(IllegalArgumentException.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));
            pull.close();assertThrows(IllegalArgumentException.class,pull::bridge);
            assertEquals(1,l.budgets.get(2).usage().counts().get(MembershipResources.Unit.CONTROL));
        }
    }
    @Test void actualHigherPromiseFencesWithoutDependingOnCallerGuard()throws Exception {
        try(var l=new Local()) {
            var seen=new AtomicBoolean();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->l.link(2).exchange(peer,request,kind,deadline).thenApply(reply->{
                if(request.kind().equals("TRANSFER_COMMIT") && seen.compareAndSet(false,true)) {
                    var higher=new TreeMap<>(l.f.ballot);higher.put("counter",9L);
                    l.owners.get(2).observeCurrent(higher);
                }
                return reply;
            });
            try(var pull=l.pull(2,link,()->{})) {
                assertThrows(IllegalArgumentException.class,()->pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2)));
                assertTrue(seen.get());assertThrows(IllegalArgumentException.class,pull::bridge);
            }
        }
    }
    @Test void completedRemoteProofStillRequiresLiveLocalAuthorityBeforeUse()throws Exception {
        try(var l=new Local();var pull=l.pull(2,l.link(2),()->{})) {
            pull.fetch(l.peer(0),l.original.statement,l.original.acknowledgements.subList(0,2));
            l.owners.get(2).close();assertThrows(Exception.class,pull::bridge);
        }
    }
}
