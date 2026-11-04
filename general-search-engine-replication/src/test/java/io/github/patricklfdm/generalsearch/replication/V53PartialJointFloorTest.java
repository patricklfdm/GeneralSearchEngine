package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Conditional joint generations, real PROMISE storage and writer interruption.
 * Native bootstrap, TCP, process death and complete maintenance are separate gates. */
class V53PartialJointFloorTest {
    @TempDir Path temp;
    static Stream<Arguments> cuts() {
        return IntStream.rangeClosed(1,4).boxed().flatMap(n->Stream.of("FLOOR_COPY_CREATED","FLOOR_MANIFEST_FORCED",
            "FLOOR_IMAGE_FORCED","FLOOR_MEMBER_FORCED").map(cut->Arguments.of(n,cut)));
    }
    static void save(Path path,Object value)throws IOException {Files.write(path,canonical(value,16*1024*1024));}
    static void bounded(MembershipResources resources) {
        var use=resources.usage();assertTrue(use.counts().getOrDefault(MembershipResources.Unit.SOURCE,0)<=6);
        assertTrue(use.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=7);
    }
    @ParameterizedTest(name="original-{0}-{1}") @MethodSource("cuts")
    void originalWriterCutsResumeWithTwoRealPromises(int ordinal,String cut)throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-partial-joint-floor/run-"+UUID.randomUUID()));
        System.out.println("v53PartialJointFloorEvidence="+raw.toAbsolutePath());
        var fixture=new V53CurrentGenerationFixture(5,6,false);var helper=new V53FloorTest();
        var copies=new ArrayList<MembershipFloor.Copy>();var paths=new TreeMap<Integer,Path>();
        for(int node:List.of(1,2,5,6)) {
            Path path=temp.resolve("node-"+node);paths.put(node,path);copies.add(helper.copy(path,5,6,node));
        }
        var budget=resources();var proposal=MembershipFloor.create(fixture.root(),copies.getFirst(),copies);
        var initialEvents=new ArrayList<Map<String,Object>>();var resumedEvents=new ArrayList<Map<String,Object>>();
        var wire=new ArrayList<Map<String,Object>>();var writing=new AtomicBoolean();var copyNumber=new AtomicInteger();
        var success=false;
        save(raw.resolve("case.json"),Map.of("profile","5-REPLACE","ordinal",ordinal,"cut",cut,"handoff",true,
            "historicalOwnershipVerified",false,"processDeath",false,"nativeRuntime",false,"phase3Complete",false));
        try {
            try(var owner=MembershipGrantJournal.openFloors(paths.get(1),fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,event->{
                    if(!writing.get())return;bounded(budget);
                    initialEvents.add(Map.of("event",event,"usage",V53CombinedReceiveResourcesTest.usage(budget)));
                    if(event.equals("FLOOR_COPY_CREATED"))copyNumber.incrementAndGet();
                    if(copyNumber.get()==ordinal && event.equals(cut))throw new IOException("original writer cut");
                })) {
                owner.prepareCurrent(fixture.fixture.source.ballot(20));owner.prepareCurrent(fixture.fixture.source.ballot(21));
                V53JournalApplicationTest.copy(paths.get(1),raw.resolve("initial"));Files.createDirectory(raw.resolve("originals"));
                for(var entry:paths.entrySet())V53JournalApplicationTest.copy(entry.getValue(),raw.resolve("originals/node-"+entry.getKey()));
                writing.set(true);
                assertEquals("original writer cut",assertThrows(IOException.class,()->owner.establishFloor(copies,copy->{})).getMessage());
                V53JournalApplicationTest.copy(paths.get(1),raw.resolve("interrupted"));
            }
            assertEquals(0,budget.usage().leases());V53JournalApplicationTest.copy(paths.get(1),raw.resolve("after-close"));
            assertFalse(Files.exists(paths.get(1).resolve("floor-copies/floor.gsr")));
            try(var owner=MembershipGrantJournal.openFloors(paths.get(1),fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,event->{
                    bounded(budget);resumedEvents.add(Map.of("event",event,"usage",V53CombinedReceiveResourcesTest.usage(budget)));
                })) {
                V53JournalApplicationTest.copy(paths.get(1),raw.resolve("after-reopen"));
                assertEquals(V53CombinedResourceRecoveryTest.disk(raw.resolve("after-close")),V53CombinedResourceRecoveryTest.disk(raw.resolve("after-reopen")));
                assertArrayEquals(proposal.bytes(),owner.pendingFloorProposal().orElseThrow().bytes());
                int reopenedSources=budget.usage().counts().get(MembershipResources.Unit.SOURCE);
                assertEquals(2+ordinal,reopenedSources);
                if(ordinal==4) {
                    String own=copies.getFirst().generation.digest();
                    assertTrue(Files.isDirectory(paths.get(1).resolve("floor-copies/"+own)));
                    for(var copy:copies.subList(1,copies.size()))try(var borrowed=owner.borrowPendingFloorPrefix(copy.reference()).orElseThrow()) {borrowed.check();}
                }
                var fresh=new ArrayList<MembershipFloor.Copy>();fresh.add(owner.floorCopyCurrent());
                var state=owner.discoveryState(budget);var context=owner.activationContext();
                try(var images=owner.exportPrefix(MembershipContext.cutDigest(context.cut),state.ballot(),context.authority(),budget,()->0L,0,BUDGET)) {
                    for(int node:List.of(6,2,5)) {
                        var remoteBudget=resources();var expected=copies.stream().filter(c->c.owner.nodeId().value().equals("node-"+node)).findFirst().orElseThrow();
                        Path scratch=temp.resolve("receive-"+node);
                        try(var remote=MembershipGrantJournal.openGenerations(paths.get(node),fixture.root(),V53DeclarationsTest.node(node),remoteBudget,fixture::verify,event->{});
                            var service=MembershipTransferService.prefix(remote,remoteBudget,bounds(),()->{},()->0L,0,BUDGET)) {
                            var hint=new MembershipDiscovery.Hint(remote.activationIdentity(),remote.activationContext().cut,false);
                            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                                try {bounded(budget);assertEquals(BUDGET,deadline);var reply=service.handle(owner.activationIdentity(),request);
                                    wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));
                                    return CompletableFuture.completedFuture(reply);
                                }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
                            };
                            try(var prefix=MembershipSourcePull.prefix(owner,hint,budget,bounds(),link,()->{},()->0L,0,BUDGET);
                                var generation=MembershipSourcePull.prefix(owner,hint,budget,bounds(),link,()->{},()->0L,0,BUDGET)) {
                                var borrowed=owner.borrowPendingFloorPrefix(expected.reference());
                                if(borrowed.isPresent())prefix.fetchBorrowedFloorPrefix(borrowed.get());
                                else prefix.fetchBorrowedPrefix(scratch,images);
                                var copy=generation.fetchGeneration(prefix);assertEquals(expected.reference(),copy.reference());
                                owner.resumeFloorCopy(proposal,copy,()->{});bounded(budget);fresh.add(copy);
                                assertTrue(owner.governingFloor().isEmpty());assertEquals(0,service.usage().live());
                            }
                            assertFalse(Files.exists(scratch));
                        }
                        assertEquals(0,remoteBudget.usage().leases());
                    }
                }
                owner.resumeFloorCopy(proposal,fresh.getFirst(),()->{});assertTrue(owner.governingFloor().isEmpty());
                assertEquals(6,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertEquals(7,budget.usage().counts().get(MembershipResources.Unit.APPLICATION));
                owner.establishFloor(fresh,copy->{});assertArrayEquals(proposal.bytes(),owner.governingFloor().orElseThrow().bytes());
                V53JournalApplicationTest.copy(paths.get(1),raw.resolve("completed"));
                for(var copy:copies)for(var member:copy.copyFiles().entrySet())
                    assertArrayEquals(member.getValue(),Files.readAllBytes(paths.get(1).resolve("floor-copies/"+copy.generation.digest()+"/"+member.getKey())));
            }
            assertEquals(0,budget.usage().leases());V53JournalApplicationTest.copy(paths.get(1),raw.resolve("after-complete-close"));
            success=true;
        }finally {
            save(raw.resolve("initial-events.json"),initialEvents);save(raw.resolve("resumed-events.json"),resumedEvents);save(raw.resolve("wire.json"),wire);
            save(raw.resolve("receipt.json"),Map.of("schema","gse-v53-partial-joint-floor-v1","status",success?"PASS":"FAIL",
                "execution","conditional-original-writer-and-transfer-service","phase3Complete",false));
        }
    }
}
