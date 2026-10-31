package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53AdoptionAncestryPlanTest {
    final V53SelectionFixture f=new V53SelectionFixture(3,"REPLACE",5);
    final MembershipSelection.Bridge required=f.bridge(3,5),unused=f.bridge(2,5);
    final MembershipCapsule local=f.capsule.verify().retainingVerifiedAncestry(List.of(required,unused));
    final MembershipCapsule incoming=new V53SelectionFixture(3,"REPLACE",7).capsule.verify();
    final byte[] bytes=MembershipGenerationPlan.ancestry(List.of(required,unused));
    final List<MembershipCapsule.Anchor> parents=List.of(V53VerifiedAncestryTest.lower(required));

    @Test void onlyRequiredOriginalBridgesSurviveWithoutNewVotesOrChangedPacket() {
        var result=MembershipGenerationPlan.adoption(incoming,List.of(),parents,local,bytes);
        assertArrayEquals(incoming.packet.bytes(),result.capsule().packet.bytes());
        assertArrayEquals(MembershipGenerationPlan.ancestry(List.of(required)),MembershipGenerationPlan.ancestry(result.bridges()));
        assertTrue(result.bridges().getFirst().owned.isEmpty());
        assertThrows(UnsupportedOperationException.class,()->result.bridges().clear());
        result.capsule().verifyAncestry(MembershipGenerationPlan.ancestry(result.bridges()),parents);
        assertThrows(IllegalArgumentException.class,()->incoming.verifyAncestry(MembershipGenerationPlan.ancestry(result.bridges()),parents));
    }
    @Test void unverifiedChangedAndMissingLocalProofCannotSupplyParents() {
        var changed=bytes.clone();changed[changed.length-1]^=1;
        for(byte[] value:List.of(changed,new byte[0],Arrays.copyOf(bytes,bytes.length-1)))
            assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(incoming,List.of(),parents,local,value));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(incoming,List.of(),parents,f.capsule.verify(),bytes));
    }
    @Test void localProofCannotRepairInvalidExplicitRemoteProofOrDuplicateIt() {
        var remote=incoming.inheritingAncestry(local,List.of(required));
        var result=MembershipGenerationPlan.adoption(remote,List.of(required),parents,local,bytes);
        assertEquals(1,result.bridges().size());
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(remote,List.of(required,required),parents,local,bytes));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(incoming,List.of(required),parents,local,bytes));
        var changed=new MembershipSelection.Bridge(required.statement,required.acknowledgements.subList(0,2),Set.of());
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(remote,List.of(changed),parents,local,bytes));
    }
    @Test void obsoleteEndpointAndForeignRootCannotBeInherited() {
        var old=new V53SelectionFixture(3,"REPLACE",4);var bridge=old.bridge(2,4);
        var original=old.capsule.verify().retainingVerifiedAncestry(List.of(bridge));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(incoming,List.of(),
                List.of(V53VerifiedAncestryTest.lower(bridge)),original,MembershipGenerationPlan.ancestry(List.of(bridge))));
        var foreign=new V53SelectionFixture(4,"REPLACE",7).capsule.verify();
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(foreign,List.of(),parents,local,bytes));
    }
    @Test void ConflictingDirectOrLowerParentCannotBeHiddenByValidAncestry() {
        for(var parent:List.of(incoming.terminal(),parents.getFirst())) {
            var changed=new MembershipCapsule.Anchor(parent.cut(),parent.catalog(),"a".repeat(64));
            assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(incoming,List.of(),List.of(changed),local,bytes));
        }
    }
    @Test void ExistingCapacityLimitsAndExplicitProofValidationApplyEvenWithoutParents() {
        var remote=incoming.inheritingAncestry(local,List.of(required));
        assertEquals("generation ancestry count",assertThrows(IllegalArgumentException.class,()->
                MembershipGenerationPlan.adoption(remote,Collections.nCopies(7,required),List.of(),local,bytes)).getMessage());
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.adoption(incoming,List.of(required),List.of(),local,bytes));
        assertTrue(MembershipGenerationPlan.adoption(incoming,List.of(),List.of(incoming.terminal()),local,bytes).bridges().isEmpty());
    }
}
