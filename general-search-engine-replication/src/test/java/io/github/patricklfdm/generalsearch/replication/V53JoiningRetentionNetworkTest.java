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
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Actual disk exports and framed exchange over conditional certified fixtures.
 * This never authorizes native joining initialization or claims process history. */
class V53JoiningRetentionNetworkTest {
    @TempDir Path temp;
    static void identity(Path path,MembershipIdentity identity)throws Exception {
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT").rootDigest();
        Files.write(path.resolve("node.gsr"),encode("records","NODE",Map.of("identity",MembershipBootstrapSeed.identity(identity),"root",root)));
        Files.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",Map.of("counter",0L,"node",identity.nodeId().value(),"root",root)));
        var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value());manifest.put("node",identity.nodeId().value());
        byte[] raw=encode("records","GENERATION",manifest);Files.write(path.resolve("generations/a/generation.gsr"),raw);
        Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",root,"node",identity.nodeId().value(),"generation","a","digest",hash(raw))));
    }
    final class Local implements AutoCloseable {
        final V53JoiningRetentionSeedTest.Input in=V53JoiningRetentionSeedTest.input(3,"ADD");
        final V53CurrentGenerationFixture fixture=new V53CurrentGenerationFixture(3,in.fixture());
        final MembershipResources a=resources(),b=resources();final AtomicLong clock=new AtomicLong();
        final MembershipGrantJournal source,reader;final MembershipTransferService service;final Path path;
        Local()throws Exception {
            Path base=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));path=base.resolve("source");fixture.provision(path);
            var original=in.sources().getFirst();var promise=MembershipPeerRetentionSource.read(original).promise();
            var out=new ByteArrayOutputStream();out.writeBytes(Files.readAllBytes(path.resolve("grants.gsr")));out.writeBytes(promise.bytes());out.writeBytes(original.basis.bytes());Files.write(path.resolve("grants.gsr"),out.toByteArray());
            Path captured=Files.createDirectory(path.resolve("sources").resolve((String)promise.value().get("basisId")));
            Files.write(captured.resolve("source.gscp"),original.capsule.packet.bytes());in.fixture().source.images.forEach((digest,bytes)->{try{Files.write(captured.resolve(digest+".image"),bytes);}catch(IOException e){throw new UncheckedIOException(e);}});
            Path client=base.resolve("reader");fixture.provision(client);identity(client,in.joining());
            source=MembershipGrantJournal.openGenerations(path,fixture.root(),original.owner,a,fixture::verify,e->{});
            reader=MembershipGrantJournal.openGenerations(client,fixture.root(),in.joining(),b,fixture::verify,e->{});
            service=MembershipTransferService.prefix(source,a,bounds(),()->{},clock::get,0,BUDGET);
        }
        MembershipSourcePull pull(MembershipSourcePull.Link link)throws Exception {
            return MembershipSourcePull.prefix(reader,new MembershipDiscovery.Hint(source.activationIdentity(),source.activationContext().cut,false),b,bounds(),link,()->{},clock::get,0,BUDGET);
        }
        CompletableFuture<Decoded> deliver(MembershipIdentity peer,Decoded q,String kind,long deadline) {
            try{assertEquals(source.activationIdentity(),peer);assertEquals(BUDGET,deadline);return CompletableFuture.completedFuture(service.handle(reader.activationIdentity(),q));}
            catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        }
        String reference()throws Exception{return MembershipJoiningRetentionExport.reference(reader.activationContext(),reader.activationIdentity());}
        @Override public void close()throws Exception{service.close();source.close();reader.close();assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());}
    }
    @Test void originalFrozenFragmentAndLostRepliesKeepExactRequestsAndReleaseExport()throws Exception {
        for(String drop:List.of("none","SOURCE_OFFER","CHUNK","TRANSFER_COMMIT"))try(var l=new Local()) {
            var files=V53ReplayFilesTest.files(l.path);var usage=l.b.usage();var lost=new AtomicBoolean();var sent=new ArrayList<String>();
            try(var pull=l.pull((peer,q,kind,deadline)->{sent.add(q.digest());return l.deliver(peer,q,kind,deadline).thenCompose(reply->{
                if(kind.equals(drop) && lost.compareAndSet(false,true))return CompletableFuture.failedFuture(lost());return CompletableFuture.completedFuture(reply);
            });})) {
                byte[] fragment=pull.fetchPrefixMetadata(l.reference(),MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM);
                assertArrayEquals(MembershipJoiningRetentionSeed.fragment(l.source.originalSource()),fragment);assertEquals(0,l.service.usage().live());
                var assembled=MembershipJoiningRetentionSeed.assemble(l.in.current(),l.in.ancestry(),l.in.joining(),List.of(fragment,MembershipJoiningRetentionSeed.fragment(l.in.sources().get(1))));
                assertArrayEquals(MembershipJoiningRetentionSeed.capture(l.in.current(),l.in.ancestry(),l.in.joining(),l.in.sources()).bytes(),assembled.bytes());
                assertEquals(drop.equals("none")?0:1,sent.size()-new HashSet<>(sent).size());
            }
            assertEquals(usage,l.b.usage());assertEquals(files,V53ReplayFilesTest.files(l.path));
        }
    }
    @Test void higherFenceRevokesOpenExportAndWrongReaderNeverBorrowsIt()throws Exception {
        try(var l=new Local()) {
            var local=l.reader.activationIdentity();var context=l.reader.activationContext();
            var q=decode(encode("wire","CHUNK",Map.of("root",context.root,"view",context.authority(),"sender",MembershipBootstrapSeed.identity(local),
                    "recipient",MembershipBootstrapSeed.identity(l.source.activationIdentity()),"ballot",l.reader.discoveryState(l.b).ballot(),"trace",UUID.randomUUID().toString(),
                    "sequence",1L,"payload",Map.of("action","REQUEST","id",UUID.randomUUID().toString(),"offset",0L,"digest",l.reference(),"bytes",""))),"wire","CHUNK");
            var before=l.a.usage();
            try(var export=new MembershipJoiningRetentionExport(l.source,local,q,l.a,l.clock::get,0,BUDGET)) {
                var content=export.references().get(l.reference());l.source.observeCurrent(l.in.fixture().source.ballot(21));
                assertThrows(IllegalArgumentException.class,()->export.read(content.digest(),0,4096));
            }
            assertEquals(before,l.a.usage());assertFalse(MembershipJoiningRetentionExport.reference(context,V53DeclarationsTest.node(2),l.reference()));
        }
    }
    @Test void metadataCapacityCorruptionAndOriginalDeadlineRefuseWithoutAuthority()throws Exception {
        for(String fault:List.of("capacity","digest","deadline"))try(var l=new Local()) {
            var changed=new AtomicBoolean();var usage=l.b.usage();
            try(var pull=l.pull((peer,q,kind,deadline)->l.deliver(peer,q,kind,deadline).thenApply(reply->{
                if(kind.equals("SOURCE_OFFER") && changed.compareAndSet(false,true)) {
                    if(fault.equals("deadline")){l.clock.set(BUDGET);return reply;}
                    var fields=new TreeMap<>(reply.value());var p=new TreeMap<>(object(fields.get("payload")));
                    if(fault.equals("capacity"))p.put("bytes",(long)MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM+1);else p.put("digest","ab".repeat(32));fields.put("payload",p);
                    return decode(encode("wire",reply.kind(),fields),"wire",reply.kind());
                }return reply;
            }))) {
                assertThrows(Exception.class,()->pull.fetchPrefixMetadata(l.reference(),MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM));
            }
            assertTrue(changed.get());assertEquals(usage,l.b.usage());
        }
    }
    @Test void conditionalOrOrdinaryOwnersCannotAcquireAnInitializationCapability()throws Exception {
        try(var l=new Local()) {
            var files=V53ReplayFilesTest.files(l.path);
            assertThrows(IllegalArgumentException.class,()->new MembershipJoiningRetentionAcquisition(l.source,l.a,bounds(),
                    (p,q,k,d)->{throw new AssertionError("no network before original joined-owner admission");},()->{},l.clock::get,0,BUDGET));
            assertEquals(files,V53ReplayFilesTest.files(l.path));
        }
    }
    @Test void closingMetadataPullCancelsItsPendingRequestAndReleasesCharges()throws Exception {
        try(var l=new Local()) {
            var before=l.b.usage();var entered=new CountDownLatch(1);var future=new CompletableFuture<Decoded>();
            try(var pull=l.pull((p,q,k,d)->{entered.countDown();return future;});var executor=Executors.newVirtualThreadPerTaskExecutor()) {
                String reference=l.reference();var task=executor.submit(()->pull.fetchPrefixMetadata(reference,MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM));
                assertTrue(entered.await(5,TimeUnit.SECONDS));pull.close();assertThrows(ExecutionException.class,()->task.get(5,TimeUnit.SECONDS));assertTrue(future.isCancelled());
            }
            assertEquals(before,l.b.usage());
        }
    }
}
