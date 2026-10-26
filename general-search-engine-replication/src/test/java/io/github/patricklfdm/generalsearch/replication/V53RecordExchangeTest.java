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

class V53RecordExchangeTest {
    @TempDir Path temp;
    static void promise(Decoded value,MembershipContext context,Map<String,Object> ballot) {
        assertEquals(context.root,value.value().get("root"));assertEquals(context.authority(),value.value().get("view"));
        assertEquals(ballot,value.value().get("ballot"));assertNotNull(value.value().get("basisId"));
    }
    @Test void actualTcpPrepareFetchesTheOriginalProposerPromiseBeforeGranting()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-record-exchange/run-"+UUID.randomUUID()));
        System.out.println("v53RecordExchangeEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;var receiving=resources();var leader=group.identities.getFirst();var follower=group.identities.get(1);
                var target=f.request.targets().get(1);var transferRows=new ArrayList<Map<String,Object>>();var remote=new AtomicReference<MembershipTransport>();
                var events=new CopyOnWriteArrayList<String>();
                try(var owner=f.open(f.request.targets().getFirst(),"record-source");
                    var receiver=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),f.result.root(),follower,
                        receiving,(r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,events::add);
                    var campaign=new MembershipActivation(owner,f.resources,System::nanoTime,BUDGET)) {
                    var original=owner.promised().orElseThrow();var request=campaign.prepare(follower);var trace=UUID.randomUUID();long start=System.nanoTime();
                    Path captured=Files.createDirectory(raw.resolve("captured"));for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
                    try(var exported=owner.exportRecord(original.digest(),"PROMISE",campaign.ballot(),System::nanoTime,start,BUDGET);
                        var session=new MembershipSourceSession(exported,follower,trace,f.resources,128,FRAME,System::nanoTime,start,BUDGET)) {
                        var transport=group.start(0,session,MembershipTransport.Events.NONE,bounds(),f.resources);
                        var service=group.start(1,(sender,incoming)->{
                            assertEquals("PREPARE",incoming.kind());assertEquals(leader,sender);
                            MembershipSourcePull.Link link=(peer,frame,kind,deadline)->remote.get().exchange(peer,frame,kind,deadline).thenApply(reply->{
                                transferRows.add(Map.of("request",Base64.getEncoder().encodeToString(frame.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));return reply;});
                            try(var pull=new MembershipSourcePull(group.capsule,follower,leader,object(incoming.value().get("ballot")),trace,
                                    receiving,bounds(),link,()->{},System::nanoTime,start,BUDGET)) {
                                var fetched=pull.fetchRecord((String)object(incoming.value().get("payload")).get("promise"),"PROMISE",value->{promise(value,group.capsule.context,campaign.ballot());events.add("record-validated");});
                                events.add("record-returned");
                                Files.write(raw.resolve("received.gsr"),fetched.bytes());
                                var reply=MembershipActivation.prepare(receiver,sender,incoming,fetched).response();events.add("prepare-replied");return reply;
                            }
                        },MembershipTransport.Events.NONE,bounds(),receiving);remote.set(service);
                        var response=transport.exchange(follower,request,"PROMISE",start+BUDGET).get(30,TimeUnit.SECONDS);
                        Files.write(raw.resolve("prepare.json"),canonical(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(response.bytes())),65536));
                        assertEquals(receiver.originalBasis().orElseThrow().digest(),object(response.value().get("payload")).get("basis"));
                        assertArrayEquals(original.bytes(),Files.readAllBytes(raw.resolve("received.gsr")));
                        assertTrue(receiver.originalSelection().isEmpty());assertEquals(MembershipActivation.State.PREPARING,campaign.state());
                    }
                }
                for(var transport:group.transports)transport.close();assertEquals(0,receiving.usage().leases());
                f.snapshot("after");Files.write(raw.resolve("wire.json"),canonical(transferRows,1024*1024));Files.write(raw.resolve("events.json"),canonical(events,65536));cases.add(Map.of("size",size,"exchanges",transferRows.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-record-exchange-v1","status","PASS","cases",cases,
                "publicRuntime",false,"network",true,"scope","original-promise-before-prepare"),65536));
    }
    final class Local implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture fixture;
        final MembershipGrantJournal owner;
        final MembershipSelection.Source source;
        final MembershipResources receiving=resources();
        final AtomicLong clock=new AtomicLong();
        Local()throws Exception {
            Path root=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            fixture=new V53BootstrapPublicationTest.Fixture(root,Files.createDirectory(root.resolve("raw")),3,false);
            owner=fixture.open(fixture.request.targets().getFirst(),"record");source=owner.beginActivation();
        }
        MembershipRecordExport export(Decoded record)throws Exception {return owner.exportRecord(record.digest(),record.kind(),object(source.basis.value().get("ballot")),clock::get,0,BUDGET);}
        MembershipSourcePull client(UUID trace,MembershipSourcePull.Link link){return new MembershipSourcePull(source.capsule,fixture.request.targets().get(1).identity(),source.owner,
                object(source.basis.value().get("ballot")),trace,receiving,bounds(),link,()->{},clock::get,0,BUDGET);}
        @Override public void close()throws Exception {owner.close();assertEquals(0,fixture.resources.usage().leases());assertEquals(0,receiving.usage().leases());}
    }
    @Test void originalReferenceAndKindAreRequiredAndNoBytesAreWritten()throws Exception {
        try(var f=new Local()) {
            var before=V53ReplayFilesTest.files(f.fixture.request.targets().getFirst().replicaDirectory());int leases=f.fixture.resources.usage().leases();
            var ballot=object(f.source.basis.value().get("ballot"));
            assertThrows(IllegalArgumentException.class,()->f.owner.exportRecord("0".repeat(64),"PROMISE",ballot,f.clock::get,0,BUDGET));
            assertThrows(IllegalArgumentException.class,()->f.owner.exportRecord(f.source.basis.digest(),"PROMISE",ballot,f.clock::get,0,BUDGET));
            assertThrows(IllegalArgumentException.class,()->f.owner.exportRecord(f.source.basis.digest(),"ROOT",ballot,f.clock::get,0,BUDGET));
            assertEquals(leases,f.fixture.resources.usage().leases());assertEquals(before,V53ReplayFilesTest.files(f.fixture.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void expiryOwnerCloseAndPhysicalReplacementRevokeRecordBorrow()throws Exception {
        for(String mode:List.of("expiry","close","replace"))try(var f=new Local()) {
            var record=f.owner.promised().orElseThrow();var export=f.export(record);
            if(mode.equals("expiry"))f.clock.set(BUDGET);
            else if(mode.equals("close"))f.owner.close();
            else {Path p=f.fixture.request.targets().getFirst().replicaDirectory().resolve("grants.gsr"),replacement=temp.resolve("replacement");Files.copy(p,replacement);Files.move(replacement,p,StandardCopyOption.REPLACE_EXISTING);}
            assertThrows(Exception.class,()->export.read(record.digest(),0,32));export.close();
            assertEquals(0,f.fixture.resources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0));
        }
    }
    @Test void retainedOlderPromiseIsNotReplacedByTheLatestGrant()throws Exception {
        try(var f=new Local()) {
            var original=f.owner.promised().orElseThrow();try(var export=f.export(original)) {
                f.owner.beginActivation();assertNotEquals(original.digest(),f.owner.promised().orElseThrow().digest());
                assertArrayEquals(original.bytes(),export.read(original.digest(),0,4*1024*1024));
            }
        }
    }
    @Test void retirementDoesNotPinTheJournalAndRevokesTheMissingOriginal()throws Exception {
        var helper=new V53SourceReleaseTest();helper.temp=temp;Path path=temp.resolve("retire/authority");String old=helper.provision(path);var resources=helper.resources();var clock=new AtomicLong();
        try(var owner=helper.open(path,resources,event->{})) {
            var record=owner.planSourceRetirement(old).basis;
            try(var export=owner.exportRecord(record.digest(),"BASIS",object(record.value().get("ballot")),clock::get,0,BUDGET)) {
                assertArrayEquals(record.bytes(),export.read(record.digest(),0,4096));owner.retireSource(old);
                assertThrows(IllegalArgumentException.class,export::references);clock.set(-1);
                assertThrows(IllegalArgumentException.class,()->export.read(record.digest(),0,1));
                assertEquals(0,resources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0));
            }
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void semanticFailureCannotCommitAndRecordBuffersAreReleased()throws Exception {
        try(var f=new Local()) {
            var record=f.owner.promised().orElseThrow();var trace=UUID.randomUUID();var reader=f.fixture.request.targets().get(1).identity();var kinds=new ArrayList<String>();
            try(var export=f.export(record);var session=new MembershipSourceSession(export,reader,trace,f.fixture.resources,128,FRAME,f.clock::get,0,BUDGET);
                var pull=f.client(trace,(peer,request,kind,deadline)->{kinds.add(kind);try{return CompletableFuture.completedFuture(session.handle(reader,request));}catch(Exception error){return CompletableFuture.failedFuture(error);}})) {
                assertThrows(IOException.class,()->pull.fetchRecord(record.digest(),"PROMISE",v->{throw new IOException("wrong expected promise");}));
                assertFalse(kinds.contains("TRANSFER_COMMIT"));assertEquals(0,f.receiving.usage().leases());
            }
        }
    }
    @Test void lostCommitReplyReplaysExactBytesAndRetainsReceivedRecordUntilClose()throws Exception {
        try(var f=new Local()) {
            var record=f.owner.promised().orElseThrow();var trace=UUID.randomUUID();var reader=f.fixture.request.targets().get(1).identity();var dropped=new AtomicBoolean();var commits=new ArrayList<String>();
            try(var export=f.export(record);var session=new MembershipSourceSession(export,reader,trace,f.fixture.resources,128,FRAME,f.clock::get,0,BUDGET);
                var pull=f.client(trace,(peer,request,kind,deadline)->{
                    try{var reply=session.handle(reader,request);if(kind.equals("TRANSFER_COMMIT")){commits.add(request.digest());if(dropped.compareAndSet(false,true))return CompletableFuture.failedFuture(lost());}return CompletableFuture.completedFuture(reply);}
                    catch(Exception error){return CompletableFuture.failedFuture(error);}})) {
                assertArrayEquals(record.bytes(),pull.fetchRecord(record.digest(),"PROMISE",v->promise(v,f.source.capsule.context,object(record.value().get("ballot")))).bytes());
                assertEquals(2,commits.size());assertEquals(1,new HashSet<>(commits).size());assertEquals(record.size(),f.receiving.usage().queued());
                assertThrows(IllegalArgumentException.class,()->pull.fetchRecord(record.digest(),"PROMISE",v->{}));
            }
            assertEquals(0,f.receiving.usage().leases());
        }
    }
    @Test void sharedControlCapacityAndOriginalDeadlineAreNotExtended()throws Exception {
        try(var f=new Local()) {
            var held=new ArrayList<MembershipResources.Lease>();
            try {
                for(int i=0;i<256;i++)held.add(f.fixture.resources.reserve(MembershipResources.Unit.CONTROL,"full-"+i,1));
                assertThrows(IllegalArgumentException.class,()->f.export(f.owner.promised().orElseThrow()));
            }finally{held.forEach(MembershipResources.Lease::close);}
            f.clock.set(BUDGET);assertThrows(IllegalArgumentException.class,()->f.export(f.owner.promised().orElseThrow()));
            assertEquals(0,f.fixture.resources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0));
        }
    }
    @Test void allSevenKindsComeFromActualForcedGrantOrVoteRecords()throws Exception {
        var fixture=new V53JournalApplicationTest();fixture.temp=temp;fixture.setup(temp.resolve("votes"));Path root=temp.resolve("votes");
        var r=resources();try(var owner=fixture.open(root,1,r,e->{})) {
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(fixture.f.f.node(root,1).resolve(MembershipPendingAccept.FILE)));
            var original=new ArrayList<>(List.of(owner.originalBasis().orElseThrow(),vote.promise(),vote.selected(),vote.entry(),vote.accept(),vote.proof(),vote.certificate()));
            var kinds=new HashSet<String>();var clock=new AtomicLong();var context=owner.activationContext();
            for(var record:original)try(var export=owner.exportRecord(record.digest(),record.kind(),object(vote.accept().value().get("ballot")),clock::get,0,BUDGET)) {
                kinds.add(record.kind());assertArrayEquals(record.bytes(),export.read(record.digest(),0,4*1024*1024));
                var transfer=UUID.randomUUID();var receiving=resources();var reader=V53DeclarationsTest.node(2);
                try(var session=new MembershipSourceSession(export,reader,transfer,r,128,FRAME,clock::get,0,BUDGET);
                    var pull=new MembershipSourcePull(owner.floorCopyCurrent().capsule,reader,V53DeclarationsTest.node(1),object(vote.accept().value().get("ballot")),transfer,
                        receiving,bounds(),(peer,request,kind,deadline)->{try{return CompletableFuture.completedFuture(session.handle(reader,request));}catch(Exception error){return CompletableFuture.failedFuture(error);}},()->{},clock::get,0,BUDGET)) {
                    assertArrayEquals(record.bytes(),pull.fetchRecord(record.digest(),record.kind(),v->assertEquals(context.root,v.value().get("root"))).bytes());
                }
                assertEquals(0,receiving.usage().leases());
            }
            assertEquals(Set.of("PROMISE","BASIS","SELECTED","ENTRY","ACCEPT","PROOF","CERTIFICATE"),kinds);
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void publishedOriginalsRemainFetchableFromVerifiedCurrentPacketAfterVoteRetirement()throws Exception {
        Path root=Files.createDirectory(temp.resolve("published"));var f=new V53BootstrapPublicationTest.Fixture(root,Files.createDirectory(root.resolve("raw")),3,false);
        f.campaign(1);f.publish(1,false);var clock=new AtomicLong();
        try(var owner=f.open(f.request.targets().getFirst(),"published-record")) {
            assertTrue(owner.currentCertificate().isEmpty());var capsule=owner.floorCopyCurrent().capsule;int count=0;
            var kinds=object(CATALOG.get("records"));
            for(String digest:capsule.packet.objectNames()) {
                byte[] bytes=capsule.packet.objectBytes(digest);if(bytes.length<HEADER || java.nio.ByteBuffer.wrap(bytes).getInt()!=0x47534552)continue;
                int id=Short.toUnsignedInt(java.nio.ByteBuffer.wrap(bytes).getShort(8));
                String kind=kinds.entrySet().stream().filter(v->number(object(v.getValue()).get("id"))==id).map(Map.Entry::getKey).findFirst().orElseThrow();
                if(!MembershipRecordExport.KINDS.contains(kind))continue;
                try(var export=owner.exportRecord(digest,kind,f.ballot,clock::get,0,BUDGET)){assertArrayEquals(bytes,export.read(digest,0,4*1024*1024));count++;}
            }
            assertTrue(count>=2,"published packet retains actual first entry and proof records");
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
