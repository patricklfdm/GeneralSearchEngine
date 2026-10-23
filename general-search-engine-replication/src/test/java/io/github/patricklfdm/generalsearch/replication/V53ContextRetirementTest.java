package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Physical owner lifetime from original generation to exact context and a governing floor. */
class V53ContextRetirementTest {
    @TempDir static Path fixtures;
    @TempDir Path temporary;
    static V53StagedApplicationTest.Seed seed;
    static MembershipFloor.Copy peer;
    static String oldSlot;
    static final List<String> FLOOR_CUTS=List.of("FLOOR_DIRECTORY_CREATED","FLOOR_COPY_CREATED","FLOOR_COPY_DIRECTORY_FORCED",
            "FLOOR_COPIES_FORCED","FLOOR_PARENT_FORCED","FLOOR_BEFORE_RETURN");
    @BeforeAll static void actualOwners()throws Exception {
        seed=V53StagedApplicationTest.seed(fixtures.resolve("seed"),Set.of(1));var f=seed.fixture().f;
        var images=V53StagedApplicationTest.images(seed);var ballot=new TreeMap<>(V53StagedApplicationTest.nextBallot(seed));
        ballot.put("proposer","node-3");ballot.put("incarnation",V53DeclarationsTest.node(3).storageId().toString());
        var sources=new ArrayList<MembershipSelection.Source>();
        for(int n:V53StagedApplicationTest.NODES)try(var owner=f.open(n)){owner.prepareCurrent(ballot);sources.add(owner.originalSource());}
        for(int n:V53StagedApplicationTest.NODES)try(var owner=f.open(n)){owner.selectCurrent(sources,List.of());owner.installCurrent(sources,List.of(),images);}
        for(int n:V53StagedApplicationTest.NODES) {
            var resources=resources();try(var owner=open(f.node(n),n,resources,e->{})){owner.retainPendingContext();if(n==2)peer=owner.contextFloorCopy();}
            assertEquals(0,resources.usage().leases());
        }
        oldSlot=(String)MembershipPendingAccept.decode(Files.readAllBytes(f.node(1).resolve("pending.accept"))).selector().value().get("generation");
    }
    static MembershipResources resources(){return V53JournalContextTest.resources();}
    static MembershipGrantJournal open(Path node,int n,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=seed.fixture().f;
        return MembershipGrantJournal.openContextual(node,f.initial.application.f.f.f.root(),V53DeclarationsTest.node(n),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,event->{
                    V53RetirementImagesTest.bounded(resources);cut.at(event);
                });
    }
    Path copy(String name)throws Exception {Path node=temporary.resolve(name);V53JournalApplicationTest.copy(seed.fixture().f.node(1),node);return node;}
    static Map<String,String> protectedFiles(Path node)throws IOException {
        var files=new TreeMap<>(V53ReplayFilesTest.files(node));
        files.keySet().removeIf(name->name.equals("generations/"+oldSlot) || name.startsWith("generations/"+oldSlot+"/")
                || name.equals(MembershipFloorFiles.DIRECTORY) || name.startsWith(MembershipFloorFiles.DIRECTORY+"/") || name.equals("retirement") || name.startsWith("retirement/"));return files;
    }
    static void establish(MembershipGrantJournal owner)throws IOException {
        owner.establishContextFloor(List.of(owner.contextFloorCopy(),peer));
    }
    static void done(Path node,MembershipGrantJournal owner)throws IOException {
        assertFalse(Files.exists(node.resolve("generations/"+oldSlot)));assertFalse(Files.exists(node.resolve("retirement")));
        assertArrayEquals(Files.readAllBytes(node.resolve("pending.accept")),owner.retainPendingContext().vote().bytes());
        assertTrue(owner.governingFloor().isPresent());assertTrue(owner.retireContextOriginal().isEmpty());
        assertEquals(seed.phased().certificate().digest(),owner.currentCertificate().orElseThrow().digest());
    }
    @Test void exactContextReopensAfterItsOriginalGenerationRetiresWithoutLosingAnyPhase()throws Exception {
        Path evidence=Path.of("target/v53-context-retirement").resolve("run-"+UUID.randomUUID());Files.createDirectories(evidence);
        Path node=copy("complete");var before=protectedFiles(node);var resources=resources();var events=new ArrayList<String>();int[] peak={0};
        V53JournalApplicationTest.copy(node,evidence.resolve("initial"));
        V53JournalApplicationTest.copy(seed.fixture().f.node(2),evidence.resolve("peer"));
        try(var owner=open(node,1,resources,event->{events.add(event);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));})) {
            events.clear();var ballot=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));ballot.put("counter",24L);owner.observeCurrent(ballot);
            establish(owner);V53JournalApplicationTest.copy(node,evidence.resolve("floor"));
            assertTrue(owner.retireContextOriginal().isPresent());done(node,owner);V53JournalContextTest.noAck(events);
            for(var action:List.<org.junit.jupiter.api.function.Executable>of(owner::releaseFloor,owner::rotateJournal,
                    ()->owner.prepareCurrent(ballot),()->owner.acceptCurrent(seed.entry(),seed.payload()),owner::discardRedundantPendingContext))
                assertThrows(IllegalArgumentException.class,action);
        }
        assertEquals(0,resources.usage().leases());assertEquals(before,protectedFiles(node));
        V53JournalApplicationTest.copy(node,evidence.resolve("retired"));
        try(var owner=open(node,1,resources,events::add)){done(node,owner);V53JournalContextTest.noAck(events);}
        assertEquals(0,resources.usage().leases());assertEquals(before,protectedFiles(node));
        V53JournalApplicationTest.copy(node,evidence.resolve("reopened"));Files.write(evidence.resolve("events.json"),canonical(events,65536));
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-retirement-v1","status","PASS","oldSlot",oldSlot,
                "peakImages",peak[0],"freshProcesses",false,"nextCampaign",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextRetirementEvidence="+evidence.toAbsolutePath());
    }
    @Test void everyRetirementBoundaryResumesAfterASecondInterruptedContextReseal()throws Exception {
        Path floor=copy("floor-seed");var resources=resources();try(var owner=open(floor,1,resources,e->{})){establish(owner);}
        for(String point:V53RetirementTest.CUTS) {
            Path node=temporary.resolve(point);V53JournalApplicationTest.copy(floor,node);var before=protectedFiles(node);boolean[] hit={false};
            try(var owner=open(node,1,resources,event->{if(event.equals(point)){hit[0]=true;throw new IOException("retirement cut");}})) {
                assertEquals("retirement cut",assertThrows(IOException.class,owner::retireContextOriginal).getMessage());assertTrue(hit[0],point);
            }
            assertEquals(0,resources.usage().leases());assertEquals(before,protectedFiles(node));
            assertEquals("context recovery cut",assertThrows(IOException.class,()->open(node,1,resources,event->{
                if(event.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("context recovery cut");
            })).getMessage());
            assertEquals(0,resources.usage().leases());assertEquals(before,protectedFiles(node));
            try(var owner=open(node,1,resources,e->{})){owner.retireContextOriginal();done(node,owner);}
            assertEquals(0,resources.usage().leases());assertEquals(before,protectedFiles(node));
        }
    }
    @Test void partialFloorCannotAuthorizeRetirementButCanCompleteFromTheExactOfferedCopies()throws Exception {
        for(String point:FLOOR_CUTS) {
            Path node=copy(point);var before=protectedFiles(node);var resources=resources();
            try(var owner=open(node,1,resources,event->{if(event.equals(point))throw new IOException("floor cut");})) {
                assertThrows(IOException.class,()->establish(owner));
            }
            assertEquals(0,resources.usage().leases());
            try(var owner=open(node,1,resources,e->{})) {
                if(owner.governingFloor().isEmpty()) {
                    assertThrows(IllegalArgumentException.class,owner::retireContextOriginal);
                    // Admission refusal has no mutation and must not poison the owner.
                    owner.establishContextFloor(List.of(peer,copyCurrentFromSeed()));
                }
                owner.retireContextOriginal();done(node,owner);
            }
            assertEquals(0,resources.usage().leases());assertEquals(before,protectedFiles(node));
        }
    }
    static MembershipFloor.Copy copyCurrentFromSeed()throws Exception {
        var resources=resources();try(var owner=open(seed.fixture().f.node(1),1,resources,e->{})){return owner.contextFloorCopy();}
    }
    @Test void missingFloorContextSourceOrOriginalRefusesReopenWithoutRepair()throws Exception {
        Path complete=copy("retired-seed");var resources=resources();
        try(var owner=open(complete,1,resources,e->{})){establish(owner);owner.retireContextOriginal();}
        for(String change:List.of("context","floor","source","vote")) {
            Path node=temporary.resolve("missing-"+change);V53JournalApplicationTest.copy(complete,node);
            Path target=switch(change) {
                case "context"->node.resolve(MembershipPendingContextFiles.FILE);
                case "floor"->node.resolve(MembershipFloorFiles.DIRECTORY).resolve(MembershipFloorFiles.FLOOR);
                case "vote"->node.resolve("pending.accept");
                default->{var context=MembershipPendingContext.decode(Files.readAllBytes(node.resolve(MembershipPendingContextFiles.FILE)));
                    var basis=decode(V53PendingContextTest.parts(MembershipPendingContext.encode(context)).segments().get(3),"records","BASIS");
                    yield node.resolve("sources").resolve((String)basis.value().get("basisId")).resolve("source.gscp");}
            };
            assertTrue(Files.isRegularFile(target),target.toString());Files.delete(target);var before=V53ReplayFilesTest.files(node);
            var error=assertThrows(Exception.class,()->open(node,1,resources,e->{}));
            assertTrue(error instanceof IOException || error instanceof IllegalArgumentException || error instanceof ReplicationException,error.toString());
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
        }
        Path missing=copy("missing-without-floor");Path original=missing.resolve("generations/"+oldSlot);
        Files.move(original,temporary.resolve("kept-original"));var before=V53ReplayFilesTest.files(missing);
        assertEquals("retained context missing governing retirement floor",assertThrows(IllegalArgumentException.class,()->open(missing,1,resources,e->{})).getMessage());
        assertEquals(before,V53ReplayFilesTest.files(missing));assertEquals(0,resources.usage().leases());
    }
}
