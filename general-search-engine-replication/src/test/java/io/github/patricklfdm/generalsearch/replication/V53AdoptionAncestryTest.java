package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Conditional original histories exercise real adoption, retirement and reopen.
 * Local historical bridges preserve retained parents, never supply new votes. */
class V53AdoptionAncestryTest {
    @TempDir Path temp;
    @ParameterizedTest @ValueSource(ints={3,4,5})
    void jointOwnerAdoptsFinalWithoutRequiringDonorToKnowItsOlderFloor(int size)throws Exception {
        var initial=new V53CurrentGenerationFixture(size,3,false);
        var joint=new V53AdoptionFenceFixture(size,6);var stable=new V53AdoptionFenceFixture(size,7);
        var bridge=new V53SelectionFixture(size,"REPLACE",5).bridge(3,5);
        var owned=new HashSet<>(initial.fixture.owned);owned.addAll(joint.owned);owned.addAll(stable.owned);owned.addAll(bridge.owned);
        var path=temp.resolve("owner");initial.provision(path);
        var budget=new MembershipResources(512*MembershipResources.MIB);
        MembershipCurrentGeneration.Verifier verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,owned);
        byte[] ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));
        try(var owner=MembershipGrantJournal.openRetirement(path,initial.root(),V53DeclarationsTest.node(1),budget,verifier,e->{})) {
            var copies=new ArrayList<MembershipFloor.Copy>();copies.add(owner.floorCopyCurrent());
            for(int node=2;node<=size/2+1;node++)copies.add(new V53FloorTest().copy(temp.resolve("peer-"+node),size,3,node));
            owner.establishFloor(copies);owner.prepareCurrent(initial.fixture.source.ballot(20));
            owner.adoptCurrent(joint.remote.packet(),joint.remote.source.images,List.of(bridge));
            assertTrue(owner.retireInactive().isPresent());
        }
        var originalSources=V53ReplayFilesTest.files(path.resolve("sources"));
        var incoming=V53VerifiedAdoptionTest.verified(stable);byte[] packet=incoming.packet.bytes();
        try(var owner=MembershipGrantJournal.openRetirement(path,initial.root(),V53DeclarationsTest.node(1),budget,verifier,e->{})) {
            assertEquals(6L,owner.activationContext().cut.get("index"));
            var result=owner.adoptCurrent(incoming,stable.remote.source.images,List.of());
            assertArrayEquals(result.bytes(),owner.adoptCurrent(incoming,stable.remote.source.images,List.of()).bytes());
            assertNull(result.value().get("basis"));assertNull(result.value().get("selection"));assertNull(result.value().get("ownedTail"));
            var copy=owner.floorCopyCurrent();assertArrayEquals(packet,copy.capsule.packet.bytes());
            assertArrayEquals(ancestry,copy.fileBytes("ancestry.gsr"));
            copy.capsule.verifyAncestry(ancestry,List.of(V53VerifiedAncestryTest.lower(bridge)));
        }
        assertEquals(originalSources,V53ReplayFilesTest.files(path.resolve("sources")));
        try(var owner=MembershipGrantJournal.openRetirement(path,initial.root(),V53DeclarationsTest.node(1),budget,verifier,e->{})) {
            assertEquals(7L,owner.activationContext().cut.get("index"));
            assertArrayEquals(ancestry,owner.floorCopyCurrent().fileBytes("ancestry.gsr"));
        }
        assertEquals(0,budget.usage().leases());
        assertThrows(IllegalArgumentException.class,()->incoming.verifyAncestry(ancestry,List.of(V53VerifiedAncestryTest.lower(bridge))));
    }
}
