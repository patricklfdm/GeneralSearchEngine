package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional protocol fixtures for the typed boundary, alongside actual-bootstrap TCP histories. */
class V53VerifiedAdoptionTest {
    @TempDir Path temp;
    static MembershipCapsule verified(V53AdoptionFenceFixture f) {
        return MembershipCapsule.verify(f.remote.source.root,f.remote.packet(),f.remote.source.images,f.owned);
    }
    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    @Test void typedFenceAndInstallPreserveExactOriginalAuthorityWithoutFreshVotes()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(6,7)) {
            var f=new V53AdoptionFenceFixture(size,through);var path=temp.resolve(size+"-"+through);f.provision(path);
            var prefix=verified(f);var budget=resources();
            try(var owner=f.open(path,budget,event->{})) {
                var fence=owner.fenceMembershipPrefix(prefix,f.remote.source.images,List.of());
                assertNull(fence.value().get("basisId"));assertTrue(owner.originalBasis().isEmpty());
                var result=owner.adoptCurrent(prefix,f.remote.source.images,List.of());
                assertArrayEquals(result.bytes(),owner.adoptCurrent(prefix,f.remote.source.images,List.of()).bytes());
                assertNull(result.value().get("selection"));assertNull(result.value().get("basis"));assertNull(result.value().get("ownedTail"));
                assertThrows(IllegalArgumentException.class,owner::originalSource);
            }
            try(var owner=f.open(path,budget,event->{})){assertEquals(prefix.context.cut,owner.activationContext().cut);}
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void foreignVerifiedRootAndChangedImagesCannotTouchLocalStorage()throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);var foreign=new V53AdoptionFenceFixture(4,7);
        var path=temp.resolve("original");f.provision(path);var budget=resources();
        try(var owner=f.open(path,budget,event->{})) {
            var before=V53ReplayFilesTest.files(path);var wrong=verified(foreign);
            assertEquals("adoption historical root differs",assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(wrong,foreign.remote.source.images,List.of())).getMessage());
            assertEquals("adoption historical root differs",assertThrows(IllegalArgumentException.class,()->owner.fenceMembershipPrefix(wrong,foreign.remote.source.images,List.of())).getMessage());
            var incoming=verified(f);var images=new TreeMap<>(f.remote.source.images);var first=images.firstKey();byte[] bytes=images.get(first).clone();bytes[0]^=1;images.put(first,bytes);
            assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(incoming,images,List.of()));
            assertThrows(IllegalArgumentException.class,()->owner.fenceMembershipPrefix(incoming,images,List.of()));
            assertEquals(before,V53ReplayFilesTest.files(path));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void typedRangeCannotMintAMembershipFence()throws Exception {
        var f=new V53AdoptionFenceFixture(3,1);var path=temp.resolve("range");f.provision(path);var budget=resources();
        try(var owner=f.open(path,budget,event->{})) {
            var prefix=verified(f);var before=V53ReplayFilesTest.files(path);
            assertEquals("no authenticated membership certificate fence",assertThrows(IllegalArgumentException.class,()->owner.fenceMembershipPrefix(prefix,f.remote.source.images,List.of())).getMessage());
            assertEquals("no authenticated membership certificate fence",assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(prefix,f.remote.source.images,List.of())).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(path));
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void higherObservedBallotStillFencesEveryTypedInstallBoundary()throws Exception {
        for(String point:V53AdoptionInstallTest.CUTS) {
            var f=new V53AdoptionFenceFixture(3,7);var path=temp.resolve(point);f.provision(path);var prefix=verified(f);var budget=resources();
            MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var owner=f.open(path,budget,event->{if(event.equals(point))ref[0].observeCurrent(f.initial.fixture.source.ballot(80));})) {
                ref[0]=owner;assertThrows(IllegalArgumentException.class,()->owner.adoptCurrent(prefix,f.remote.source.images,List.of()));
            }
            try(var owner=f.open(path,budget,event->{})){assertNotNull(owner.adoptCurrent(prefix,f.remote.source.images,List.of()));}
            assertEquals(0,budget.usage().leases());
        }
    }
}
