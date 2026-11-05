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

class V53RetainedProvenanceTest {
    @TempDir Path temp;
    @Test void actualTcpHistoricalCopiesRequireNoLiveHistoricalVoteQueries()throws Exception {
        var evidence=Files.createDirectories(Path.of("target/v53-retained-provenance/run-"+UUID.randomUUID()));System.out.println("v53RetainedProvenanceEvidence="+evidence.toAbsolutePath());
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
                        var received=pull.fetchPrefix(scratch);var verified=pull.verifiedPrefix();
                        assertEquals(hint.cut(),verified.context.cut);
                        assertThrows(IllegalArgumentException.class,()->MembershipCapsule.verify(f.original.seed.rootRecord,received.packet(),received.images(),Set.of()));
                        assertEquals(verified.context.cut,verified.verifyExtension(received.packet(),received.images(),Set.of()).context.cut);assertNull(received.packetBinding().basisId());assertNull(received.packetBinding().basisDigest());
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
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-retained-provenance-v1","status","PASS","cases",cases,
                "network",true,"publicRuntime",false,"adoption",false,"scope","authenticated-complete-historical-copy"),65536));
    }
    final class Adopted implements AutoCloseable {
        final V53AdoptionFenceFixture fixture=new V53AdoptionFenceFixture(3,7);
        final MembershipResources a=resources(),b=resources();
        final MembershipGrantJournal source,reader;
        final MembershipTransferService service;
        final MembershipSourcePull pull;
        final MembershipSourceReceive received;
        final MembershipCapsule copied;
        final List<String> calls=new ArrayList<>();
        final AtomicLong clock=new AtomicLong();
        final Path scratch;
        Adopted(boolean extra)throws Exception {
            var root=Files.createDirectory(temp.resolve("case-"+UUID.randomUUID()));
            if(extra) {
                var next=fixture.remote.source.steps.get(7);
                for(String key:List.of("entry","accept","proof","certificate"))fixture.remote.add((String)next.get(key));
                fixture.remote.add((String)fixture.remote.entry(7).get("payload"));
            }
            fixture.provision(root.resolve("source"));V53FloorWorker.provision(root.resolve("reader"),3,0,3);
            source=fixture.open(root.resolve("source"),a,e->{});source.adoptCurrent(fixture.remote.packet(),fixture.remote.source.images,List.of());
            reader=MembershipGrantJournal.openGenerations(root.resolve("reader"),fixture.initial.root(),V53DeclarationsTest.node(3),b,
                    (r,p,m)->MembershipCapsule.verify(r,p,m,fixture.owned),e->{});
            service=MembershipTransferService.prefix(source,a,bounds(),()->{},clock::get,0,BUDGET);
            pull=MembershipSourcePull.prefix(reader,new MembershipDiscovery.Hint(source.activationIdentity(),source.activationContext().cut,false),b,bounds(),
                    (peer,request,kind,deadline)->{calls.add(request.kind());try{return CompletableFuture.completedFuture(service.handle(reader.activationIdentity(),request));}
                        catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}},()->{},clock::get,0,BUDGET);
            scratch=root.resolve("received");received=pull.fetchPrefix(scratch);copied=pull.verifiedPrefix();
        }
        Decoded edge(){return decode(copied.packet.objectBytes((String)object(list(copied.packet.capsule().value().get("items")).get(1)).get("certificate")),"records","CERTIFICATE");}
        Map<String,Object> parent(){return copied.anchor(5).cut();}
        @Override public void close()throws Exception {pull.close();service.close();reader.close();source.close();assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());}
    }
    @Test void historicalMembershipCopyIsDistinctFromFreshAcceptProofAndCheckpointVotes()throws Exception {
        try(var a=new Adopted(false)) {
            var certificate=a.edge();var context=a.copied.context;
            assertNotNull(a.copied.publicationCertificate(certificate,a.parent()));
            assertThrows(IllegalArgumentException.class,()->context.certificateAt(certificate,Set.of(),a.parent()));
            assertThrows(IllegalArgumentException.class,()->MembershipCapsule.verify(a.fixture.remote.source.root,a.received.packet(),a.received.images(),Set.of()));
            assertTrue(a.calls.stream().allMatch(v->Set.of("CHUNK","TRANSFER_COMMIT").contains(v)));assertFalse(a.calls.isEmpty());
            assertFalse(context.voters().contains("node-3")); // the old reader has actually been removed
        }
    }
    @Test void ownedReceivedHistorySurvivesSourceCloseUntilLocalReceiveEnds()throws Exception {
        try(var a=new Adopted(false)) {
            var images=a.received.images();var packet=a.received.packet();var certificate=a.edge();var parent=a.parent();
            a.service.close();a.source.close();
            var reused=a.copied.verifyExtension(packet,images,Set.of());assertEquals(a.copied.context.cut,reused.context.cut);
            assertNotNull(reused.publicationCertificate(certificate,parent));
            assertNotNull(a.pull.verifiedPrefix());a.pull.close();assertThrows(IllegalArgumentException.class,a.pull::verifiedPrefix);
        }
    }
    @Test void alternateWellFormedHistoricalCertificateDoesNotInheritAnotherCopiesAuthority()throws Exception {
        try(var a=new Adopted(false)) {
            var certificate=a.fixture.reprove(6,50);var item=object(list(a.fixture.remote.capsule.get("items")).get(1));item.put("certificate",certificate.digest());
            var packet=a.fixture.remote.packet();var context=new MembershipContext(a.fixture.remote.source.root,
                    decode(packet.objectBytes((String)packet.capsule().value().get("catalog")),"records","CATALOG"),a.copied.context.cut,
                    a.fixture.remote.objects,a.fixture.remote.source.images);
            assertNotNull(context.certificateStructure(certificate,a.parent()));
            assertThrows(IllegalArgumentException.class,()->a.copied.verifyExtension(packet,a.fixture.remote.source.images,Set.of()));
        }
    }
    @Test void changedCheckpointWitnessSetRequiresNewExactAuthority()throws Exception {
        try(var a=new Adopted(false)) {
            var item=object(list(a.fixture.remote.capsule.get("items")).getFirst());var endorsements=new ArrayList<>(list(item.get("endorsements")));
            endorsements.removeLast();item.put("endorsements",endorsements);
            var packet=a.fixture.remote.packet(); // two original stable voters are still a valid majority
            assertThrows(IllegalArgumentException.class,()->a.copied.verifyExtension(packet,a.fixture.remote.source.images,Set.of()));
        }
    }
    @Test void unusedInventoryCertificateCannotBePromotedToAuthenticatedHistory()throws Exception {
        try(var a=new Adopted(true)) {
            var next=a.fixture.remote.source.steps.get(7);var certificate=decode(a.copied.packet.objectBytes((String)next.get("certificate")),"records","CERTIFICATE");
            assertNotNull(a.copied.context.certificateStructure(certificate,a.copied.context.cut));
            assertThrows(IllegalArgumentException.class,()->a.copied.publicationCertificate(certificate,a.copied.context.cut));
            assertNotNull(a.copied.publicationCertificate(a.edge(),a.parent()));
        }
    }
    @Test void copyingAnAuthenticatedMembershipProofThroughAnotherCompactionPreservesItsExactParent()throws Exception {
        try(var a=new Adopted(false)) {
            var certificate=a.edge();var images=a.received.images();var copied=a.copied.retainingCertificate(a.copied,certificate,a.parent(),images);
            assertNotNull(copied.publicationCertificate(certificate,a.parent()));
            var wrong=new TreeMap<>(a.parent());wrong.put("entry","f".repeat(64));
            assertThrows(IllegalArgumentException.class,()->copied.publicationCertificate(certificate,wrong));
        }
    }
    @Test void completeGrantSourcesAuthenticateHistoricalCopiesWithoutInventingOldVoterObservations()throws Exception {
        var helper=new V53SourceExchangeTest();helper.temp=temp;
        try(var l=helper.new Local();var pull=l.client(l::deliver,()->{})) {
            var received=pull.fetch(temp.resolve("grant"),l.original.basis.digest());var result=pull.verifiedOriginalSource();
            assertEquals(l.original.reference(),result.reference());assertArrayEquals(received.packet().bytes(),result.capsule.packet.bytes());
            assertThrows(IllegalArgumentException.class,pull::verifiedPrefix);
        }
    }
    @Test void uncompletedAndGenericRecordPullsCannotMintRetainedPrefixAuthority()throws Exception {
        var helper=new V53SourceExchangeTest();helper.temp=temp;
        try(var l=helper.new Local();var pull=l.client(l::deliver,()->{})) {
            assertThrows(IllegalArgumentException.class,pull::verifiedOriginalSource);
            pull.fetchRecord(l.original.basis.digest(),"BASIS",r->{});
            assertThrows(IllegalArgumentException.class,pull::verifiedOriginalSource);
        }
    }
    @Test void exactReceivingBytesAndLiveLocalFenceRemainRequiredBeforeTrustingACopy()throws Exception {
        for(String failure:List.of("file","fence","deadline","closed"))try(var a=new Adopted(false)) {
            switch(failure) {
                case "file" -> Files.write(a.scratch.resolve("source.gscp"),new byte[]{1});
                case "fence" -> {var higher=new TreeMap<>(a.reader.discoveryState(a.b).ballot());higher.put("counter",100L);a.reader.observeCurrent(higher);}
                case "deadline" -> a.clock.set(BUDGET);
                case "closed" -> a.pull.close();
            }
            assertThrows(IllegalArgumentException.class,a.pull::verifiedPrefix,failure);
        }
    }
    @Test void publicCopyHandleCannotBeConstructedFromHashesOrPlainRecords()throws Exception {
        assertTrue(Arrays.stream(MembershipSourcePull.RetainedCopy.class.getDeclaredConstructors()).allMatch(v->java.lang.reflect.Modifier.isPrivate(v.getModifiers())));
        var f=new V53CapsuleFixture(3,"REPLACE",7);
        assertThrows(NullPointerException.class,()->MembershipCapsule.verifyRetained(f.source.root,f.packet(),f.source.images,null));
        assertThrows(IllegalArgumentException.class,()->MembershipCapsule.verify(f.source.root,f.packet(),f.source.images,Set.of()));
    }
    @Test void retainedCopyStillRejectsIncompletePhasesAndInsufficientQuorumsFromAnAdversarialHandler()throws Exception {
        for(String fault:List.of("missing-accept","missing-descriptor","quorum"))try(var a=new Adopted(false)) {
            var f=a.fixture.remote;var item=object(list(f.capsule.get("items")).get(fault.equals("quorum")?2:1));
            var certificate=decode(f.objects.get((String)item.get("certificate")),"records","CERTIFICATE");
            if(fault.equals("missing-descriptor"))f.objects.remove(item.get("descriptor"));
            else {
                var common=new TreeMap<>(certificate.value());common.remove("accepts");common.remove("proofs");
                if(fault.equals("missing-accept"))f.objects.remove(hash(encode("records","ACCEPT",common)));
                else {
                    var cert=new TreeMap<>(certificate.value());
                    // Two witnesses satisfy the byte format and old stable majority,
                    // but the removed node cannot supply the new majority for FINAL.
                    cert.put("accepts",list(cert.get("accepts")).stream().filter(v->Set.of("node-1","node-3").contains(object(v).get("voter"))).toList());
                    assertEquals(2,list(cert.get("accepts")).size());
                    common.put("accepts",cert.get("accepts"));byte[] proof=encode("records","PROOF",common);f.objects.put(hash(proof),proof);
                    byte[] encoded=encode("records","CERTIFICATE",cert);f.objects.put(hash(encoded),encoded);item.put("certificate",hash(encoded));
                }
            }
            var packet=f.packet();var encoded=packet.bytes();var blobs=new TreeMap<String,byte[]>();blobs.put(hash(encoded),encoded);blobs.putAll(f.source.images);
            var refs=new TreeMap<String,MembershipSourceExport.Content>();
            refs.put(hash(encoded),new MembershipSourceExport.Content(hash(encoded),encoded.length,MembershipTransfer.Kind.CAPSULE));
            refs.put(cutDigest(a.copied.context.cut),refs.get(hash(encoded)));
            packet.images().forEach((digest,size)->refs.put(digest,new MembershipSourceExport.Content(digest,size,MembershipTransfer.Kind.APPLICATION)));
            var fake=new MembershipTransferExport() {
            public List<MembershipResources.Lease> closeReservations(){return List.of();}
                public MembershipContext context(){return a.copied.context;}
                public MembershipIdentity identity(){return a.source.activationIdentity();}
                public Map<String,Object> ballot(){return Map.of();}
                public Map<String,MembershipSourceExport.Content> references(){return refs;}
                public void request(MembershipIdentity sender,Decoded request,UUID session){MembershipPrefixExport.envelope(context(),identity(),sender,request);}
                public byte[] read(String digest,long offset,int maximum){var bytes=blobs.get(digest);return Arrays.copyOfRange(bytes,(int)offset,(int)Math.min(bytes.length,offset+maximum));}
                public void close(){}
            };
            var session=new AtomicReference<MembershipSourceSession>();
            try(var pull=MembershipSourcePull.prefix(a.reader,new MembershipDiscovery.Hint(a.source.activationIdentity(),a.copied.context.cut,false),a.b,bounds(),
                    (peer,request,kind,deadline)->{try {
                        if(session.get()==null)session.set(new MembershipSourceSession(fake,a.reader.activationIdentity(),UUID.fromString((String)request.value().get("trace")),a.a,4*1024*1024,FRAME,()->0L,0,BUDGET));
                        return CompletableFuture.completedFuture(session.get().handle(a.reader.activationIdentity(),request));
                    }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}},()->{},()->0L,0,BUDGET)) {
                pull.fetchPrefix(temp.resolve("invalid-"+UUID.randomUUID()));
                var rejected=assertThrows(IllegalArgumentException.class,pull::verifiedPrefix,fault);
                if(fault.equals("quorum"))assertEquals("both governing majorities required",rejected.getMessage());
            }finally{if(session.get()!=null)session.get().close();}
        }
    }
}
