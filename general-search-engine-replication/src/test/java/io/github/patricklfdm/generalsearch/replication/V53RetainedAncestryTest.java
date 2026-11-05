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

class V53RetainedAncestryTest {
    @TempDir Path temp;
    final class Local implements AutoCloseable {
        final V53CheckpointPullTest.Local l;
        final MembershipTransferService service;
        final MembershipSourcePull prefix;
        final MembershipCapsule higher;
        final List<Map<String,Object>> wire=new ArrayList<>();
        Local()throws Exception {
            var helper=new V53CheckpointPullTest();helper.temp=temp;l=helper.new Local();
            service=MembershipTransferService.prefix(l.owners.getFirst(),l.budgets.getFirst(),bounds(),()->{},l.clock::get,0,BUDGET);
            prefix=pull(link());prefix.fetchPrefix(temp.resolve("prefix-"+UUID.randomUUID()));higher=prefix.verifiedPrefix();wire.clear();
        }
        MembershipSourcePull.Link link(){return (p,r,k,d)->{
            try {assertEquals(BUDGET,d);var reply=service.handle(l.peer(2),r);wire.add(V53SelectedPullTest.wire(r,reply));return CompletableFuture.completedFuture(reply);}
            catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        };}
        MembershipSourcePull pull(MembershipSourcePull.Link link)throws Exception {
            return MembershipSourcePull.prefix(l.owners.get(2),new MembershipDiscovery.Hint(l.peer(0),l.higher.context.cut,false),l.budgets.get(2),bounds(),link,()->{},l.clock::get,0,BUDGET);
        }
        @Override public void close()throws Exception {prefix.close();service.close();l.close();}
    }
    @Test void actualTcpCopiesCompletePublishedAncestryFromOneOwnerAtEveryStableSize()throws Exception {
        var evidence=Files.createDirectories(Path.of("target/v53-retained-ancestry/run-"+UUID.randomUUID()));System.out.println("v53RetainedAncestryEvidence="+evidence.toAbsolutePath());
        var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            var raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;f.campaign(1);f.publish(1,false);MembershipCapsule.Anchor lower;
                try(var owner=f.open(f.request.targets().getFirst(),"lower")){lower=owner.floorCopyCurrent().capsule.terminal();}
                f.publish(2,true);
                var owners=new ArrayList<MembershipGrantJournal>();var budgets=new ArrayList<MembershipResources>();var endpoints=new ArrayList<MembershipActivationEndpoint>();
                var wire=new ArrayList<Map<String,Object>>();var events=new ArrayList<String>();int prefixExchanges;
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
                    try(var discovery=new MembershipDiscovery(owners.getFirst(),budgets.getFirst(),bounds(),link,()->{},System::nanoTime,started,BUDGET)){hint=discovery.query(group.identities.get(1));}
                    try(var prefix=MembershipSourcePull.prefix(owners.getFirst(),hint,budgets.getFirst(),bounds(),link,()->{},System::nanoTime,started,BUDGET)) {
                        var received=prefix.fetchPrefix(temp.resolve("received-"+UUID.randomUUID()));var higher=prefix.verifiedPrefix();assertNull(higher.anchor(1));
                        Files.createDirectory(raw.resolve("received"));Files.write(raw.resolve("received/source.gscp"),received.packet().bytes());
                        for(var image:received.images().entrySet())Files.write(raw.resolve("received").resolve(image.getKey()+".image"),image.getValue());
                        prefixExchanges=wire.size();Files.write(raw.resolve("prefix-wire.json"),canonical(wire,4*1024*1024));wire.clear();
                        try(var pull=MembershipSourcePull.prefix(owners.getFirst(),hint,budgets.getFirst(),bounds(),link,()->{},System::nanoTime,started,BUDGET)) {
                            var complete=pull.fetchAncestry(higher);complete.verifyAncestry(pull.ancestryBytes(),List.of(lower));
                            assertThrows(IllegalArgumentException.class,()->higher.verifyAncestry(pull.ancestryBytes(),List.of(lower)));
                            assertTrue(pull.ancestry().stream().allMatch(b->b.owned.isEmpty()));
                            Files.write(raw.resolve("received-manifest.gsr"),pull.ancestryManifest().bytes());Files.write(raw.resolve("received-ancestry.gsr"),pull.ancestryBytes());
                        }
                    }
                    assertTrue(events.isEmpty());assertTrue(endpoints.stream().allMatch(v->v.usage().scopeEnded()));
                }finally {for(var t:group.transports)t.close();for(var endpoint:endpoints)endpoint.close();for(var owner:owners)owner.close();for(var budget:budgets)assertEquals(0,budget.usage().leases());}
                f.snapshot("after");Files.write(raw.resolve("ancestry-wire.json"),canonical(wire,4*1024*1024));Files.write(raw.resolve("events.json"),canonical(events,65536));
                cases.add(Map.of("size",size,"prefixExchanges",prefixExchanges,"ancestryExchanges",wire.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-retained-ancestry-v1","status","PASS","cases",cases,
                "network",true,"publicRuntime",false,"adoption",false,"scope","authenticated-complete-supplemental-ancestry"),65536));
    }
    @Test void completeCopyDoesNotCreateOwnedVotesOrAuthenticateChangedWitnesses()throws Exception {
        try(var l=new Local();var pull=l.pull(l.link())) {
            var complete=pull.fetchAncestry(l.higher);var bridges=pull.ancestry();assertFalse(bridges.isEmpty());
            for(var bridge:bridges)assertTrue(bridge.owned.isEmpty());complete.verifyAncestry(pull.ancestryBytes(),List.of(l.l.lower));
            var original=bridges.stream().filter(b->b.statement.value().get("start").equals(l.l.lower.cut())).findFirst().orElseThrow();
            assertThrows(IllegalArgumentException.class,()->original.verify(l.higher,l.l.lower));
            var changed=new MembershipSelection.Bridge(original.statement,original.acknowledgements.subList(0,2),Set.of());
            assertEquals(3,original.acknowledgements.size());assertThrows(IllegalArgumentException.class,()->changed.verify(complete,l.l.lower));
            assertThrows(IllegalArgumentException.class,pull::verifiedPrefix);assertThrows(IllegalArgumentException.class,pull::verifiedOriginalSource);
            pull.close();assertThrows(IllegalArgumentException.class,pull::ancestry);assertThrows(IllegalArgumentException.class,pull::ancestryBytes);
        }
    }
    @Test void removedOldReaderCanObtainJointAndFinalAncestryWithoutContactingFormerVoters()throws Exception {
        for(int through:List.of(6,7)) {
            var f=new V53AdoptionFenceFixture(3,through);var initial=new V53CurrentGenerationFixture(3,1,true);f.owned.addAll(initial.fixture.owned);
            var bridge=new V53SelectionFixture(3,"REPLACE",7).bridge(1,5);f.owned.addAll(bridge.owned);
            var source=temp.resolve("source-"+through);initial.provision(source);var reader=temp.resolve("reader-"+through);V53FloorWorker.provision(reader,3,0,3);
            var a=resources();var b=resources();
            try(var owner=f.open(source,a,e->{});var old=MembershipGrantJournal.openGenerations(reader,f.initial.root(),V53DeclarationsTest.node(3),b,(r,p,m)->MembershipCapsule.verify(r,p,m,f.owned),e->{})) {
                owner.prepareCurrent(initial.fixture.source.ballot(20));owner.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of(bridge));
                try(var service=MembershipTransferService.prefix(owner,a,bounds(),()->{},()->0L,0,BUDGET)) {
                    var contacted=new HashSet<MembershipIdentity>();MembershipSourcePull.Link link=(p,r,k,d)->{contacted.add(p);try{return CompletableFuture.completedFuture(service.handle(old.activationIdentity(),r));}catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}};
                    var hint=new MembershipDiscovery.Hint(owner.activationIdentity(),owner.activationContext().cut,false);
                    try(var prefix=MembershipSourcePull.prefix(old,hint,b,bounds(),link,()->{},()->0L,0,BUDGET);
                        var pull=MembershipSourcePull.prefix(old,hint,b,bounds(),link,()->{},()->0L,0,BUDGET)) {
                        prefix.fetchPrefix(temp.resolve("received-old-"+through));var higher=prefix.verifiedPrefix();var result=pull.fetchAncestry(higher);
                        assertNotEquals(old.activationContext().authority(),result.context.authority());
                        var lower=new MembershipCapsule.Anchor(object(bridge.statement.value().get("start")),(String)bridge.statement.value().get("catalogBefore"),(String)bridge.statement.value().get("applicationBefore"));
                        result.verifyAncestry(pull.ancestryBytes(),List.of(lower));assertEquals(Set.of(owner.activationIdentity()),contacted);
                        assertTrue(pull.ancestry().stream().allMatch(v->v.owned.isEmpty()));
                    }
                }
            }
            assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());
        }
    }
    @Test void missingAncestryIsAnExplicitEmptyInventoryNotPermissionToSkipRequiredParents()throws Exception {
        var helper=new V53RetainedProvenanceTest();helper.temp=temp;
        try(var a=helper.new Adopted(false);var pull=MembershipSourcePull.prefix(a.reader,new MembershipDiscovery.Hint(a.source.activationIdentity(),a.copied.context.cut,false),a.b,bounds(),
                (p,r,k,d)->{try{return CompletableFuture.completedFuture(a.service.handle(a.reader.activationIdentity(),r));}catch(Exception error){return CompletableFuture.failedFuture(error);}},()->{},a.clock::get,0,BUDGET)) {
            var result=pull.fetchAncestry(a.copied);assertTrue(pull.ancestry().isEmpty());assertEquals(0,pull.ancestryBytes().length);
            var lower=new MembershipCapsule.Anchor(object(new V53SelectionFixture(3,"REPLACE",7).bridge(1,5).statement.value().get("start")),"a".repeat(64),"b".repeat(64));
            assertThrows(IllegalArgumentException.class,()->result.verifyAncestry(pull.ancestryBytes(),List.of(lower)));
        }
    }
    @Test void lostOfferDataAndCommitRetryOnlyTheirOriginalBytes()throws Exception {
        try(var l=new Local()) {
            var lost=new HashSet<String>();var duplicates=new ArrayList<String>();
            var link=l.link();try(var pull=l.pull((p,r,k,d)->link.exchange(p,r,k,d).thenCompose(reply->{duplicates.add(r.digest());
                if(lost.add(k))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null));return CompletableFuture.completedFuture(reply);}))) {
                pull.fetchAncestry(l.higher);assertFalse(pull.ancestry().isEmpty());
            }
            assertEquals(Set.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT"),lost);assertEquals(3,duplicates.size()-new HashSet<>(duplicates).size());
        }
    }
    @Test void exhaustedAndNonretryableFailuresReleaseTheReceivingBudget()throws Exception {
        try(var l=new Local()) {
            for(var reason:List.of(MembershipTransport.Reason.IO,MembershipTransport.Reason.CAPACITY,MembershipTransport.Reason.PROTOCOL)) {
                var calls=new AtomicInteger();var before=l.l.budgets.get(2).usage();
                try(var pull=l.pull((p,r,k,d)->{calls.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"failure",null));})) {
                    assertThrows(IOException.class,()->pull.fetchAncestry(l.higher));assertThrows(IllegalArgumentException.class,pull::ancestry);
                }
                assertEquals(reason==MembershipTransport.Reason.IO?3:1,calls.get());assertEquals(before,l.l.budgets.get(2).usage());
            }
        }
    }
    @Test void deadlineOrHigherFenceAfterManifestCommitCannotReturnPartialAncestry()throws Exception {
        for(boolean fence:List.of(false,true))try(var l=new Local()) {
            var original=l.l.owners.get(2).discoveryState(l.l.budgets.get(2));var link=l.link();var commits=new AtomicInteger();
            try(var pull=l.pull((p,r,k,d)->link.exchange(p,r,k,d).thenApply(reply->{if(r.kind().equals("TRANSFER_COMMIT") && commits.incrementAndGet()==1) {
                if(fence){var ballot=new TreeMap<>(original.ballot());ballot.put("counter",100L);l.l.owners.get(2).observeCurrent(ballot);}else l.l.clock.set(BUDGET);
            }return reply;}))) {assertThrows(IllegalArgumentException.class,()->pull.fetchAncestry(l.higher));assertThrows(IllegalArgumentException.class,pull::ancestry);assertEquals(1,commits.get());}
        }
    }
    @Test void cancellationReleasesPartialMetadataAndCancelsPendingExchange()throws Exception {
        try(var l=new Local()) {
            var before=l.l.budgets.get(2).usage();var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();var link=l.link();
            try(var pull=l.pull((p,r,k,d)->{if(r.kind().equals("CHUNK") && r.value().get("sequence").equals(4L)){entered.countDown();return pending;}return link.exchange(p,r,k,d);});var executor=Executors.newVirtualThreadPerTaskExecutor()) {
                var work=executor.submit(()->pull.fetchAncestry(l.higher));assertTrue(entered.await(5,TimeUnit.SECONDS));pull.close();assertThrows(ExecutionException.class,()->work.get(5,TimeUnit.SECONDS));assertTrue(pending.isCancelled());
            }
            assertEquals(before,l.l.budgets.get(2).usage());
        }
    }
    @Test void actualGenerationReplacementRevokesManifestAndAncestryBorrow()throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);var path=temp.resolve("replace");f.provision(path);var budget=resources();
        try(var owner=f.open(path,budget,e->{})) {
            var old=owner.activationContext();var ballot=owner.discoveryState(budget).ballot();String reference=MembershipPrefixExport.ancestryReference(old);
            try(var export=owner.exportPrefix(reference,ballot,old.authority(),budget,()->0L,0,BUDGET)) {
                var metadata=export.references().get(reference);assertEquals(MembershipTransfer.Kind.RECORD,metadata.kind());owner.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
                assertThrows(IllegalArgumentException.class,()->export.read(metadata.digest(),0,16));assertThrows(IllegalArgumentException.class,export::references);
            }
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void substitutedManifestsAndInvalidCompleteAncestryRejectAfterAuthenticatedDelivery()throws Exception {
        try(var l=new Local()) {
            Decoded manifest;byte[] original;
            try(var good=l.pull(l.link())){good.fetchAncestry(l.higher);manifest=good.ancestryManifest();original=good.ancestryBytes();}
            for(String fault:List.of("owner","packet","capacity","torn","duplicate","too-many","endpoint","foreign","quorum")) {
                var fields=new TreeMap<>(manifest.value());var rows=new ArrayList<Map<String,Object>>();
                for(Object row:list(fields.get("files")))rows.add(new TreeMap<>(object(row)));fields.put("files",rows);
                byte[] ancestry=original;
                if(fault.equals("owner"))fields.put("node","node-2");
                if(fault.equals("packet"))rows.stream().filter(r->r.get("path").equals("source.gscp")).findFirst().orElseThrow().put("sha256","a".repeat(64));
                if(fault.equals("torn"))ancestry=Arrays.copyOf(original,original.length-1);
                if(Set.of("duplicate","too-many").contains(fault)) {
                    var out=new ByteArrayOutputStream();for(int i=0;i<(fault.equals("duplicate")?2:7);i++)out.write(original);ancestry=out.toByteArray();
                }
                if(Set.of("endpoint","foreign","quorum").contains(fault)) {
                    var out=new ByteArrayOutputStream();var bridge=l.l.original;var statement=new TreeMap<>(bridge.statement.value());
                    if(fault.equals("endpoint"))statement.put("catalogAfter","a".repeat(64));out.write(encode("records","CHECKPOINT",statement));
                    int count=fault.equals("quorum")?1:bridge.acknowledgements.size();
                    for(int i=0;i<count;i++) {
                        var ack=new TreeMap<>(bridge.acknowledgements.get(i).value());if(fault.equals("foreign") && i==0)ack.put("voter","node-0");
                        out.write(encode("records","CHECKPOINT_ACK",ack));
                    }
                    ancestry=out.toByteArray();
                }
                var row=rows.stream().filter(r->r.get("path").equals("ancestry.gsr")).findFirst().orElseThrow();row.put("sha256",hash(ancestry));row.put("size",fault.equals("capacity")?96*1024L+1:(long)ancestry.length);
                byte[] encoded=encode("records","GENERATION",fields);var blobs=Map.of(hash(encoded),encoded,hash(ancestry),ancestry);
                var refs=new TreeMap<String,MembershipSourceExport.Content>();
                refs.put(MembershipPrefixExport.ancestryReference(l.higher.context),new MembershipSourceExport.Content(hash(encoded),encoded.length,MembershipTransfer.Kind.RECORD));
                refs.put(hash(ancestry),new MembershipSourceExport.Content(hash(ancestry),ancestry.length,MembershipTransfer.Kind.RECORD));
                var fake=new MembershipTransferExport() {
            public List<MembershipResources.Lease> closeReservations(){return List.of();}
                    public MembershipContext context(){return l.higher.context;}
                    public MembershipIdentity identity(){return l.l.peer(0);}
                    public Map<String,Object> ballot(){return Map.of();}
                    public Map<String,MembershipSourceExport.Content> references(){return refs;}
                    public void request(MembershipIdentity sender,Decoded request,UUID session){MembershipPrefixExport.envelope(context(),identity(),sender,request);}
                    public byte[] read(String digest,long offset,int maximum){var bytes=blobs.get(digest);return Arrays.copyOfRange(bytes,(int)offset,(int)Math.min(bytes.length,offset+maximum));}
                    public void close(){}
                };
                var session=new AtomicReference<MembershipSourceSession>();var before=l.l.budgets.get(2).usage();
                try(var pull=l.pull((peer,request,kind,deadline)->{try {
                    if(session.get()==null)session.set(new MembershipSourceSession(fake,l.l.peer(2),UUID.fromString((String)request.value().get("trace")),l.l.budgets.getFirst(),4*1024*1024,FRAME,()->0L,0,BUDGET));
                    return CompletableFuture.completedFuture(session.get().handle(l.l.peer(2),request));
                }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}})) {
                    var rejected=assertThrows(IllegalArgumentException.class,()->pull.fetchAncestry(l.higher),fault);
                    String reason=switch(fault){case "owner"->"ancestry manifest owner/capsule";case "packet"->"ancestry manifest exact packet";
                        case "capacity"->"ancestry offered capacity";case "torn"->"torn generation ancestry";case "duplicate"->"duplicate generation ancestry";
                        case "too-many"->"generation ancestry count";case "endpoint"->"ancestry exact frozen endpoints";case "foreign"->"ancestry ACK binding";default->"ancestry endorsement count";};
                    assertEquals(reason,rejected.getMessage(),fault);assertThrows(IllegalArgumentException.class,pull::ancestry);
                }finally{if(session.get()!=null)session.get().close();}
                assertEquals(before,l.l.budgets.get(2).usage());
            }
        }
    }
    @Test void ancestryCapabilityIsPrivateAndCannotBeMintedFromRawStatements()throws Exception {
        assertTrue(Arrays.stream(MembershipSourcePull.RetainedAncestry.class.getDeclaredConstructors()).allMatch(v->java.lang.reflect.Modifier.isPrivate(v.getModifiers())));
        var f=new V53CapsuleFixture(3,"REPLACE",7);var c=f.verify();assertThrows(NullPointerException.class,()->c.retainingAncestry(new byte[0],null));
    }
}
