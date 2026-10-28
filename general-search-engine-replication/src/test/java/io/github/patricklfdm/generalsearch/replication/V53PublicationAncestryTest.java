package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fixture-owned original ACKs test assembly; real endpoint qualification is
 * supplied separately by the native SEAL-to-new-stable round history. */
class V53PublicationAncestryTest {
    @Test void nativePendingInventoryKeepsExistingAncestryWithoutAuthenticatingExtraRecords() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var bridge=f.bridge(3,5);
        // The complete fixture contains observations for all nine steps. The
        // native owner at cut five has no observation for the next certificate.
        var original=f.capsule.packet();var owned=new HashSet<MembershipContext.Owned>();
        for(var observation:f.capsule.owned)if(original.objectNames().contains(observation.record()))owned.add(observation);
        var before=MembershipCapsule.verify(f.capsule.source.root,original,f.capsule.source.images,owned)
                .retainingVerifiedAncestry(List.of(bridge));var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));
        var packet=V53CheckpointPlanTest.certified(before,f.capsule.source,f.capsule.source.steps.get(5));
        var pending=before.originalMaterialization(packet,f.capsule.source.images);
        pending.verifyAncestry(bytes,List.of(V53VerifiedAncestryTest.lower(bridge)));
        assertTrue(pending.verifiedAncestry(bytes).getFirst().owned.isEmpty());
        var cert=decode(packet.objectBytes((String)f.capsule.source.steps.get(5).get("certificate")),"records","CERTIFICATE");
        assertThrows(IllegalArgumentException.class,()->pending.publicationCertificate(cert,before.context.cut));
        // The old projection lost history outside the indexed packet entirely.
        assertThrows(IllegalArgumentException.class,()->before.materialization(packet,f.capsule.source.images,List.of())
                .verifyAncestry(bytes,List.of(V53VerifiedAncestryTest.lower(bridge))));
    }
    @Test void originalMaterializationCannotExtendPrefixOrInventHistoricalAuthority() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var bridge=f.bridge(3,5);
        var before=f.capsule.verify();var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));
        assertThrows(IllegalArgumentException.class,()->before.originalMaterialization(before.packet,f.capsule.source.images)
                .verifyAncestry(bytes,List.of(V53VerifiedAncestryTest.lower(bridge))));
        var next=new V53SelectionFixture(4,"REMOVE",6);
        assertThrows(IllegalArgumentException.class,()->before.originalMaterialization(next.capsule.packet(),next.capsule.source.images));
    }
    @Test void membershipEdgeKeepsOriginalStableAncestorsWithoutInventingNewAcknowledgements() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var bridge=f.bridge(3,5);
        var before=f.capsule.verify().retainingVerifiedAncestry(List.of(bridge));
        var ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));var lower=V53VerifiedAncestryTest.lower(bridge);
        var plan=V53CheckpointPlanTest.plan(before,f.capsule.source,5).renewAncestors(List.of(lower),ancestry);
        assertEquals("MEMBERSHIP",plan.statement.value().get("scope"));assertTrue(plan.additionalParents().isEmpty());
        var retained=plan.retainedBridges(ancestry);assertEquals(1,retained.size());
        assertArrayEquals(ancestry,MembershipGenerationPlan.ancestry(retained));
        assertTrue(retained.getFirst().owned.isEmpty(),"stored authority is historical, not a fresh observed ACK");
        var ends=V53CheckpointPlanTest.endorsements(plan);
        assertThrows(IllegalArgumentException.class,()->plan.publication(ends.acks(),ends.owned(),List.of()));
        var published=plan.publication(ends.acks(),ends.owned(),retained);
        published.verifyAncestry(ancestry,List.of(lower));
        assertEquals(6L,published.context.cut.get("index"));
        assertNotNull(published.context.view.get("operation"));
    }
    @Test void extendingTheSameRangeRequiresRenewalInsteadOfReusingItsOldEndpoint() {
        var f=new V53SelectionFixture(4,"REMOVE",4);var bridge=f.bridge(2,4);
        var before=f.capsule.verify().retainingVerifiedAncestry(List.of(bridge));
        var ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));var lower=V53VerifiedAncestryTest.lower(bridge);
        var plan=V53CheckpointPlanTest.plan(before,f.capsule.source,4).renewAncestors(List.of(lower),ancestry);
        assertEquals("RANGE",plan.statement.value().get("scope"));
        assertEquals(List.of(lower),plan.additionalParents());assertTrue(plan.retainedBridges(ancestry).isEmpty());
        var ends=V53CheckpointPlanTest.endorsements(plan);
        assertThrows(IllegalArgumentException.class,()->plan.publication(ends.acks(),ends.owned(),List.of(bridge)));
    }
    @Test void retainedProofsMustBeAuthenticatedRequiredAndUnchanged() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var required=f.bridge(3,5);var unused=f.bridge(2,5);
        var before=f.capsule.verify().retainingVerifiedAncestry(List.of(required,unused));
        var ancestry=MembershipGenerationPlan.ancestry(List.of(required,unused));
        var plan=V53CheckpointPlanTest.plan(before,f.capsule.source,5)
                .renewAncestors(List.of(V53VerifiedAncestryTest.lower(required)),ancestry);
        assertArrayEquals(MembershipGenerationPlan.ancestry(List.of(required)),MembershipGenerationPlan.ancestry(plan.retainedBridges(ancestry)));
        assertThrows(IllegalArgumentException.class,()->plan.retainedBridges(new byte[0]));
        var changed=ancestry.clone();changed[changed.length-1]^=1;
        assertThrows(IllegalArgumentException.class,()->plan.retainedBridges(changed));
        var unowned=V53CheckpointPlanTest.plan(f.capsule.verify(),f.capsule.source,5);
        assertThrows(IllegalArgumentException.class,()->unowned.retainedBridges(ancestry));
    }
}
