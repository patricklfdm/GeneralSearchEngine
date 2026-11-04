package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static org.junit.jupiter.api.Assertions.*;

/** Original conditional joint copies; no native liveness or process-death claim. */
class V53DeferredGrantTest {
    @TempDir Path temp;
    final V53CurrentGenerationFixture f=new V53CurrentGenerationFixture(5,6,false);
    record Data(Path path,List<MembershipFloor.Copy> copies,List<String> sources) {}
    MembershipGrantJournal open(Path path,MembershipResources budget,MembershipBallotAllocator.Cut cut)throws IOException {
        return MembershipGrantJournal.openCapturing(path,f.root(),V53DeclarationsTest.node(1),budget,f::verify,cut);
    }
    Data provision(String name)throws Exception {
        Path root=temp.resolve(name);Files.createDirectory(root);var helper=new V53FloorTest();
        var copies=new ArrayList<MembershipFloor.Copy>();
        for(int node:List.of(1,2,5,6))copies.add(helper.copy(root.resolve("node-"+node),5,6,node));
        var budget=V53SourceExchangeTest.resources();var sources=new ArrayList<String>();Path path=root.resolve("node-1");
        try(var owner=open(path,budget,event->{})) {
            for(long ballot:List.of(20L,21L))sources.add((String)owner.prepareCurrent(f.fixture.source.ballot(ballot)).value().get("basisId"));
        }
        assertEquals(0,budget.usage().leases());return new Data(path,List.copyOf(copies),List.copyOf(sources));
    }
    void reclaim(Data data,MembershipGrantJournal owner,MembershipResources budget,MembershipGrantJournal.DeferredGrant grant)throws IOException {
        assertFalse(Thread.holdsLock(owner),"network maintenance must not hold the writer");
        grant.check();assertTrue(owner.originalBasis().isEmpty());assertTrue(owner.originalSelection().isEmpty());
        assertEquals(2,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
        assertFalse(Files.exists(data.path.resolve(MembershipCaptureFiles.FILE)));
        owner.establishFloor(data.copies);grant.check();
        assertEquals(6,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
        assertEquals(7,budget.usage().counts().get(MembershipResources.Unit.APPLICATION));
        for(String id:data.sources){owner.planSourceRetirement(id);owner.retireSource(id);grant.check();}
        owner.releaseFloor();grant.check();
        assertEquals(0,budget.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0));
    }
    @Test void fourthFloorCopyFitsBeforeTheFreshCaptureAndDuplicateDoesNotReclaim()throws Exception {
        var data=provision("complete");var budget=V53SourceExchangeTest.resources();var token=new AtomicReference<MembershipGrantJournal.DeferredGrant>();
        try(var owner=open(data.path,budget,event->{})) {
            var result=owner.prepareCurrent(f.fixture.source.ballot(30),grant->{token.set(grant);reclaim(data,owner,budget,grant);});
            assertEquals(30L,object(result.value().get("ballot")).get("counter"));
            assertEquals(1,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(2,budget.usage().counts().get(MembershipResources.Unit.APPLICATION));
            var files=V53ReplayFilesTest.files(data.path);
            assertArrayEquals(result.bytes(),owner.prepareCurrent(f.fixture.source.ballot(30),g->fail("duplicate maintenance")).bytes());
            assertEquals(files,V53ReplayFilesTest.files(data.path));
            assertThrows(IllegalArgumentException.class,token.get()::check);
        }
        assertEquals(0,budget.usage().leases());
        try(var owner=open(data.path,budget,event->{})){assertEquals(30L,object(owner.originalBasis().orElseThrow().value().get("ballot")).get("counter"));}
    }
    @Test void abandonedMaintenanceCannotInventABasisBeforeOrAfterReopen()throws Exception {
        var data=provision("abandoned");var budget=V53SourceExchangeTest.resources();
        var token=new AtomicReference<MembershipGrantJournal.DeferredGrant>();
        Map<String,String> retained;
        try(var owner=open(data.path,budget,event->{})) {
            assertEquals("unavailable",assertThrows(IOException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30),grant->{token.set(grant);grant.check();throw new IOException("unavailable");})).getMessage());
            assertThrows(IllegalArgumentException.class,token.get()::check);
            retained=V53ReplayFilesTest.files(data.path);
            assertEquals("incomplete original basis; fresh ballot required",assertThrows(IllegalArgumentException.class,
                    ()->owner.prepareCurrent(f.fixture.source.ballot(30),g->fail("abandoned grant resurrected"))).getMessage());
            assertEquals(retained,V53ReplayFilesTest.files(data.path));
        }
        assertEquals(0,budget.usage().leases());
        try(var owner=open(data.path,budget,event->{})) {
            assertTrue(owner.originalBasis().isEmpty());assertEquals(retained,V53ReplayFilesTest.files(data.path));
            assertEquals(30L,object(owner.promised().orElseThrow().value().get("ballot")).get("counter"));
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30)));
            owner.establishFloor(data.copies);for(String id:data.sources)owner.retireSource(id);owner.releaseFloor();
            assertEquals(31L,object(owner.prepareCurrent(f.fixture.source.ballot(31)).value().get("ballot")).get("counter"));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void noOpMaintenanceCannotAdmitTheThirdSource()throws Exception {
        var data=provision("noop");var budget=V53SourceExchangeTest.resources();
        try(var owner=open(data.path,budget,event->{})) {
            var sourceFiles=V53ReplayFilesTest.files(data.path.resolve("sources"));
            assertEquals("deferred grant source maintenance incomplete",assertThrows(IllegalArgumentException.class,
                    ()->owner.prepareCurrent(f.fixture.source.ballot(30),MembershipGrantJournal.DeferredGrant::check)).getMessage());
            assertTrue(owner.originalBasis().isEmpty());assertEquals(sourceFiles,V53ReplayFilesTest.files(data.path.resolve("sources")));
            assertEquals(2,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void higherObservationFencesCaptureWithoutDeletingAnyOriginal()throws Exception {
        var data=provision("fenced");var budget=V53SourceExchangeTest.resources();
        try(var owner=open(data.path,budget,event->{})) {
            var sourceFiles=V53ReplayFilesTest.files(data.path.resolve("sources"));
            assertThrows(MembershipGrantJournal.HigherBallot.class,()->owner.prepareCurrent(f.fixture.source.ballot(30),grant->{
                grant.check();owner.observeCurrent(f.fixture.source.ballot(31));
            }));
            assertTrue(owner.originalBasis().isEmpty());assertEquals(sourceFiles,V53ReplayFilesTest.files(data.path.resolve("sources")));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void interruptedForcedPromiseReopensWithoutAThirdSource()throws Exception {
        var data=provision("promise-cut");var budget=V53SourceExchangeTest.resources();
        try(var owner=open(data.path,budget,event->{if(event.equals("PROMISE_FORCED"))throw new IOException("promise cut");})) {
            assertEquals("promise cut",assertThrows(IOException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30),g->fail("unreturned promise"))).getMessage());
        }
        assertEquals(0,budget.usage().leases());
        try(var owner=open(data.path,budget,event->{})) {
            assertEquals(2,budget.usage().counts().get(MembershipResources.Unit.SOURCE));assertTrue(owner.originalBasis().isEmpty());
            assertEquals(30L,object(owner.promised().orElseThrow().value().get("ballot")).get("counter"));
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30)));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void captureIntentAfterReclamationKeepsExistingOriginalRecovery()throws Exception {
        for(String point:List.of("SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_IMAGE_PREFIX_WRITTEN","BASIS_FORCED")) {
            var data=provision(point);var budget=V53SourceExchangeTest.resources();
            try(var owner=open(data.path,budget,event->{if(event.equals(point))throw new IOException(point);})) {
                assertEquals(point,assertThrows(IOException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30),
                        grant->reclaim(data,owner,budget,grant))).getMessage());
            }
            assertEquals(0,budget.usage().leases());
            try(var owner=open(data.path,budget,event->{})) {
                var basis=owner.originalBasis().orElseThrow();assertEquals(30L,object(basis.value().get("ballot")).get("counter"));
                var files=V53ReplayFilesTest.files(data.path);
                assertArrayEquals(basis.bytes(),owner.prepareCurrent(f.fixture.source.ballot(30),g->fail("recovered grant" )).bytes());
                assertEquals(files,V53ReplayFilesTest.files(data.path));assertEquals(1,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void outgoingActivationUsesOnlyOneBallotAcrossReclamation()throws Exception {
        var data=provision("outgoing");var budget=V53SourceExchangeTest.resources();
        try(var owner=open(data.path,budget,event->{});
            var campaign=new MembershipActivation(owner,budget,System::nanoTime,System.nanoTime(),60_000_000_000L,
                    grant->reclaim(data,owner,budget,grant))) {
            assertEquals(22L,campaign.ballot().get("counter"));assertEquals(1,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(MembershipActivation.State.PREPARING,campaign.state());
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void incomingPrepareAuthenticatesBeforeReclamationAndReturnsOnlyCompletedBasis()throws Exception {
        var data=provision("incoming");var budget=V53SourceExchangeTest.resources();
        var proposer=f.admitted.context.identities.get("node-2");
        var ballot=Map.<String,Object>of("counter",30L,"proposer","node-2","incarnation",proposer.storageId().toString());
        var promise=decode(encode("records","PROMISE",Map.of("root",f.root().manifestDigest(),"view",f.admitted.context.authority(),
                "ballot",ballot,"basisId",UUID.randomUUID().toString())),"records","PROMISE");
        var request=MembershipActivation.frame("PREPARE",f.admitted.context,proposer,V53DeclarationsTest.node(1),ballot,UUID.randomUUID(),1,Map.of("promise",promise.digest()));
        try(var owner=open(data.path,budget,event->{})) {
            var before=V53ReplayFilesTest.files(data.path);
            assertThrows(IllegalArgumentException.class,()->MembershipActivation.prepare(owner,proposer,request,owner.promised().orElseThrow(),g->fail("unauthenticated maintenance")));
            assertEquals(before,V53ReplayFilesTest.files(data.path));
            var result=MembershipActivation.prepare(owner,proposer,request,promise,grant->reclaim(data,owner,budget,grant));
            assertEquals(result.source().basis.digest(),object(result.response().value().get("payload")).get("basis"));
            assertEquals(1,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void interruptedFloorAndRetirementRetainTheUnexposedPromiseUntilFreshGrant()throws Exception {
        for(String point:List.of("FLOOR_MANIFEST_FORCED","FLOOR_IMAGE_FORCED","FLOOR_BEFORE_RETURN",
                "SOURCE_RETIREMENT_FORCED","SOURCE_RETIREMENT_JOURNAL_PRUNED","SOURCE_RETIREMENT_FILE_DELETED")) {
            var data=provision("maintenance-"+point);var budget=V53SourceExchangeTest.resources();
            try(var owner=open(data.path,budget,event->{if(event.equals(point))throw new IOException(point);})) {
                assertEquals(point,assertThrows(IOException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30),
                        grant->reclaim(data,owner,budget,grant))).getMessage());
            }
            assertEquals(0,budget.usage().leases());
            try(var owner=open(data.path,budget,event->{})) {
                assertTrue(owner.originalBasis().isEmpty());
                assertEquals(30L,object(owner.promised().orElseThrow().value().get("ballot")).get("counter"));
                owner.establishFloor(data.copies);
                for(String id:data.sources)if(Files.exists(data.path.resolve("sources").resolve(id)))owner.retireSource(id);
                owner.releaseFloor();
                assertEquals("incomplete original basis; fresh ballot required",assertThrows(IllegalArgumentException.class,
                        ()->owner.prepareCurrent(f.fixture.source.ballot(30))).getMessage());
                assertEquals(31L,object(owner.prepareCurrent(f.fixture.source.ballot(31)).value().get("ballot")).get("counter"));
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void anAcceptedTailCannotEnterCleanSourceReclamation()throws Exception {
        var tail=new V53CurrentGenerationFixture(5,6,true);Path path=temp.resolve("accepted");tail.provision(path);
        var budget=V53SourceExchangeTest.resources();
        try(var owner=MembershipGrantJournal.openCapturing(path,tail.root(),V53DeclarationsTest.node(1),budget,tail::verify,event->{})) {
            for(long counter:List.of(20L,21L,22L)) {
                var basis=owner.prepareCurrent(tail.fixture.source.ballot(counter),g->fail("accepted source entered clean reclamation"));
                assertEquals(tail.accepted,basis.value().get("accepted"));
            }
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void changedAdmissionContextIsRejectedUnderTheWriterBeforePromise()throws Exception {
        var data=provision("entry-fenced");var budget=V53SourceExchangeTest.resources();
        try(var owner=open(data.path,budget,event->{})) {
            var before=V53ReplayFilesTest.files(data.path);var usage=budget.usage();
            assertEquals("entry fenced",assertThrows(IOException.class,()->owner.prepareCurrent(f.fixture.source.ballot(30),
                    grant->fail("changed context reached maintenance"),()->{
                        assertTrue(Thread.holdsLock(owner));throw new IOException("entry fenced");
                    })).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(data.path));assertEquals(usage,budget.usage());
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void waitingForTheWriterCannotAllocateAfterTheOriginalDeadline()throws Exception {
        var data=provision("waiting");var budget=V53SourceExchangeTest.resources();var clock=new AtomicLong();
        var result=new CompletableFuture<Throwable>();Thread worker;
        try(var owner=open(data.path,budget,event->{})) {
            var before=V53ReplayFilesTest.files(data.path);
            synchronized(owner) {
                worker=Thread.ofPlatform().start(()->{
                    try(var campaign=new MembershipActivation(owner,budget,clock::get,0,100,grant->fail("expired grant maintenance"))){result.complete(null);}
                    catch(Throwable error){result.complete(error);}
                });
                V53MembershipTransportTest.waitFor(()->worker.getState()==Thread.State.BLOCKED);clock.set(100);
            }
            assertEquals("original activation deadline",result.get(5,TimeUnit.SECONDS).getMessage());
            worker.join(5000);assertFalse(worker.isAlive());assertEquals(before,V53ReplayFilesTest.files(data.path));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void maintenanceDoesNotRenewTheCaptureDeadline()throws Exception {
        var data=provision("deadline");var budget=V53SourceExchangeTest.resources();var clock=new AtomicLong();
        try(var owner=open(data.path,budget,event->{})) {
            assertEquals("original activation deadline",assertThrows(IllegalArgumentException.class,()->
                    new MembershipActivation(owner,budget,clock::get,0,100,grant->{reclaim(data,owner,budget,grant);clock.set(100);})).getMessage());
            assertTrue(owner.originalBasis().isEmpty());
            assertEquals(22L,object(owner.promised().orElseThrow().value().get("ballot")).get("counter"));
            assertEquals(0,budget.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0));
        }
        assertEquals(0,budget.usage().leases());
    }
}
