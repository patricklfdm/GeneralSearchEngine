package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original local ancestry may preserve retained grants without changing the
 * selected source set, next entry, or supplying a fabricated remote receipt. */
class V53InstallationAncestryTest {
    static MembershipSelection.Decision decision(V53SelectionFixture f) {
        var sources=List.of(f.source("node-1"),f.source("node-2"),f.source("node-3"));
        return new MembershipSelection.Campaign(sources.getFirst()).select(sources,List.of());
    }
    @Test void localRetainedGrantSurvivesEqualCutRemoteSelection() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var bridge=f.bridge(3,5);var chosen=decision(f);
        var local=f.capsule.verify().retainingVerifiedAncestry(List.of(bridge));
        var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));var parents=List.of(V53VerifiedAncestryTest.lower(bridge));
        assertEquals("missing retained installation ancestry",assertThrows(IllegalArgumentException.class,
                ()->MembershipGenerationPlan.installationBridges(chosen,List.of(),List.of(),parents)).getMessage());
        var result=MembershipGenerationPlan.installation(chosen,List.of(),List.of(),parents,local,bytes);
        assertArrayEquals(chosen.selected().bytes(),result.decision().selected().bytes());
        assertEquals(chosen.sources().stream().map(MembershipSelection.Source::reference).toList(),
                result.decision().sources().stream().map(MembershipSelection.Source::reference).toList());
        assertArrayEquals(chosen.longest().capsule.packet.bytes(),result.decision().longest().capsule.packet.bytes());
        assertArrayEquals(bytes,MembershipGenerationPlan.ancestry(result.bridges()));
        assertTrue(result.bridges().getFirst().owned.isEmpty());
        result.decision().longest().capsule.verifyAncestry(bytes,parents);
    }
    @Test void changedOrUnownedAncestryCannotBecomeInstallationAuthority() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var bridge=f.bridge(3,5);var chosen=decision(f);
        var local=f.capsule.verify().retainingVerifiedAncestry(List.of(bridge));
        var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));var parents=List.of(V53VerifiedAncestryTest.lower(bridge));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(chosen,List.of(),List.of(),parents,f.capsule.verify(),bytes));
        var changed=bytes.clone();changed[changed.length-1]^=1;
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(chosen,List.of(),List.of(),parents,local,changed));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(chosen,List.of(),List.of(),parents,local,new byte[0]));
    }
    @Test void membershipEdgePreservesAnEarlierStableEndpointWithoutRenewingIt() {
        var old=new V53SelectionFixture(4,"REMOVE",5);var bridge=old.bridge(3,5);
        var local=old.capsule.verify().retainingVerifiedAncestry(List.of(bridge));var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));
        var chosen=decision(new V53SelectionFixture(4,"REMOVE",6));var parents=List.of(V53VerifiedAncestryTest.lower(bridge));
        var result=MembershipGenerationPlan.installation(chosen,List.of(),List.of(),parents,local,bytes);
        assertArrayEquals(chosen.selected().bytes(),result.decision().selected().bytes());
        assertArrayEquals(bytes,MembershipGenerationPlan.ancestry(result.bridges()));
        result.decision().longest().capsule.verifyAncestry(bytes,parents);
        assertTrue(result.bridges().getFirst().owned.isEmpty());
        assertNotNull(result.decision().longest().capsule.context.view.get("operation"));
    }
    @Test void obsoleteRangeCannotBeRenewedByCopyingItsOldEndorsements() {
        var old=new V53SelectionFixture(4,"REMOVE",4);var bridge=old.bridge(2,4);
        var local=old.capsule.verify().retainingVerifiedAncestry(List.of(bridge));var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));
        var next=decision(new V53SelectionFixture(4,"REMOVE",5));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(next,List.of(),List.of(),
                List.of(V53VerifiedAncestryTest.lower(bridge)),local,bytes));
    }
    @Test void unusedLocalBridgesAreOmittedButExplicitDuplicatesStillFail() {
        var f=new V53SelectionFixture(4,"REMOVE",5);var required=f.bridge(3,5);var unused=f.bridge(2,5);var chosen=decision(f);
        var local=f.capsule.verify().retainingVerifiedAncestry(List.of(required,unused));
        var bytes=MembershipGenerationPlan.ancestry(List.of(required,unused));var parents=List.of(V53VerifiedAncestryTest.lower(required));
        var result=MembershipGenerationPlan.installation(chosen,List.of(),List.of(),parents,local,bytes);
        assertArrayEquals(MembershipGenerationPlan.ancestry(List.of(required)),MembershipGenerationPlan.ancestry(result.bridges()));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(chosen,List.of(),List.of(required,required),parents,local,bytes));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(chosen,List.of(),List.of(unused),parents,local,bytes));
    }
}
