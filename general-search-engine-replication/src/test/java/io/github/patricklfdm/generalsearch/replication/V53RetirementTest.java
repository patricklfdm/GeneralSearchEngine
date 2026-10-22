package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53RetirementTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("RETIREMENT_OLD_FILES_FORCED","RETIREMENT_RESERVED","RETIREMENT_CREATED","RETIREMENT_PROPOSAL_WRITTEN",
            "RETIREMENT_PROPOSAL_FORCED","RETIREMENT_SOURCE_CREATED","RETIREMENT_MANIFEST_WRITTEN","RETIREMENT_MANIFEST_FORCED",
            "RETIREMENT_IMAGE_WRITTEN","RETIREMENT_IMAGE_FORCED","RETIREMENT_MEMBER_WRITTEN","RETIREMENT_MEMBER_FORCED",
            "RETIREMENT_SOURCE_FORCED","RETIREMENT_AUTHORITY_WRITTEN","RETIREMENT_AUTHORITY_FORCED","RETIREMENT_PARENT_FORCED",
            "RETIREMENT_DELETE_VALIDATED","RETIREMENT_FILE_DELETED","RETIREMENT_DIRECTORY_DELETED",
            "RETIREMENT_SAVED_FILE_DELETED","RETIREMENT_SAVED_DIRECTORY_DELETED","RETIREMENT_PROPOSAL_CLEARED",
            "RETIREMENT_AUTHORITY_CLEARED","RETIREMENT_CLEARED","RETIREMENT_BEFORE_RETURN");
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    V53AdoptionFenceFixture fixture(){return new V53AdoptionFenceFixture(3,6);}
    MembershipGrantJournal open(Path path,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=fixture();return MembershipGrantJournal.openRetirement(path,f.initial.root(),V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.owned),cut);
    }
    void provision(Path path)throws Exception {
        var f=fixture();f.initial.provision(path);var peer=new V53FloorTest().copy(temp.resolve(path.getFileName()+"-peer"),3,0,2);
        try(var store=open(path,resources(),e->{})){store.establishFloor(List.of(store.floorCopyCurrent(),peer));store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());}
    }
    Map<String,byte[]> protectedFiles(Path path)throws Exception {
        var result=new TreeMap<String,byte[]>();
        try(var all=Files.walk(path)){for(Path p:all.filter(Files::isRegularFile).toList()) {
            String name=path.relativize(p).toString();if(!name.startsWith("generations/a/") && !name.startsWith("retirement/"))result.put(name,Files.readAllBytes(p));
        }}return result;
    }
    void unchanged(Map<String,byte[]> expected,Path path)throws Exception {
        var actual=protectedFiles(path);assertEquals(expected.keySet(),actual.keySet());for(String name:expected.keySet())assertArrayEquals(expected.get(name),actual.get(name),name);
    }
    @Test void retirementRetainsFloorCurrentPromiseAndSourcesAndFreesOnlyInactiveSlot()throws Exception {
        Path path=temp.resolve("complete");provision(path);var protectedFiles=protectedFiles(path);var resources=resources();
        try(var store=open(path,resources,e->{})) {
            assertTrue(store.retireInactive().isPresent());assertFalse(store.retireInactive().isPresent());
            assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.GENERATION));assertEquals(2,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        assertEquals(0,resources.usage().leases());assertFalse(Files.exists(path.resolve("retirement")));assertFalse(Files.exists(path.resolve("generations/a")));unchanged(protectedFiles,path);
        var finalView=new V53AdoptionFenceFixture(3,7);var initial=fixture();finalView.owned.addAll(initial.owned);
        try(var store=MembershipGrantJournal.openRetirement(path,initial.initial.root(),V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,finalView.owned),e->{})) {
            assertEquals("a",store.adoptCurrent(finalView.remote.packet(),finalView.remote.source.images,List.of()).value().get("generation"));
            assertThrows(IllegalArgumentException.class,store::retireInactive); // old floor cannot cover joint index 6
        }
        assertTrue(Files.exists(path.resolve("generations/b/generation.gsr")));assertEquals(0,resources.usage().leases());
    }
    @Test void everyInterruptedBoundaryResumesWithAllProtectedAuthorityUnchanged()throws Exception {
        for(String point:CUTS) {
            Path path=temp.resolve(point);provision(path);var protectedFiles=protectedFiles(path);var resources=resources();
            try(var store=open(path,resources,e->{if(e.equals(point))throw new java.io.IOException("cut "+point);})) {assertThrows(java.io.IOException.class,store::retireInactive,point);}
            assertEquals(0,resources.usage().leases(),point);unchanged(protectedFiles,path);
            try(var store=open(path,resources,e->{})){store.retireInactive();assertFalse(store.retireInactive().isPresent());}
            unchanged(protectedFiles,path);assertFalse(Files.exists(path.resolve("generations/a")),point);assertFalse(Files.exists(path.resolve("retirement")),point);assertEquals(0,resources.usage().leases(),point);
        }
    }
    @Test void recoveryInterruptedAgainAtAuthorityResealRetainsOriginalDeletionDecision()throws Exception {
        Path path=temp.resolve("repeat");provision(path);var protectedFiles=protectedFiles(path);
        try(var store=open(path,resources(),e->{if(e.equals("RETIREMENT_FILE_DELETED"))throw new java.io.IOException("first");})) {assertThrows(java.io.IOException.class,store::retireInactive);}
        byte[] original=Files.readAllBytes(path.resolve("retirement/retirement.gsr"));
        for(int attempt=0;attempt<2;attempt++) {
            try(var store=open(path,resources(),e->{if(e.equals("RETIREMENT_AUTHORITY_RESEALED"))throw new java.io.IOException("again");})) {assertThrows(java.io.IOException.class,store::retireInactive);}
            assertArrayEquals(original,Files.readAllBytes(path.resolve("retirement/retirement.gsr")));unchanged(protectedFiles,path);
        }
        try(var store=open(path,resources(),e->{})){store.retireInactive();}unchanged(protectedFiles,path);
    }
    @Test void changedRemainingOrSavedBytesCannotResumeDeletion()throws Exception {
        for(String location:List.of("generations/a","retirement/source")) {
            Path path=temp.resolve(location.startsWith("generations")?"old":"saved");provision(path);
            try(var store=open(path,resources(),e->{if(e.equals("RETIREMENT_PARENT_FORCED"))throw new java.io.IOException("cut");})) {assertThrows(java.io.IOException.class,store::retireInactive);}
            Path file=path.resolve(location).resolve("promise.gsr");byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);
            var resources=resources();try(var store=open(path,resources,e->{})){assertThrows(Exception.class,store::retireInactive);}
            assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void pendingRetirementBlocksAnotherGrantEvenAfterOldDirectoryWasRemoved()throws Exception {
        Path path=temp.resolve("pending");provision(path);
        try(var store=open(path,resources(),e->{if(e.equals("RETIREMENT_DIRECTORY_DELETED"))throw new java.io.IOException("cut");})) {assertThrows(java.io.IOException.class,store::retireInactive);}
        try(var store=open(path,resources(),e->{})) {
            assertEquals("pending retirement must finish before authority changes",assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(fixture().initial.fixture.source.ballot(100))).getMessage());
            store.retireInactive();assertNotNull(store.prepareCurrent(fixture().initial.fixture.source.ballot(100)));
        }
    }
    @Test void sharedCapacityFailureDoesNotStartRetirementOrDeleteOriginal()throws Exception {
        Path path=temp.resolve("capacity");provision(path);var resources=resources();var external=new ArrayList<MembershipResources.Lease>();
        try(var store=open(path,resources,e->{})) {
            for(int i=0;i<4;i++)external.add(resources.reserve(MembershipResources.Unit.SOURCE,"busy-"+i,1));
            assertThrows(IllegalArgumentException.class,store::retireInactive);assertFalse(Files.exists(path.resolve("retirement")));assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
        }finally{external.forEach(MembershipResources.Lease::close);}
        assertEquals(0,resources.usage().leases());
    }
    @Test void aPendingSelectedInstallCannotBeRetiredInsteadOfCompleted()throws Exception {
        Path path=temp.resolve("selected-pending");var f=new V53GenerationInstallFixture(3,0,1,false);f.provision(path);
        try(var store=MembershipGrantJournal.openRetirement(path,f.root(),V53DeclarationsTest.node(1),resources(),f::verify,e->{if(e.equals("INSTALL_GENERATION_FORCED"))throw new java.io.IOException("cut");})) {
            var peer=new V53FloorTest().copy(temp.resolve("peer"),3,0,2);store.establishFloor(List.of(store.floorCopyCurrent(),peer));
            assertThrows(java.io.IOException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
        }
        try(var store=MembershipGrantJournal.openRetirement(path,f.root(),V53DeclarationsTest.node(1),resources(),f::verify,e->{})) {assertThrows(IllegalArgumentException.class,store::retireInactive);}
        assertTrue(Files.exists(path.resolve("generations/b/generation.gsr")));
    }
    @Test void anOlderSelectedGenerationDoesNotBlockAdoptionMaintenanceOrFreshGrants()throws Exception {
        Path path=temp.resolve("older-selected");var f=fixture();f.initial.provision(path);
        var peer=new V53FloorTest().copy(temp.resolve("peer"),3,0,2);
        try(var store=open(path,resources(),e->{})) {
            store.establishFloor(List.of(store.floorCopyCurrent(),peer));store.prepareCurrent(f.initial.fixture.source.ballot(100));
            var selection=new V53SelectionFixture(3,"REPLACE",0);var offers=List.of(store.originalSource(),selection.source("node-2",100,null,0));
            store.selectCurrent(offers,List.of());store.installCurrent(offers,List.of(),f.initial.fixture.source.images);store.retireInactive();
            store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
            assertNotNull(store.floorCopyCurrent());
            assertEquals(100L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));
            assertNotNull(store.prepareCurrent(f.initial.fixture.source.ballot(101)));assertTrue(store.retireInactive().isPresent());
        }
        try(var store=open(path,resources(),e->{})){assertFalse(store.retireInactive().isPresent());assertNotNull(store.floorCopyCurrent());}
    }
    @Test void aboveFloorOwnedTailRequiresItsExactActiveCopy()throws Exception {
        for(boolean preserve:List.of(false,true)) {
            Path path=temp.resolve("tail-"+preserve);var initial=new V53CurrentGenerationFixture(3,0,true);initial.provision(path);
            var fixture=new V53GenerationInstallFixture(3,0,preserve?0:1,true);var peer=new V53FloorTest().copy(temp.resolve("peer-"+preserve),3,0,2);
            try(var store=MembershipGrantJournal.openRetirement(path,initial.root(),V53DeclarationsTest.node(1),resources(),fixture::verify,e->{})) {
                store.establishFloor(List.of(store.floorCopyCurrent(),peer));store.prepareCurrent(initial.fixture.source.ballot(20));
                var offers=List.of(store.originalSource(),fixture.remote(2,20,false));store.selectCurrent(offers,List.of());
                store.installCurrent(offers,List.of(),fixture.images());byte[] tail=Files.readAllBytes(path.resolve("generations/a/owned-tail.gsr"));
                if(preserve) {
                    assertTrue(store.retireInactive().isPresent());assertArrayEquals(tail,Files.readAllBytes(path.resolve("generations/b/owned-tail.gsr")));
                    assertFalse(Files.exists(path.resolve("generations/a")));
                }else {
                    assertThrows(IllegalArgumentException.class,store::retireInactive);assertArrayEquals(tail,Files.readAllBytes(path.resolve("generations/a/owned-tail.gsr")));
                    assertFalse(Files.exists(path.resolve("retirement")));
                }
            }
        }
    }

    @Test void liveInodeOrSelectorReplacementCannotAuthorizeFurtherDeletion()throws Exception {
        for(String changed:List.of("retirement/source/generation.gsr","selector.gsr")) {
            Path path=temp.resolve(changed.startsWith("selector")?"selector-change":"copy-change");provision(path);var resources=resources();
            try(var store=open(path,resources,e->{if(e.equals("RETIREMENT_DELETE_VALIDATED")) {
                Path file=path.resolve(changed),replacement=temp.resolve("replacement");Files.write(replacement,Files.readAllBytes(file));Files.move(replacement,file,StandardCopyOption.REPLACE_EXISTING);
            }})) {assertThrows(IllegalArgumentException.class,store::retireInactive);}
            assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void aMissingSavedOriginalWhileDeletionIsIncompleteFailsClosed()throws Exception {
        Path path=temp.resolve("missing-saved");provision(path);
        try(var store=open(path,resources(),e->{if(e.equals("RETIREMENT_FILE_DELETED"))throw new java.io.IOException("cut");})) {assertThrows(java.io.IOException.class,store::retireInactive);}
        Files.delete(path.resolve("retirement/source/generation.gsr"));
        try(var store=open(path,resources(),e->{})){assertThrows(IllegalArgumentException.class,store::retireInactive);}
        assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
    }

}
