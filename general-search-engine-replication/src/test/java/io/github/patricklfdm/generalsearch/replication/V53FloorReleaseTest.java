package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53FloorReleaseTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("FLOOR_RELEASE_AUTHORITY_CREATED","FLOOR_RELEASE_AUTHORITY_WRITTEN","FLOOR_RELEASE_AUTHORITY_FORCED","FLOOR_RELEASE_PARENT_FORCED",
            "FLOOR_RELEASE_RELINQUISHED","FLOOR_RELEASE_FILE_DELETED","FLOOR_RELEASE_COPY_DELETED","FLOOR_RELEASE_PROPOSAL_CLEARED",
            "FLOOR_RELEASE_AUTHORITY_CLEARED","FLOOR_RELEASE_CLEARED","FLOOR_RELEASE_BEFORE_RETURN");
    final V53CurrentGenerationFixture fixture=new V53CurrentGenerationFixture(3,7,false);
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openMaintenance(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,cut);
    }
    void provision(Path path)throws Exception {
        Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,7);
        try(var store=open(path,resources(),e->{})){store.retireInactive();}
    }
    Map<String,byte[]> protectedFiles(Path path)throws Exception {
        var files=new TreeMap<String,byte[]>();try(var all=Files.walk(path)){for(Path file:all.filter(Files::isRegularFile).toList()) {
            String name=path.relativize(file).toString();if(!name.startsWith("floor-copies/"))files.put(name,Files.readAllBytes(file));
        }}return files;
    }
    void unchanged(Map<String,byte[]> before,Path path)throws Exception {
        var after=protectedFiles(path);assertEquals(before.keySet(),after.keySet());for(String name:before.keySet())assertArrayEquals(before.get(name),after.get(name),name);
    }
    @Test void releaseReclaimsOnlyFloorReservationsAndAllowsAnotherCompleteFloor()throws Exception {
        Path path=temp.resolve("repeat/authority");provision(path);var files=protectedFiles(path);var resources=resources();
        try(var store=open(path,resources,e->{})) {
            assertEquals(3,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(4,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            var peer=new V53FloorTest().copy(temp.resolve("peer"),3,7,2);
            for(int i=0;i<3;i++) {
                store.releaseFloor();assertTrue(store.governingFloor().isEmpty());assertFalse(Files.exists(path.resolve("floor-copies")));
                assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertEquals(2,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                store.establishFloor(List.of(store.floorCopyCurrent(),peer));assertTrue(store.governingFloor().isPresent());
            }
            store.releaseFloor();
        }
        unchanged(files,path);assertEquals(0,resources.usage().leases());
        try(var store=open(path,resources,e->{})){assertTrue(store.governingFloor().isEmpty());store.releaseFloor();}
    }
    @Test void everyReleaseBoundaryReopensAndPreservesCurrentAndOriginalSources()throws Exception {
        for(String cut:CUTS) {
            Path path=temp.resolve(cut+"/authority");provision(path);var files=protectedFiles(path);var resources=resources();
            try(var store=open(path,resources,e->{if(e.equals(cut))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::releaseFloor);}
            assertEquals(0,resources.usage().leases());
            try(var store=open(path,resources,e->{})){store.releaseFloor();assertTrue(store.governingFloor().isEmpty());}
            unchanged(files,path);assertFalse(Files.exists(path.resolve("floor-copies")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void releaseNeedsNoAdditionalSourceOrImageSlotAtSharedCapacity()throws Exception {
        Path path=temp.resolve("full/authority");provision(path);var resources=resources();var external=new ArrayList<MembershipResources.Lease>();
        for(int i=0;i<3;i++) {
            external.add(resources.reserve(MembershipResources.Unit.SOURCE,"elsewhere-"+i,1));
            external.add(resources.reserve(MembershipResources.Unit.APPLICATION,"elsewhere-"+i,1));
        }
        try(var store=open(path,resources,e->{})) {
            assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(7,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            store.releaseFloor();assertEquals(4,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(5,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }
        assertEquals(6,resources.usage().leases());external.forEach(MembershipResources.Lease::close);assertEquals(0,resources.usage().leases());
    }
    @Test void pendingReleaseCannotAdvertiseFloorOrAdmitAnotherMutation()throws Exception {
        Path path=temp.resolve("blocked/authority");provision(path);MembershipGrantJournal[] owner={null};boolean[] checked={false};
        try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_AUTHORITY_FORCED")) {
            var active=owner[0];assertTrue(active.governingFloor().isEmpty());
            assertEquals("pending floor release must finish before authority changes",assertThrows(IllegalArgumentException.class,
                    ()->active.prepareCurrent(fixture.fixture.source.ballot(101))).getMessage());
            assertThrows(IllegalArgumentException.class,active::floorCopyCurrent);
            assertThrows(IllegalArgumentException.class,active::retireInactive);
            assertThrows(IllegalArgumentException.class,active::rotateJournal);checked[0]=true;
        }})){owner[0]=store;store.releaseFloor();}
        assertTrue(checked[0]);assertFalse(Files.exists(path.resolve("floor-copies")));
    }
    @Test void recoveryCanBeInterruptedAgainAfterDeletionHasBegun()throws Exception {
        Path path=temp.resolve("recovery/authority");provision(path);var files=protectedFiles(path);
        try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_FILE_DELETED"))throw new java.io.IOException("first");})){assertThrows(java.io.IOException.class,store::releaseFloor);}
        assertFalse(Files.exists(path.resolve("floor-copies/floor.gsr")));
        var resources=resources();assertThrows(java.io.IOException.class,()->open(path,resources,e->{if(e.equals("FLOOR_RELEASE_AUTHORITY_FORCED"))throw new java.io.IOException("again");}));
        assertEquals(0,resources.usage().leases());
        try(var store=open(path,resources,e->{})){store.releaseFloor();}unchanged(files,path);assertEquals(0,resources.usage().leases());
    }
    @Test void partialReleaseAuthorityRequiresCompleteOriginalFloor()throws Exception {
        for(boolean removed:List.of(false,true)) {
            Path path=temp.resolve("partial-"+removed+"/authority");provision(path);
            try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_AUTHORITY_WRITTEN"))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::releaseFloor);}
            Path release=path.resolve("floor-copies/release.gsr");byte[] bytes=Files.readAllBytes(release);Files.write(release,Arrays.copyOf(bytes,bytes.length/2));
            if(removed) {
                Files.delete(path.resolve("floor-copies/floor.gsr"));var resources=resources();
                assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{}));assertEquals(0,resources.usage().leases());
            }else try(var store=open(path,resources(),e->{})){assertTrue(store.governingFloor().isEmpty());}
        }
    }
    @Test void changedRemainingBytesOrSelectorRejectBeforeFurtherDeletion()throws Exception {
        for(String member:List.of("image","selector","authority")) {
            Path path=temp.resolve(member+"/authority");provision(path);
            try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_RELINQUISHED"))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::releaseFloor);}
            Path file;
            if(member.equals("image"))try(var all=Files.walk(path.resolve("floor-copies"))){file=all.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}
            else file=path.resolve(member.equals("selector")?"selector.gsr":"floor-copies/release.gsr");
            byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);var before=new TreeSet<String>();
            try(var all=Files.walk(path)){all.forEach(p->before.add(path.relativize(p).toString()));}
            var resources=resources();assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{}));assertEquals(0,resources.usage().leases());
            var after=new TreeSet<String>();try(var all=Files.walk(path)){all.forEach(p->after.add(path.relativize(p).toString()));}assertEquals(before,after);
        }
    }
    @Test void sameBytesAtNewInodeAreRejectedBeforeRelinquishingFloor()throws Exception {
        for(String name:List.of("floor-copies/release.gsr","selector.gsr")) {
            Path path=temp.resolve(name.startsWith("floor")?"authority-change/authority":"selector-change/authority");provision(path);
            try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_AUTHORITY_FORCED")) {
                Path file=path.resolve(name),copy=path.getParent().resolve("replacement");Files.write(copy,Files.readAllBytes(file));Files.move(copy,file,StandardCopyOption.REPLACE_EXISTING);
            }})){assertThrows(IllegalArgumentException.class,store::releaseFloor);}
            assertTrue(Files.exists(path.resolve("floor-copies/floor.gsr")));
        }
    }
    @Test void inactiveGenerationAndLegacyModesCannotBypassRelease()throws Exception {
        Path path=temp.resolve("occupied/authority");Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,7);
        try(var store=open(path,resources(),e->{})){assertThrows(IllegalArgumentException.class,store::releaseFloor);store.retireInactive();}
        try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_AUTHORITY_WRITTEN"))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::releaseFloor);}
        var resources=resources();assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openRotating(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,e->{}));assertEquals(0,resources.usage().leases());
        try(var store=open(path,resources,e->{})){store.releaseFloor();}
    }
    @Test void aWellFramedForeignReleaseDecisionCannotDeleteMoreFiles()throws Exception {
        Path path=temp.resolve("foreign/authority");provision(path);
        try(var store=open(path,resources(),e->{if(e.equals("FLOOR_RELEASE_RELINQUISHED"))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::releaseFloor);}
        Path file=path.resolve("floor-copies/release.gsr");var value=new TreeMap<>(decode(Files.readAllBytes(file),"records","RETIREMENT").value());
        value.put("selector","00".repeat(32));Files.write(file,encode("records","RETIREMENT",value));
        var resources=resources();assertEquals("floor release authority context changed",assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{})).getMessage());
        assertEquals(0,resources.usage().leases());assertTrue(Files.exists(path.resolve("floor-copies/proposal.gsr")));
    }
    @Test void nonemptyIncompleteFloorCannotBeDiscardedToMakeRoom()throws Exception {
        Path path=temp.resolve("incomplete/authority");provision(path);Files.delete(path.resolve("floor-copies/floor.gsr"));
        try(var store=open(path,resources(),e->{})) {
            assertEquals("incomplete floor cannot be released",assertThrows(IllegalArgumentException.class,store::releaseFloor).getMessage());
        }
        assertTrue(Files.exists(path.resolve("floor-copies/proposal.gsr")));
    }
}
