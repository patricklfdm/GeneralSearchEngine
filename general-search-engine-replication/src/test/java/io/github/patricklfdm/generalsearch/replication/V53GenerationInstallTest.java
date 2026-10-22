package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53GenerationInstallTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("INSTALL_RESERVED","INSTALL_DIRECTORY_CREATED","INSTALL_MANIFEST_WRITTEN","INSTALL_MANIFEST_FORCED",
            "INSTALL_MEMBER_WRITTEN","INSTALL_MEMBER_FORCED","INSTALL_IMAGE_WRITTEN","INSTALL_IMAGE_FORCED","INSTALL_GENERATION_FORCED",
            "INSTALL_SELECTOR_WRITTEN","INSTALL_SELECTOR_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_PARENT_FORCED","INSTALL_BEFORE_RETURN");
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    Path create(String name,V53GenerationInstallFixture f) throws Exception {Path path=temp.resolve(name);f.provision(path);return path;}
    @Test void exactSelectedParentTailAndImageBecomeCurrentAndOriginalGrantSurvives() throws Exception {
        for(int size:List.of(3,4,5))for(boolean tail:List.of(false,true)) {
            var f=new V53GenerationInstallFixture(size,0,1,tail);Path path=create(size+"-"+tail,f);byte[] old=Files.readAllBytes(path.resolve("generations/a/generation.gsr"));
            var resources=resources();Decoded basis,installed;
            try(var store=f.open(path,resources,e->{})) {
                basis=store.originalBasis().orElseThrow();installed=store.installCurrent(f.offers(store,20),f.bridges,f.images());
                assertEquals("b",installed.value().get("generation"));assertEquals(1L,object(installed.value().get("cut")).get("index"));
                assertEquals(tail,store.currentOwnedTail().isPresent());assertArrayEquals(basis.bytes(),store.prepareCurrent(f.initial.fixture.source.ballot(20)).bytes());
                assertArrayEquals(installed.bytes(),store.installCurrent(f.offers(store,20),f.bridges,f.images()).bytes());
                assertEquals(2,resources.usage().counts().get(MembershipResources.Unit.GENERATION));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=f.open(path,resources,e->{})) {
                assertArrayEquals(installed.bytes(),store.installCurrent(f.offers(store,20),f.bridges,f.images()).bytes());
                var next=store.prepareCurrent(f.initial.fixture.source.ballot(21));assertEquals(1L,object(next.value().get("cut")).get("index"));
                assertArrayEquals(next.bytes(),store.prepareCurrent(f.initial.fixture.source.ballot(21)).bytes());
            }
            assertArrayEquals(old,Files.readAllBytes(path.resolve("generations/a/generation.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void everyInterruptedForceResumesOnlyTheExactSelectionAndKeepsOldGeneration() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,true);
        for(String point:CUTS) {
            Path path=create(point,f);var resources=resources();byte[] old=Files.readAllBytes(path.resolve("generations/a/generation.gsr"));
            try(var store=f.open(path,resources,e->{if(e.equals(point))throw new IOException("cut");})) {
                assertThrows(IOException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=f.open(path,resources,e->{})) {
                var installed=store.installCurrent(f.offers(store,20),f.bridges,f.images());assertEquals("b",installed.value().get("generation"));
            }
            assertArrayEquals(old,Files.readAllBytes(path.resolve("generations/a/generation.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void partialExactMembersCanResumeButDifferingBytesCannotBeRepaired() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,true);
        for(boolean corrupt:List.of(false,true)) {
            Path path=create("partial-"+corrupt,f);
            try(var store=f.open(path,resources(),e->{if(e.equals("INSTALL_MANIFEST_WRITTEN"))throw new IOException("cut");})) {
                assertThrows(IOException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
            }
            Path manifest=path.resolve("generations/b/generation.gsr");byte[] bytes=Arrays.copyOf(Files.readAllBytes(manifest),30);if(corrupt)bytes[2]^=1;Files.write(manifest,bytes);
            try(var store=f.open(path,resources(),e->{})) {
                assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(21)));
                if(corrupt)assertThrows(IllegalArgumentException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
                else assertNotNull(store.installCurrent(f.offers(store,20),f.bridges,f.images()));
            }
            if(corrupt)assertArrayEquals(bytes,Files.readAllBytes(manifest));
        }
    }
    @Test void changedInputOrSelectorAtPublicationCannotReturnInstalledReceipt() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,false);
        for(String kind:List.of("image","selector")) {
            Path path=create(kind,f);var images=f.images();byte[] before=Files.readAllBytes(path.resolve("selector.gsr"));
            try(var store=f.open(path,resources(),e->{if(e.equals("INSTALL_MANIFEST_FORCED")) {
                if(kind.equals("image"))images.values().iterator().next()[0]^=1;
                else{Path selector=path.resolve("selector.gsr");Files.move(selector,temp.resolve("old-selector"));Files.write(selector,before);}
            }})) {assertThrows(Exception.class,()->store.installCurrent(f.offers(store,20),f.bridges,images));}
            assertArrayEquals(before,Files.readAllBytes(path.resolve("selector.gsr")));
        }
    }
    @Test void compactedParentRequiresRetainedAuthenticatedAncestryOnEveryReopen() throws Exception {
        var f=new V53GenerationInstallFixture(3,1,2,true);Path path=create("ancestry",f);
        try(var store=f.open(path,resources(),e->{})){assertNotNull(store.installCurrent(f.offers(store,20),f.bridges,f.images()));}
        try(var store=f.open(path,resources(),e->{})){assertNotNull(store.currentOwnedTail());}
        Files.delete(path.resolve("generations/b/ancestry.gsr"));assertThrows(Exception.class,()->f.open(path,resources(),e->{}));
    }
    @Test void higherObservationAtEachInstallBoundaryPreventsOldReceipt() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,true);
        for(String point:CUTS) {
            Path path=create("fenced-"+point,f);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(path,resources(),e->{if(e.equals(point))ref[0].observeCurrent(f.initial.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
            }
            try(var store=f.open(path,resources(),e->{})){assertNotNull(store.installCurrent(f.offers(store,20),f.bridges,f.images()));}
        }
    }
    @Test void occupiedOldGenerationCannotBeDeletedToMakeRoomForAnotherInstall() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,false);Path path=create("retirement",f);
        try(var store=f.open(path,resources(),e->{})) {
            store.installCurrent(f.offers(store,20),f.bridges,f.images());byte[] old=Files.readAllBytes(path.resolve("generations/a/generation.gsr"));
            store.prepareCurrent(f.initial.fixture.source.ballot(21));store.selectCurrent(f.offers(store,21),List.of());
            var error=assertThrows(IllegalArgumentException.class,()->store.installCurrent(f.offers(store,21),List.of(),f.images()));
            assertEquals("inactive generation requires retirement or exact original install",error.getMessage());
            assertArrayEquals(old,Files.readAllBytes(path.resolve("generations/a/generation.gsr")));
        }
    }
    @Test void installedCapsuleVerifierMustPassBeforeAnySelectorOrStagingMutation() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,true);Path path=create("verify-first",f);byte[] selector=Files.readAllBytes(path.resolve("selector.gsr"));
        try(var store=MembershipGrantJournal.openGenerations(path,f.root(),V53DeclarationsTest.node(1),resources(),(root,packet,images)->{
            if(number(object(packet.capsule().value().get("cut")).get("index"))>0)throw new IllegalArgumentException("unavailable authenticated checkpoint");
            return f.verify(root,packet,images);
        },e->{})) {
            assertEquals("unavailable authenticated checkpoint",assertThrows(IllegalArgumentException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images())).getMessage());
            assertArrayEquals(selector,Files.readAllBytes(path.resolve("selector.gsr")));assertFalse(Files.exists(path.resolve("generations/b")));
        }
    }
    @Test void nextTailFromAnotherOriginalSourceIsMergedWithoutChangingItsBytes() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,false);Path path=temp.resolve("merge-tail");f.initial.provision(path);
        try(var store=f.open(path,resources(),e->{})) {
            store.prepareCurrent(f.initial.fixture.source.ballot(20));var carried=f.remote(3,20,true);
            var offers=List.of(store.originalSource(),f.remote(2,20,false),carried);
            var selected=store.selectCurrent(offers,List.of());assertEquals(carried.entry.digest(),selected.value().get("nextEntry"));
            store.installCurrent(offers,List.of(),f.images());
            assertArrayEquals(carried.accepted.bytes(),Files.readAllBytes(path.resolve("generations/b/owned-tail.gsr")));
            var packet=MembershipSourcePacket.decode(Files.readAllBytes(path.resolve("generations/b/source.gscp")));
            assertArrayEquals(carried.entry.bytes(),packet.objectBytes(carried.entry.digest()));
        }
        try(var store=f.open(path,resources(),e->{})){assertTrue(store.currentOwnedTail().isPresent());}
    }
    @Test void sharedImageCapacityRejectsBeforeWritingAndReleasesReservations() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,false);Path path=create("capacity",f);var resources=resources();
        var external=new ArrayList<MembershipResources.Lease>();
        try(var store=f.open(path,resources,e->{})) {
            for(int i=0;i<5;i++)external.add(resources.reserve(MembershipResources.Unit.APPLICATION,"other-"+i,1));
            var error=assertThrows(IllegalArgumentException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
            assertEquals("resource ownership/count",error.getMessage());assertFalse(Files.exists(path.resolve("generations/b")));
        }finally{external.forEach(MembershipResources.Lease::close);}
        assertEquals(0,resources.usage().leases());
        try(var store=f.open(path,resources,e->{})){assertNotNull(store.installCurrent(f.offers(store,20),f.bridges,f.images()));}
    }
    @Test void recoveryCanBeInterruptedAgainAndPartialSelectorRequiresExactPrefix() throws Exception {
        var f=new V53GenerationInstallFixture(3,0,1,true);Path path=create("twice",f);
        for(int repeat=0;repeat<2;repeat++) {
            try(var store=f.open(path,resources(),e->{if(e.equals("INSTALL_SELECTOR_WRITTEN"))throw new IOException("cut");})) {
                assertThrows(IOException.class,()->store.installCurrent(f.offers(store,20),f.bridges,f.images()));
            }
            Path pending=path.resolve("selector.pending.gsr");Files.write(pending,Arrays.copyOf(Files.readAllBytes(pending),20));
        }
        try(var store=f.open(path,resources(),e->{})){assertNotNull(store.installCurrent(f.offers(store,20),f.bridges,f.images()));}
        assertFalse(Files.exists(path.resolve("selector.pending.gsr")));
    }
}
