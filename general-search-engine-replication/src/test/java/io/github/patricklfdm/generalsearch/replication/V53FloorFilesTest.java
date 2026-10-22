package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53FloorFilesTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("FLOOR_RESERVED","FLOOR_DIRECTORY_CREATED","FLOOR_PROPOSAL_WRITTEN","FLOOR_PROPOSAL_FORCED",
            "FLOOR_COPY_CREATED","FLOOR_MANIFEST_WRITTEN","FLOOR_MANIFEST_FORCED","FLOOR_IMAGE_WRITTEN","FLOOR_IMAGE_FORCED",
            "FLOOR_MEMBER_WRITTEN","FLOOR_MEMBER_FORCED","FLOOR_COPY_DIRECTORY_FORCED","FLOOR_COPIES_FORCED",
            "FLOOR_AUTHORITY_WRITTEN","FLOOR_AUTHORITY_FORCED","FLOOR_PARENT_FORCED","FLOOR_BEFORE_RETURN");
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipFloor.Copy copy(Path path,int through,int node)throws Exception{return new V53FloorTest().copy(path,3,through,node);}
    MembershipGrantJournal open(Path path,int through,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var fixture=new V53CurrentGenerationFixture(3,through,false);
        return MembershipGrantJournal.openFloors(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,cut);
    }
    @Test void forcedCopiesAndFloorSurviveReopenAndExactDuplicate()throws Exception {
        for(int through:List.of(0,6,7)) {
            Path path=temp.resolve("local-"+through);var a=copy(path,through,1);var b=copy(temp.resolve("peer-"+through),through,2);var resources=resources();byte[] floor;
            try(var store=open(path,through,resources,e->{})) {
                assertTrue(store.governingFloor().isEmpty());floor=store.establishFloor(List.of(a,b)).bytes();
                assertArrayEquals(floor,store.establishFloor(List.of(b,a)).bytes());
                assertEquals(2,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertEquals(3,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=open(path,through,resources,e->{})){assertArrayEquals(floor,store.governingFloor().orElseThrow().bytes());}
            assertEquals(0,resources.usage().leases());
            assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));assertTrue(Files.exists(path.resolve("grants.gsr")));
        }
    }
    @Test void everyInterruptedBoundaryResumesOnlyTheOriginalFullCopies()throws Exception {
        for(String point:CUTS) {
            Path path=temp.resolve(point);var a=copy(path,6,1);var b=copy(temp.resolve(point+"-peer"),6,2);var c=copy(temp.resolve(point+"-other"),6,6);
            byte[] promise=Files.readAllBytes(path.resolve("grants.gsr"));var resources=resources();
            try(var store=open(path,6,resources,e->{if(e.equals(point))throw new java.io.IOException("cut "+point);})) {
                assertThrows(java.io.IOException.class,()->store.establishFloor(List.of(a,b)),point);
            }
            assertEquals(0,resources.usage().leases(),point);assertArrayEquals(promise,Files.readAllBytes(path.resolve("grants.gsr")),point);
            if(Files.exists(path.resolve("floor-copies/proposal.gsr"))) {
                try(var store=open(path,6,resources,e->{})) {
                    assertThrows(IllegalArgumentException.class,()->store.establishFloor(List.of(a,c)),point);
                }
            }
            try(var store=open(path,6,resources,e->{})){store.establishFloor(List.of(a,b));assertTrue(store.governingFloor().isPresent(),point);}
            assertEquals(0,resources.usage().leases(),point);
        }
    }
    @Test void partialProposalAndMemberAreResumedButDoNotAuthorizeOtherChanges()throws Exception {
        for(String point:List.of("FLOOR_PROPOSAL_WRITTEN","FLOOR_MEMBER_WRITTEN","FLOOR_AUTHORITY_WRITTEN")) {
            Path path=temp.resolve(point);var a=copy(path,6,1);var b=copy(temp.resolve(point+"-peer"),6,2);
            try(var store=open(path,6,resources(),e->{if(e.equals(point))throw new java.io.IOException("cut");})) {assertThrows(java.io.IOException.class,()->store.establishFloor(List.of(a,b)));}
            Path member;
            if(point.equals("FLOOR_PROPOSAL_WRITTEN"))member=path.resolve("floor-copies/proposal.gsr");
            else if(point.equals("FLOOR_AUTHORITY_WRITTEN"))member=path.resolve("floor-copies/floor.gsr");
            else try(var walk=Files.walk(path.resolve("floor-copies"))){member=walk.filter(p->p.getFileName().toString().equals("promise.gsr")).findFirst().orElseThrow();}
            byte[] original=Files.readAllBytes(member);Files.write(member,Arrays.copyOf(original,original.length/2));
            try(var store=open(path,6,resources(),e->{})) {
                assertTrue(store.governingFloor().isEmpty());
                var f=new V53CurrentGenerationFixture(3,6,false);
                assertEquals("pending floor must finish before authority changes",assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.fixture.source.ballot(20))).getMessage());
                store.establishFloor(List.of(a,b));assertTrue(store.governingFloor().isPresent());
            }
        }
    }
    @Test void sharedSourceCapacityRejectsBeforeAnyFloorWritesAndDoesNotLeak()throws Exception {
        Path path=temp.resolve("limited");var a=copy(path,0,1);var b=copy(temp.resolve("peer"),0,2);var resources=resources();var external=new ArrayList<MembershipResources.Lease>();
        for(int i=0;i<5;i++)external.add(resources.reserve(MembershipResources.Unit.SOURCE,"elsewhere-"+i,1));
        byte[] promise=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,0,resources,e->{})){assertThrows(IllegalArgumentException.class,()->store.establishFloor(List.of(a,b)));}
        assertEquals(5,resources.usage().leases());assertFalse(Files.exists(path.resolve("floor-copies")));assertArrayEquals(promise,Files.readAllBytes(path.resolve("grants.gsr")));
        external.forEach(MembershipResources.Lease::close);assertEquals(0,resources.usage().leases());
    }
    @Test void corruptionExtraFilesAndSymlinksCannotBecomeRetainedFloorAuthority()throws Exception {
        for(String mutation:List.of("image","generation","extra","symlink","floor")) {
            Path path=temp.resolve(mutation);var a=copy(path,7,1);var b=copy(temp.resolve(mutation+"-peer"),7,2);
            try(var store=open(path,7,resources(),e->{})){store.establishFloor(List.of(a,b));}
            Path source=path.resolve("floor-copies").resolve(a.generation.digest());
            if(mutation.equals("extra"))Files.writeString(source.resolve("unknown"),"x");
            else if(mutation.equals("symlink")){Files.delete(source.resolve("source.gscp"));Files.createSymbolicLink(source.resolve("source.gscp"),path.resolve("generations/a/source.gscp"));}
            else {
                Path file=mutation.equals("floor")?path.resolve("floor-copies/floor.gsr"):source.resolve(mutation.equals("generation")?"generation.gsr":a.capsule.terminal().application()+".image");
                byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);
            }
            var resources=resources();assertThrows(Exception.class,()->open(path,7,resources,e->{}));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void sameByteInodeReplacementAtForceCannotReturnSuccess()throws Exception {
        for(String event:List.of("FLOOR_MANIFEST_WRITTEN","FLOOR_AUTHORITY_FORCED","FLOOR_BEFORE_RETURN")) {
            Path path=temp.resolve(event);var a=copy(path,6,1);var b=copy(temp.resolve(event+"-peer"),6,2);
            var resources=resources();
            try(var store=open(path,6,resources,e->{if(e.equals(event)) {
                Path member=event.equals("FLOOR_MANIFEST_WRITTEN")?path.resolve("floor-copies").resolve(List.of(a.generation.digest(),b.generation.digest()).stream().sorted().findFirst().orElseThrow()).resolve("generation.gsr"):path.resolve("floor-copies/floor.gsr");
                Path replacement=temp.resolve("replacement");Files.write(replacement,Files.readAllBytes(member));Files.move(replacement,member,StandardCopyOption.REPLACE_EXISTING);
            }})){assertThrows(IllegalArgumentException.class,()->store.establishFloor(List.of(a,b)),event);}
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void retainedFloorCannotBeSilentlyOpenedThroughLegacyStorageMode()throws Exception {
        Path path=temp.resolve("mode");var a=copy(path,0,1);var b=copy(temp.resolve("peer"),0,2);
        try(var store=open(path,0,resources(),e->{})){store.establishFloor(List.of(a,b));}
        var f=new V53CurrentGenerationFixture(3,0,false);
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openGenerations(path,f.root(),V53DeclarationsTest.node(1),resources(),f::verify,e->{}));
    }
    @Test void oldFloorSurvivesAdoptionButCannotBeReplacedWithoutRotation()throws Exception {
        Path path=temp.resolve("advance");var a=copy(path,0,1);var b=copy(temp.resolve("peer"),0,2);var initial=new V53CurrentGenerationFixture(3,0,false);
        var remote=new V53AdoptionFenceFixture(3,6);byte[] floor;
        MembershipCurrentGeneration.Verifier verifier=(r,p,images)->MembershipCapsule.verify(r,p,images,remote.owned);
        try(var store=MembershipGrantJournal.openFloors(path,initial.root(),V53DeclarationsTest.node(1),resources(),verifier,e->{})) {
            floor=store.establishFloor(List.of(a,b)).bytes();store.adoptCurrent(remote.remote.packet(),remote.remote.source.images,List.of());
            assertArrayEquals(floor,store.governingFloor().orElseThrow().bytes());
            var adopted=store.floorCopyCurrent();assertTrue(adopted.fileNames().contains(MembershipGenerationPlan.ADOPTION));
            var peer=copy(temp.resolve("next-peer"),6,2);
            assertThrows(IllegalArgumentException.class,()->store.establishFloor(List.of(adopted,peer)));
        }
        try(var store=MembershipGrantJournal.openFloors(path,initial.root(),V53DeclarationsTest.node(1),resources(),verifier,e->{})) {
            assertArrayEquals(floor,store.governingFloor().orElseThrow().bytes());
        }
        assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
    }
    @Test void selectedGenerationFloorCopyRetainsUnresolvedOriginalTail()throws Exception {
        for(boolean tail:List.of(false,true)) {
            var fixture=new V53GenerationInstallFixture(3,0,1,tail);Path path=temp.resolve("selected-"+tail);fixture.provision(path);
            try(var store=fixture.open(path,resources(),e->{})) {
                store.installCurrent(fixture.offers(store,20),fixture.bridges,fixture.images());var copy=store.floorCopyCurrent();
                assertEquals(tail,copy.fileNames().contains("owned-tail.gsr"));
                assertNotNull(copy.generation.value().get("basis"));assertNotNull(copy.generation.value().get("selection"));
                if(tail)assertArrayEquals(Files.readAllBytes(path.resolve("generations/b/owned-tail.gsr")),copy.fileBytes("owned-tail.gsr"));
            }
        }
    }

}
