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

/** Real transfer/storage mechanisms with explicitly conditional historical forces. */
class V53LearnerSourceTest {
    @TempDir Path temp;
    final class Fixture implements AutoCloseable {
        final V53CurrentGenerationFixture fixture;
        final MembershipResources server=resources(),client=resources();
        final MembershipGrantJournal owner;
        final MembershipTransferService service;
        final MembershipLearnerRequest request;
        final MembershipDiscovery.Hint hint;
        final Path path;
        final AtomicLong clock=new AtomicLong();
        final List<Decoded> sent=new ArrayList<>();
        Fixture(int size,String kind,int cut)throws Exception {
            var f=new V53CapsuleFixture(size,kind,cut);fixture=new V53CurrentGenerationFixture(size,f);
            path=temp.resolve("source-"+UUID.randomUUID());fixture.provision(path);
            owner=MembershipGrantJournal.openGenerations(path,fixture.root(),V53DeclarationsTest.node(1),server,fixture::verify,e->{});
            service=MembershipTransferService.prefix(owner,server,bounds(),()->{},clock::get,0,BUDGET);
            var original=object(list(f.state(2).get("results")).getFirst());var change=object(original.get("request"));
            var identities=list(change.get("target")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList();
            var joining=identities.stream().filter(i->i.nodeId().value().equals("node-6")).findFirst().orElseThrow();
            request=new MembershipLearnerRequest(fixture.root(),joining,new MembershipChangeRequest(new MembershipOperationId(fixture.root(),1),
                    (String)change.get("expected"),MembershipChangeKind.valueOf(kind),identities),temp.resolve("absent-replica"),temp.resolve("absent-plan"));
            hint=new MembershipDiscovery.Hint(owner.activationIdentity(),owner.activationContext().cut,false);
        }
        Fixture()throws Exception{this(3,"ADD",2);}
        CompletableFuture<Decoded> deliver(MembershipIdentity peer,Decoded frame,String kind,long deadline) {
            try {assertEquals(BUDGET,deadline);return CompletableFuture.completedFuture(service.handle(request.identity(),frame));}
            catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        }
        MembershipSourcePull pull(MembershipSourcePull.Link link) {
            return MembershipSourcePull.learner(request,fixture.fixture.source.root,hint,client,bounds(),(peer,frame,kind,deadline)->{
                sent.add(frame);return link.exchange(peer,frame,kind,deadline);
            },()->{},clock::get,0,BUDGET);
        }
        MembershipSourcePull pull(){return pull(this::deliver);}
        @Override public void close()throws Exception {service.close();owner.close();assertEquals(0,server.usage().leases());assertEquals(0,client.usage().leases());}
    }
    @Test void completeOriginalGenerationsAcrossAllFiveAddReplaceProfiles()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            for(int cut:List.of(2,3,4,5))try(var f=new Fixture(size,kind,cut);var prefix=f.pull();var generation=f.pull()) {
                var before=V53ReplayFilesTest.files(f.path);Path scratch=temp.resolve("scratch-"+UUID.randomUUID());
                var received=prefix.fetchPrefix(scratch);var checked=prefix.verifiedPrefix();
                assertEquals(f.owner.activationContext().catalog,checked.context.catalog);
                assertNull(received.packetBinding().basisId());assertThrows(IllegalArgumentException.class,prefix::verifiedOriginalSource);
                assertEquals(1,f.client.usage().counts().get(MembershipResources.Unit.LEARNER));assertFalse(f.client.usage().counts().containsKey(MembershipResources.Unit.SOURCE));
                var copy=generation.fetchGeneration(prefix);var original=f.owner.floorCopyCurrent();
                assertArrayEquals(original.generation.bytes(),copy.generation.bytes());assertEquals(original.fileNames(),copy.fileNames());
                for(String name:original.fileNames())assertArrayEquals(original.fileBytes(name),copy.fileBytes(name),name);
                assertEquals(before,V53ReplayFilesTest.files(f.path));
                assertFalse(Files.exists(f.request.replicaDirectory()));assertFalse(Files.exists(f.request.operationDirectory()));
            }
        }
    }
    @Test void noReservationJointAndTerminalSourcesCannotBeBorrowed()throws Exception {
        for(int cut:List.of(0,1,6,7,8,9))try(var f=new Fixture(3,"ADD",cut);var prefix=f.pull()) {
            assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("refused-"+cut)));
            assertEquals(1,f.sent.size());
        }
    }
    @Test void lossRetriesExactOriginalFramesAndExhaustionStopsAtThree()throws Exception {
        for(String mode:List.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT","exhausted"))try(var f=new Fixture()) {
            var dropped=new AtomicBoolean();
            try(var prefix=f.pull((peer,request,kind,deadline)-> {
                if(mode.equals("exhausted"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null));
                return f.deliver(peer,request,kind,deadline).thenCompose(reply->kind.equals(mode) && dropped.compareAndSet(false,true)?
                    CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null)):CompletableFuture.completedFuture(reply));
            })) {
                Path scratch=temp.resolve("loss-"+mode);
                if(mode.equals("exhausted")){assertThrows(IOException.class,()->prefix.fetchPrefix(scratch));assertEquals(3,f.sent.size());}
                else {prefix.fetchPrefix(scratch);prefix.verifiedPrefix();assertTrue(dropped.get());assertEquals(1,f.sent.size()-f.sent.stream().map(Decoded::digest).distinct().count());}
            }
        }
    }
    @Test void changedRootCutAndRequestNeverEstablishAdmission()throws Exception {
        try(var f=new Fixture()) {
            var other=new TreeMap<>(f.fixture.fixture.source.root.value());other.put("historyId",UUID.randomUUID().toString());
            var root=decode(encode("records","ROOT",other),"records","ROOT");
            assertThrows(IllegalArgumentException.class,()->MembershipSourcePull.learner(f.request,root,f.hint,f.client,bounds(),f::deliver,()->{},f.clock::get,0,BUDGET));
            var cut=new TreeMap<>(f.hint.cut());cut.put("index",number(cut.get("index"))+1);
            try(var prefix=MembershipSourcePull.learner(f.request,f.fixture.fixture.source.root,new MembershipDiscovery.Hint(f.hint.peer(),cut,false),f.client,bounds(),f::deliver,()->{},f.clock::get,0,BUDGET)) {
                assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("wrong-cut")));
            }
            var change=f.request.change();var wrong=new MembershipLearnerRequest(f.request.root(),f.request.identity(),
                    new MembershipChangeRequest(new MembershipOperationId(f.request.root(),2),change.expectedConfigurationDigest(),change.kind(),change.target()),f.request.replicaDirectory(),f.request.operationDirectory());
            try(var prefix=MembershipSourcePull.learner(wrong,f.fixture.fixture.source.root,f.hint,f.client,bounds(),f::deliver,()->{},f.clock::get,0,BUDGET)) {
                assertThrows(IllegalArgumentException.class,()->prefix.fetchPrefix(temp.resolve("wrong-operation")));
            }
        }
    }
    @Test void onlyOneLearnerScratchAndOriginalLifetimeArePermitted()throws Exception {
        try(var f=new Fixture();var first=f.pull();var second=f.pull();var generation=f.pull()) {
            first.fetchPrefix(temp.resolve("one"));
            assertThrows(IllegalArgumentException.class,()->second.fetchPrefix(temp.resolve("two")));
            assertEquals(1,f.client.usage().counts().get(MembershipResources.Unit.LEARNER));assertFalse(Files.exists(temp.resolve("two")));
            first.close();assertThrows(IllegalArgumentException.class,()->generation.fetchGeneration(first));
        }
    }
    @Test void closeDuringSubmissionCancelsWithoutWaitingForDeadline()throws Exception {
        try(var f=new Fixture()) {
            var holder=new AtomicReference<MembershipSourcePull>();var pending=new CompletableFuture<Decoded>();
            try(var prefix=f.pull((p,r,k,d)->{try{holder.get().close();}catch(IOException error){throw new UncheckedIOException(error);}return pending;})) {
                holder.set(prefix);assertThrows(IOException.class,()->prefix.fetchPrefix(temp.resolve("cancelled")));assertTrue(pending.isCancelled());assertEquals(1,f.sent.size());
            }
        }
    }
    @Test void permanentTransportFailureNeverRetries()throws Exception {
        for(var reason:List.of(MembershipTransport.Reason.PROTOCOL,MembershipTransport.Reason.CAPACITY,MembershipTransport.Reason.CLOSED))try(var f=new Fixture();
            var prefix=f.pull((p,r,k,d)->CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"permanent",null)))) {
            assertThrows(IOException.class,()->prefix.fetchPrefix(temp.resolve(reason.name())));assertEquals(1,f.sent.size());
        }
    }
    @Test void refusedScratchCleanupStillReleasesEveryLaterOwner()throws Exception {
        for(boolean checked:List.of(false,true)) {
            var resources=resources();var held=resources.reserve(MembershipResources.Unit.CONTROL,"close-check",4096);
            var primary=checked?new IOException("original cleanup refused"):new IllegalArgumentException("original cleanup refused");
            var secondary=new IOException("second cleanup refused");var last=new AtomicBoolean();
            var actual=assertThrows(Exception.class,()->MembershipLearnerSource.closeChildren(
                    ()->{throw primary;},null,()->{throw secondary;},held,()->last.set(true)));
            assertSame(primary,actual);assertArrayEquals(new Throwable[]{secondary},actual.getSuppressed());
            assertTrue(last.get());assertEquals(0,resources.usage().leases());
        }
    }

}
