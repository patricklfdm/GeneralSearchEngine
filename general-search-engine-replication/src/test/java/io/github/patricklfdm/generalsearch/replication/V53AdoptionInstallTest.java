package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53AdoptionInstallTest {
    @TempDir Path temp;
    static final List<String> CUTS;
    static {var cuts=new ArrayList<>(List.of("ADOPTION_INSTALL_VALIDATED","PROMISE_BEFORE_WRITE","PROMISE_WRITTEN","PROMISE_FORCED","ADOPTION_INSTALL_FENCED"));
        cuts.addAll(V53GenerationInstallTest.CUTS.subList(0,13));cuts.add("ADOPTION_INSTALL_BEFORE_RETURN");CUTS=List.copyOf(cuts);}
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    @Test void jointAndFinalStateRequireFreshCampaignAndRetainOldGeneration() throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(6,7)) {
            var f=new V53AdoptionFenceFixture(size,through);Path path=temp.resolve(size+"-"+through);f.provision(path);
            byte[] old=Files.readAllBytes(path.resolve("generations/a/generation.gsr"));Decoded installed;var resources=resources();
            try(var store=f.open(path,resources,e->{})) {
                installed=store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
                assertEquals((long)through,object(installed.value().get("cut")).get("index"));assertNull(installed.value().get("selection"));
                assertArrayEquals(installed.bytes(),store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()).bytes());
                assertThrows(IllegalArgumentException.class,()->store.originalSource());
                assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(24+through)));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=f.open(path,resources,e->{})) {
                var grant=store.prepareCurrent(f.initial.fixture.source.ballot(50));
                assertEquals(object(installed.value().get("cut")),grant.value().get("cut"));
                assertEquals(MembershipCapsule.verify(f.remote.source.root,f.remote.packet(),f.remote.source.images,f.owned).context.authority(),grant.value().get("view"));
                assertArrayEquals(installed.bytes(),store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()).bytes());
            }
            assertArrayEquals(old,Files.readAllBytes(path.resolve("generations/a/generation.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void everyBoundaryReopensAndResumesOriginalTransaction() throws Exception {
        for(String point:CUTS) {
            var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve(point);f.provision(path);var resources=resources();
            try(var store=f.open(path,resources,e->{if(e.equals(point))throw new IOException(point);})) {
                assertThrows(IOException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=f.open(path,resources,e->{})) {
                assertEquals(7L,object(store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()).value().get("cut")).get("index"));
            }
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void durableFloorWithoutPrefixBlocksEvenHigherOldViewPrepare() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("floor");f.provision(path);
        try(var store=f.open(path,resources(),e->{if(e.equals("ADOPTION_INSTALL_FENCED"))throw new IOException("cut");})) {
            assertThrows(IOException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
        }
        try(var store=f.open(path,resources(),e->{})) {
            assertEquals("uninstalled adoption fence; prefix recovery required",assertThrows(IllegalArgumentException.class,
                    ()->store.prepareCurrent(f.initial.fixture.source.ballot(99))).getMessage());
            assertNotNull(store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
        }
    }
    @Test void higherOriginalPromiseRemainsButObsoleteSourceCannotVote() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("higher");f.provision(path);
        try(var store=f.open(path,resources(),e->{})) {
            var original=store.prepareCurrent(f.initial.fixture.source.ballot(50));var promise=store.promised().orElseThrow();
            store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
            assertArrayEquals(promise.bytes(),store.promised().orElseThrow().bytes());assertArrayEquals(original.bytes(),store.originalBasis().orElseThrow().bytes());
            assertEquals("obsolete original grant; fresh campaign required",assertThrows(IllegalArgumentException.class,store::originalSource).getMessage());
            assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(50)));
            assertEquals(7L,object(store.prepareCurrent(f.initial.fixture.source.ballot(51)).value().get("cut")).get("index"));
        }
    }
    @Test void stagedDifferentCandidateAndCapacityRefuseBeforePromiseChange() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("different");f.provision(path);
        try(var store=f.open(path,resources(),e->{if(e.equals("INSTALL_MANIFEST_FORCED"))throw new IOException("cut");})) {
            assertThrows(IOException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
        }
        byte[] journal=Files.readAllBytes(path.resolve("grants.gsr"));var other=new V53AdoptionFenceFixture(3,6);
        try(var store=f.open(path,resources(),e->{})) {
            assertThrows(IllegalArgumentException.class,()->store.adoptCurrent(other.remote.packet(),other.remote.source.images,List.of()));
            assertArrayEquals(journal,Files.readAllBytes(path.resolve("grants.gsr")));
        }
        Path capacity=temp.resolve("capacity");f.provision(capacity);var resources=resources();var external=new ArrayList<MembershipResources.Lease>();
        byte[] before=Files.readAllBytes(capacity.resolve("grants.gsr"));
        try(var store=f.open(capacity,resources,e->{})) {
            for(int i=0;i<5;i++)external.add(resources.reserve(MembershipResources.Unit.APPLICATION,"external-"+i,1));
            assertThrows(IllegalArgumentException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
            assertArrayEquals(before,Files.readAllBytes(capacity.resolve("grants.gsr")));assertFalse(Files.exists(capacity.resolve("generations/b")));
        }finally{external.forEach(MembershipResources.Lease::close);}
        assertEquals(0,resources.usage().leases());
    }
    @Test void higherObservedBallotFencesEveryBoundaryAndNoReceiptEscapes() throws Exception {
        for(String point:CUTS) {
            var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("observed-"+point);f.provision(path);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(path,resources(),e->{if(e.equals(point))ref[0].observeCurrent(f.initial.fixture.source.ballot(80));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
            }
            try(var store=f.open(path,resources(),e->{})){assertNotNull(store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));}
        }
    }
    @Test void interruptedRecoveryAgainAndMutableImageCannotPublishDifferentBytes() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("twice");f.provision(path);
        for(int i=0;i<2;i++) {
            try(var store=f.open(path,resources(),e->{if(e.equals("INSTALL_SELECTOR_WRITTEN"))throw new IOException("cut");})) {
                assertThrows(IOException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));
            }
            Path pending=path.resolve("selector.pending.gsr");Files.write(pending,Arrays.copyOf(Files.readAllBytes(pending),20));
        }
        try(var store=f.open(path,resources(),e->{})){assertNotNull(store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));}
        Path mutation=temp.resolve("mutation");f.provision(mutation);var images=new TreeMap<String,byte[]>();f.remote.source.images.forEach((h,b)->images.put(h,b.clone()));
        byte[] selector=Files.readAllBytes(mutation.resolve("selector.gsr"));
        try(var store=f.open(mutation,resources(),e->{if(e.equals("INSTALL_RESERVED"))images.firstEntry().getValue()[0]^=1;})) {
            assertThrows(IllegalArgumentException.class,()->store.adoptCurrent(f.remote.packet(),images,List.of()));
        }
        assertArrayEquals(selector,Files.readAllBytes(mutation.resolve("selector.gsr")));
    }
    @Test void knownRemovedIdentityCanRetainAuthorityButCannotGrant() throws Exception {
        for(int size:List.of(3,4,5)) {
            var f=new V53AdoptionFenceFixture(size,7);Path path=temp.resolve("removed-"+size);f.initial.provision(path);
            String node="node-"+size;var identity=V53DeclarationsTest.node(size);
            Files.write(path.resolve("node.gsr"),encode("records","NODE",Map.of("identity",V53ContextFixture.member(size),"root",f.initial.root().manifestDigest())));
            Files.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",Map.of("counter",0L,"node",node,"root",f.initial.root().manifestDigest())));
            var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value());manifest.put("node",node);
            byte[] bytes=encode("records","GENERATION",manifest);Files.write(path.resolve("generations/a/generation.gsr"),bytes);
            Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",f.initial.root().manifestDigest(),"node",node,"generation","a","digest",hash(bytes))));
            for(int i=0;i<2;i++)try(var store=MembershipGrantJournal.openGenerations(path,f.initial.root(),identity,resources(),
                    (r,p,images)->MembershipCapsule.verify(r,p,images,f.owned),e->{})) {
                if(i==0)store.prepareCurrent(f.initial.fixture.source.ballot(20));
                assertEquals(7L,object(store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()).value().get("cut")).get("index"));
                assertEquals("grant local eligible identity",assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(50))).getMessage());
            }
        }
    }
    @Test void missingAdoptionMarkerAndSubstitutedStagingInodeRefuse() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("missing");f.provision(path);
        try(var store=f.open(path,resources(),e->{})){store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());}
        Files.delete(path.resolve("generations/b/adopted-certificate.gsr"));assertThrows(IllegalArgumentException.class,()->f.open(path,resources(),e->{}));
        Path changed=temp.resolve("inode");f.provision(changed);byte[] selector=Files.readAllBytes(changed.resolve("selector.gsr"));
        try(var store=f.open(changed,resources(),e->{if(e.equals("INSTALL_MANIFEST_FORCED")) {
            Path file=changed.resolve("generations/b/generation.gsr");byte[] value=Files.readAllBytes(file);
            Files.move(file,temp.resolve("saved-manifest"));Files.write(file,value);
        }})) {assertThrows(IllegalArgumentException.class,()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of()));}
        assertArrayEquals(selector,Files.readAllBytes(changed.resolve("selector.gsr")));
    }

    @Test void subsequentAdoptionCannotRetireOldGenerationOrRaiseFenceWithoutRoom() throws Exception {
        var joint=new V53AdoptionFenceFixture(3,6);var stable=new V53AdoptionFenceFixture(3,7);joint.owned.addAll(stable.owned);
        Path path=temp.resolve("retirement");joint.provision(path);
        try(var store=joint.open(path,resources(),e->{})) {
            store.adoptCurrent(joint.remote.packet(),joint.remote.source.images,List.of());
            byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));byte[] old=Files.readAllBytes(path.resolve("generations/a/generation.gsr"));
            assertEquals("inactive generation requires retirement or exact original install",assertThrows(IllegalArgumentException.class,
                    ()->store.adoptCurrent(stable.remote.packet(),stable.remote.source.images,List.of())).getMessage());
            assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));assertArrayEquals(old,Files.readAllBytes(path.resolve("generations/a/generation.gsr")));
        }
    }
    @Test void compactedCurrentParentRequiresAuthenticatedRetainedBridge() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);var initial=new V53CurrentGenerationFixture(3,1,true);f.owned.addAll(initial.fixture.owned);
        var bridge=new V53SelectionFixture(3,"REPLACE",7).bridge(1,5);f.owned.addAll(bridge.owned);
        Path path=temp.resolve("ancestry");initial.provision(path);
        try(var store=f.open(path,resources(),e->{})) {
            store.prepareCurrent(initial.fixture.source.ballot(20));byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));
            assertEquals("generation did not preserve original proven parent",assertThrows(IllegalArgumentException.class,
                    ()->store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of())).getMessage());
            assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));assertFalse(Files.exists(path.resolve("generations/b")));
            store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of(bridge));assertTrue(store.currentOwnedTail().isEmpty());
            assertTrue(Files.exists(path.resolve("generations/a/owned-tail.gsr")));
        }
        try(var store=f.open(path,resources(),e->{})){assertTrue(store.currentOwnedTail().isEmpty());}
    }

}
