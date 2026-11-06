package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original conditional four-voter joint copies, with two real selected installs. */
class V53PinnedFloorTest {
    @TempDir Path temp;
    final V53GenerationInstallFixture fixture=new V53GenerationInstallFixture(5,6,6,false);
    record Seed(Path path,List<MembershipFloor.Copy> peers,String oldSource) {}
    MembershipGrantJournal open(Path path,MembershipResources budget,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openCapturing(path,fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,cut);
    }
    List<MembershipSelection.Source> offers(MembershipGrantJournal owner,long counter)throws Exception {
        var result=new ArrayList<MembershipSelection.Source>();result.add(owner.originalSource());
        for(int node:List.of(2,5,6))result.add(fixture.remote(node,counter,false));return result;
    }
    List<MembershipFloor.Copy> copies(Seed seed,MembershipGrantJournal owner)throws Exception {
        var result=new ArrayList<>(seed.peers());result.add(owner.floorCopyCurrent());return result;
    }
    Seed provision(String name)throws Exception {
        Path directory=Files.createDirectory(temp.resolve(name)),path=directory.resolve("node-1");fixture.initial.provision(path);
        var peers=new ArrayList<MembershipFloor.Copy>();
        for(int node:List.of(2,5,6))peers.add(new V53FloorTest().copy(directory.resolve("node-"+node),5,6,node));
        var budget=V53SourceExchangeTest.resources();String source;
        try(var owner=open(path,budget,e->{})) {
            source=(String)owner.prepareCurrent(fixture.initial.fixture.source.ballot(20)).value().get("basisId");
            var offers=offers(owner,20);owner.selectCurrent(offers,List.of());owner.installCurrent(offers,List.of(),fixture.images());
            var floor=new ArrayList<>(peers);floor.add(owner.floorCopyCurrent());owner.establishFloor(floor);owner.retireInactive();owner.releaseFloor();
            owner.prepareCurrent(fixture.initial.fixture.source.ballot(21));offers=offers(owner,21);
            owner.selectCurrent(offers,List.of());owner.installCurrent(offers,List.of(),fixture.images());
        }
        assertEquals(0,budget.usage().leases());return new Seed(path,List.copyOf(peers),source);
    }
    void cleanup(Seed seed,MembershipGrantJournal owner)throws Exception {
        if(Files.exists(seed.path().resolve("generations/b")) || Files.exists(seed.path().resolve("retirement")))owner.retireInactive();
        if(Files.exists(seed.path().resolve("sources").resolve(seed.oldSource())))owner.retireSource(seed.oldSource());
        owner.releaseFloor();
    }
    @Test void threeVoterFloorWithThreeRetainedSourcesPinsTheOriginalAcrossReopen()throws Exception {
        var f=new V53GenerationInstallFixture(4,6,6,false);
        Path directory=Files.createDirectory(temp.resolve("three-sources")),path=directory.resolve("node-1");f.initial.provision(path);
        var peers=new ArrayList<MembershipFloor.Copy>();
        for(int node:List.of(2,3))peers.add(new V53FloorTest().copy(directory.resolve("node-"+node),4,6,node));
        var used=V53SourceExchangeTest.resources();int[] peak={0};
        MembershipBallotAllocator.Cut observe=e->{peak[0]=Math.max(peak[0],used.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));};
        Map<String,String> original;
        try(var owner=MembershipGrantJournal.openCapturing(path,f.root(),V53DeclarationsTest.node(1),used,f::verify,observe)) {
            for(long counter=20;counter<=22;counter++) {
                owner.prepareCurrent(f.initial.fixture.source.ballot(counter));var offers=f.offers(owner,counter);
                owner.selectCurrent(offers,List.of());owner.installCurrent(offers,List.of(),f.images());
                var copies=new ArrayList<>(peers);copies.add(owner.floorCopyCurrent());
                if(counter<22){owner.establishFloor(copies);owner.retireInactive();owner.releaseFloor();}
                else {
                    assertEquals(3,used.usage().counts().get(MembershipResources.Unit.SOURCE));
                    assertEquals(5,used.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    original=V53ReplayFilesTest.files(path.resolve("generations"));
                    var floor=owner.establishMaintenanceFloor(copies,null);
                    assertEquals(3,list(floor.value().get("sources")).size());
                    assertEquals(7,used.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    assertEquals(5,used.usage().counts().get(MembershipResources.Unit.SOURCE));
                    assertEquals(original,V53ReplayFilesTest.files(path.resolve("generations")));
                    assertArrayEquals(Files.readAllBytes(path.resolve("selector.gsr")),Files.readAllBytes(path.resolve("floor-copies/local.gsr")));
                    assertFalse(Files.exists(path.resolve("floor-copies").resolve(owner.floorCopyCurrent().generation.digest())));
                }
            }
        }
        assertEquals(7,peak[0]);assertEquals(0,used.usage().leases());
        try(var owner=MembershipGrantJournal.openCapturing(path,f.root(),V53DeclarationsTest.node(1),used,f::verify,observe)) {
            assertEquals(3,list(owner.governingFloor().orElseThrow().value().get("sources")).size());
            assertEquals(7,used.usage().counts().get(MembershipResources.Unit.APPLICATION));
            owner.retireInactive();owner.releaseFloor();
            assertFalse(Files.exists(path.resolve("floor-copies")));
            assertEquals(4,used.usage().counts().get(MembershipResources.Unit.APPLICATION));
            assertEquals(3,used.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        assertEquals(0,used.usage().leases());
    }
    @Test void installedFourVoterFloorReusesOnlyTheChargedCurrentOriginal()throws Exception {
        var seed=provision("complete");var used=V53SourceExchangeTest.resources();int[] peak={0,0};
        Path evidence=Path.of("target/v53-pinned-floor/run-"+UUID.randomUUID());Files.createDirectories(evidence);
        for(String node:List.of("node-1","node-2","node-5","node-6"))snapshot(seed.path().getParent().resolve(node),evidence.resolve("seed").resolve(node));
        var events=new ArrayList<Map<String,Object>>();String[] phase={"open"};
        try(var owner=open(seed.path(),used,e->{
            peak[0]=Math.max(peak[0],used.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0));
            peak[1]=Math.max(peak[1],used.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            events.add(Map.of("phase",phase[0],"event",e,"sources",used.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0),
                    "images",used.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)));
        })) {
            var original=V53ReplayFilesTest.files(seed.path().resolve("generations"));
            phase[0]="floor";
            var floor=owner.establishMaintenanceFloor(copies(seed,owner),null);
            assertEquals(4,list(floor.value().get("sources")).size());assertEquals(7,used.usage().counts().get(MembershipResources.Unit.APPLICATION));
            assertEquals(5,used.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(original,V53ReplayFilesTest.files(seed.path().resolve("generations")));
            assertArrayEquals(Files.readAllBytes(seed.path().resolve("selector.gsr")),Files.readAllBytes(seed.path().resolve("floor-copies/local.gsr")));
            assertFalse(Files.exists(seed.path().resolve("floor-copies").resolve(owner.floorCopyCurrent().generation.digest())));
            snapshot(seed.path(),evidence.resolve("pinned"));phase[0]="retire";owner.retireInactive();snapshot(seed.path(),evidence.resolve("retired"));
            phase[0]="compact";owner.retireSource(seed.oldSource());snapshot(seed.path(),evidence.resolve("compacted"));
            phase[0]="release";owner.releaseFloor();snapshot(seed.path(),evidence.resolve("released"));
            assertFalse(Files.exists(seed.path().resolve("floor-copies")));
            assertEquals(1,used.usage().counts().get(MembershipResources.Unit.SOURCE));assertEquals(2,used.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }
        assertEquals(6,peak[0]);assertEquals(7,peak[1]);assertEquals(0,used.usage().leases());
        phase[0]="cold";
        try(var owner=open(seed.path(),used,e->{if(phase[0].equals("cold"))events.add(Map.of("phase",phase[0],"event",e,"sources",used.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0),
                "images",used.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)));})) {
            snapshot(seed.path(),evidence.resolve("cold"));
            assertEquals(21L,object(owner.promised().orElseThrow().value().get("ballot")).get("counter"));
            phase[0]="next";
            owner.prepareCurrent(fixture.initial.fixture.source.ballot(22));var offers=offers(owner,22);owner.selectCurrent(offers,List.of());
            owner.installCurrent(offers,List.of(),fixture.images()); // A released pin no longer blocks the next selected generation.
        }
        Files.write(evidence.resolve("events.json"),canonical(events,1024*1024));
        System.out.println("v53PinnedFloorEvidence="+evidence.toAbsolutePath());
        assertEquals(0,used.usage().leases());
    }
    static void snapshot(Path from,Path to)throws IOException {
        try(var paths=Files.walk(from)) {for(Path path:paths.sorted().toList()) {
            Path dest=to.resolve(from.relativize(path));if(Files.isDirectory(path))Files.createDirectories(dest);else Files.copy(path,dest);
        }}
    }
    @Test void interruptedPinProposalAndCopiesResumeWithTheExactCurrentOriginal()throws Exception {
        for(String point:List.of("FLOOR_DIRECTORY_CREATED","FLOOR_LOCAL_ORIGINAL_FORCED","FLOOR_LOCAL_SELECTOR_WRITTEN",
                "FLOOR_LOCAL_SELECTOR_FORCED","FLOOR_LOCAL_PARENT_FORCED","FLOOR_PROPOSAL_FORCED","FLOOR_IMAGE_FORCED","FLOOR_PARENT_FORCED","FLOOR_BEFORE_RETURN")) {
            var seed=provision(point);var used=V53SourceExchangeTest.resources();var original=V53ReplayFilesTest.files(seed.path().resolve("generations"));
            try(var owner=open(seed.path(),used,e->{if(e.equals(point))throw new IOException(point);})) {
                assertEquals(point,assertThrows(IOException.class,()->owner.establishMaintenanceFloor(copies(seed,owner),null)).getMessage());
            }
            assertEquals(0,used.usage().leases());assertEquals(original,V53ReplayFilesTest.files(seed.path().resolve("generations")));
            try(var owner=open(seed.path(),used,e->{})){owner.establishMaintenanceFloor(copies(seed,owner),null);cleanup(seed,owner);}
            assertEquals(0,used.usage().leases());assertFalse(Files.exists(seed.path().resolve("floor-copies")));
        }
    }
    @Test void retirementAndFloorReleaseRecoverWithoutDeletingThePinnedCurrent()throws Exception {
        for(String point:List.of("RETIREMENT_PARENT_FORCED","RETIREMENT_FILE_DELETED","RETIREMENT_DIRECTORY_DELETED",
                "SOURCE_RETIREMENT_JOURNAL_PRUNED","FLOOR_RELEASE_PARENT_FORCED","FLOOR_RELEASE_RELINQUISHED",
                "FLOOR_RELEASE_FILE_DELETED","FLOOR_RELEASE_LOCAL_CLEARED","FLOOR_RELEASE_AUTHORITY_CLEARED")) {
            var seed=provision(point);var used=V53SourceExchangeTest.resources();boolean[] armed={false};Map<String,String> current;
            try(var owner=open(seed.path(),used,e->{if(armed[0] && e.equals(point))throw new IOException(point);})) {
                owner.establishMaintenanceFloor(copies(seed,owner),null);
                current=V53ReplayFilesTest.files(seed.path().resolve("generations/a"));armed[0]=true;
                assertEquals(point,assertThrows(IOException.class,()->cleanup(seed,owner)).getMessage());
            }
            assertEquals(0,used.usage().leases());assertEquals(current,V53ReplayFilesTest.files(seed.path().resolve("generations/a")));
            try(var owner=open(seed.path(),used,e->{})) {
                if(Files.exists(seed.path().resolve("floor-copies")))cleanup(seed,owner);
                assertEquals(current,V53ReplayFilesTest.files(seed.path().resolve("generations/a")));
                owner.prepareCurrent(fixture.initial.fixture.source.ballot(22));
            }
            assertEquals(0,used.usage().leases());
        }
    }
    @Test void aNewSelectedInstallCannotReplaceThePinnedGeneration()throws Exception {
        var seed=provision("pin");var used=V53SourceExchangeTest.resources();
        try(var owner=open(seed.path(),used,e->{})) {
            owner.establishMaintenanceFloor(copies(seed,owner),null);owner.retireInactive();
            owner.prepareCurrent(fixture.initial.fixture.source.ballot(22));var offers=offers(owner,22);owner.selectCurrent(offers,List.of());
            var original=V53ReplayFilesTest.files(seed.path());
            assertEquals("governing floor pins current generation until release",assertThrows(IllegalArgumentException.class,
                    ()->owner.installCurrent(offers,List.of(),fixture.images())).getMessage());
            assertEquals(original,V53ReplayFilesTest.files(seed.path()));
        }
        assertEquals(0,used.usage().leases());
    }
    @Test void aCorruptedOrMissingPinCannotTurnAThreeCopyFloorIntoAuthority()throws Exception {
        for(String mutation:List.of("missing","changed","alias")) {
            var seed=provision(mutation);var used=V53SourceExchangeTest.resources();
            try(var owner=open(seed.path(),used,e->{})){owner.establishMaintenanceFloor(copies(seed,owner),null);}
            Path pin=seed.path().resolve("floor-copies/local.gsr");
            if(mutation.equals("missing"))Files.delete(pin);
            else if(mutation.equals("changed")){byte[] bytes=Files.readAllBytes(pin);bytes[bytes.length-1]^=1;Files.write(pin,bytes);}
            else {Files.delete(pin);Files.createSymbolicLink(pin,Path.of("../selector.gsr"));}
            var original=V53ReplayFilesTest.files(seed.path().resolve("generations"));
            assertThrows(Exception.class,()->{try(var ignored=open(seed.path(),used,e->{})){fail("invalid floor accepted");}});
            assertEquals(original,V53ReplayFilesTest.files(seed.path().resolve("generations")));assertEquals(0,used.usage().leases());
        }
    }
    @Test void anExactPartialLocalMarkerCanOnlyResumeItsOriginalCurrent()throws Exception {
        for(int length:List.of(0,37)) {
            var seed=provision("partial-"+length);var used=V53SourceExchangeTest.resources();
            try(var owner=open(seed.path(),used,e->{if(e.equals("FLOOR_LOCAL_PARENT_FORCED"))throw new IOException("cut");})) {
                assertThrows(IOException.class,()->owner.establishMaintenanceFloor(copies(seed,owner),null));
            }
            Path marker=seed.path().resolve("floor-copies/local.gsr");Files.write(marker,Arrays.copyOf(Files.readAllBytes(marker),length));
            var before=V53ReplayFilesTest.files(seed.path().resolve("generations"));
            try(var owner=open(seed.path(),used,e->{})) {
                assertTrue(owner.pendingFloorProposal().isEmpty());
                assertThrows(IllegalArgumentException.class,owner::retireInactive);
                assertEquals(before,V53ReplayFilesTest.files(seed.path().resolve("generations")));
                owner.establishMaintenanceFloor(copies(seed,owner),null);cleanup(seed,owner);
            }
            assertEquals(0,used.usage().leases());
        }
    }
    @Test void pinnedHandoffDrainsOnlyForcedRemoteCopiesAndReopensAfterInterruptedDrain()throws Exception {
        for(boolean interrupted:List.of(false,true)) {
            var seed=provision("handoff-"+interrupted);var used=V53SourceExchangeTest.resources();
            var receiving=new HashMap<String,MembershipResources.Lease>();var events=new ArrayList<String>();
            var handed=new HashSet<String>();
            try(var owner=open(seed.path(),used,event->{
                events.add(event);assertTrue(used.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0)<=6);
                assertTrue(used.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=7);
                if(interrupted && event.equals("FLOOR_COPY_HANDED_OFF"))throw new IOException("handoff cut");
            })) {
                for(var peer:seed.peers())receiving.put(peer.generation.digest(),used.reserve(MembershipResources.Unit.SOURCE,"receiver:"+peer.owner.nodeId().value(),1));
                MembershipFloorFiles.Handoff drain=copy->{
                    assertNotEquals("node-1",copy.owner.nodeId().value());
                    assertEquals("FLOOR_COPY_DIRECTORY_FORCED",events.getLast());
                    assertFalse(Files.exists(seed.path().resolve("floor-copies/floor.gsr")));
                    for(var file:copy.copyFiles().entrySet())assertArrayEquals(file.getValue(),Files.readAllBytes(seed.path().resolve("floor-copies").resolve(copy.generation.digest()).resolve(file.getKey())));
                    assertTrue(handed.add(copy.owner.nodeId().value()));receiving.remove(copy.generation.digest()).close();
                };
                if(interrupted)assertEquals("handoff cut",assertThrows(IOException.class,()->owner.establishMaintenanceFloor(copies(seed,owner),drain)).getMessage());
                else {owner.establishMaintenanceFloor(copies(seed,owner),drain);assertEquals(Set.of("node-2","node-5","node-6"),handed);cleanup(seed,owner);}
            }finally{receiving.values().forEach(MembershipResources.Lease::close);}
            assertEquals(0,used.usage().leases());
            if(interrupted)try(var owner=open(seed.path(),used,e->{})) {
                assertTrue(owner.governingFloor().isEmpty());assertTrue(owner.pendingFloorProposal().isPresent());
                // Native recovery consumes exact original copies individually before publishing FLOOR.
                var proposal=owner.pendingFloorProposal().orElseThrow();
                for(var copy:copies(seed,owner))owner.resumeFloorCopy(proposal,copy,()->{});
                owner.establishMaintenanceFloor(copies(seed,owner),copy->{});cleanup(seed,owner);
            }
            assertEquals(0,used.usage().leases());
        }
    }
}
