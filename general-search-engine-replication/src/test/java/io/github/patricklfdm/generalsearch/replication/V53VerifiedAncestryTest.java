package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Authenticated supplemental statements remain exact history, never new votes. */
class V53VerifiedAncestryTest {
    static MembershipCapsule.Anchor lower(MembershipSelection.Bridge bridge) {
        var v=bridge.statement.value();return new MembershipCapsule.Anchor(object(v.get("start")),(String)v.get("catalogBefore"),(String)v.get("applicationBefore"));
    }
    @Test void sharedValidationBindsEveryParentToOneAuthenticatedCapsule() {
        var fixture=new V53SelectionFixture(3,"REPLACE",5);var original=fixture.capsule.verify();
        var bridge=fixture.bridge(1,5);var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));
        var retained=original.retainingVerifiedAncestry(List.of(bridge));var parent=lower(bridge);
        var checked=retained.checkedAncestry(bytes);
        checked.require(retained,List.of(parent,retained.terminal()));
        assertThrows(IllegalArgumentException.class,()->original.checkedAncestry(bytes));
        assertThrows(IllegalArgumentException.class,()->checked.require(original,List.of(parent)));
        // Even equivalent bytes under a distinct capsule require a fresh proof.
        var equivalent=original.retainingVerifiedAncestry(List.of(bridge));
        assertThrows(IllegalArgumentException.class,()->checked.require(equivalent,List.of(parent)));
        var changed=new MembershipCapsule.Anchor(parent.cut(),"f".repeat(64),parent.application());
        assertThrows(IllegalArgumentException.class,()->checked.require(retained,List.of(changed)));
        bytes[bytes.length-1]^=1;
        assertThrows(IllegalArgumentException.class,()->retained.checkedAncestry(bytes));
        checked.require(retained,List.of(parent)); // prior immutable result is not mutable input storage
    }
    @Test void exactOwnedBridgeSurvivesSerializationWithoutChangingOriginalCapsule() {
        var f=new V53SelectionFixture(3,"REPLACE",5);var original=f.capsule.verify();var bridge=f.bridge(1,5);
        var bytes=MembershipGenerationPlan.ancestry(List.of(bridge));var parent=lower(bridge);
        assertThrows(IllegalArgumentException.class,()->original.verifyAncestry(bytes,List.of(parent)));
        var retained=original.retainingVerifiedAncestry(List.of(bridge));retained.verifyAncestry(bytes,List.of(parent));
        assertArrayEquals(original.packet.bytes(),retained.packet.bytes());
        assertThrows(IllegalArgumentException.class,()->original.verifyAncestry(bytes,List.of(parent)));
        var historical=new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements,Set.of());
        historical.verify(retained,parent);
        assertThrows(IllegalArgumentException.class,()->historical.verify(original,parent));
    }
    @Test void rawWitnessHashesAndChangedWitnessSetCannotAcquireAuthority() {
        var f=new V53SelectionFixture(3,"REPLACE",5);var original=f.capsule.verify();var bridge=f.bridge(1,5);
        var raw=new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements,Set.of());
        assertEquals("ancestry ACK before owned end",assertThrows(IllegalArgumentException.class,()->original.retainingVerifiedAncestry(List.of(raw))).getMessage());
        var retained=original.retainingVerifiedAncestry(List.of(bridge));
        var changed=new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements.subList(0,2),Set.of());
        assertThrows(IllegalArgumentException.class,()->retained.retainingVerifiedAncestry(List.of(changed)));
    }
    @Test void boundEndpointsAndAcknowledgementsMustMatchTheProvenPrefix() {
        var f=new V53SelectionFixture(3,"REPLACE",5);var original=f.capsule.verify();var bridge=f.bridge(1,5);
        var fields=new TreeMap<>(bridge.statement.value());fields.put("applicationAfter","a".repeat(64));
        var changed=new MembershipSelection.Bridge(decode(encode("records","CHECKPOINT",fields),"records","CHECKPOINT"),bridge.acknowledgements,bridge.owned);
        assertEquals("ancestry exact frozen endpoints",assertThrows(IllegalArgumentException.class,()->original.retainingVerifiedAncestry(List.of(changed))).getMessage());
        var other=new V53SelectionFixture(4,"REPLACE",5).bridge(1,5);
        assertThrows(IllegalArgumentException.class,()->original.retainingVerifiedAncestry(List.of(other)));
    }
    @Test void duplicateAndExcessiveBridgesRemainRejected() {
        var f=new V53SelectionFixture(3,"REPLACE",5);var original=f.capsule.verify();var bridge=f.bridge(1,5);
        assertEquals("duplicate generation ancestry",assertThrows(IllegalArgumentException.class,()->original.retainingVerifiedAncestry(List.of(bridge,bridge))).getMessage());
        assertEquals("generation ancestry count",assertThrows(IllegalArgumentException.class,()->original.retainingVerifiedAncestry(Collections.nCopies(7,bridge))).getMessage());
    }
    @Test void historicalAttachmentPreservesTheOriginalGrantAndRejectsPacketChanges() {
        var f=new V53SelectionFixture(3,"REPLACE",5);var source=f.source("node-1");var bridge=f.bridge(1,5);
        var attached=source.withVerifiedHistory(source.capsule.retainingVerifiedAncestry(List.of(bridge)));
        assertSame(source.basis,attached.basis);assertSame(source.owner,attached.owner);
        assertSame(source.accepted,attached.accepted);assertSame(source.entry,attached.entry);assertEquals(source.reference(),attached.reference());
        var other=new V53SelectionFixture(3,"REPLACE",5);byte[] extra=new byte[]{1,2,3};other.capsule.objects.put(hash(extra),extra);var changed=other.capsule.verify();
        assertTrue(source.capsule.sameProvenPrefix(changed.packet));
        assertEquals("source history changed original packet",assertThrows(IllegalArgumentException.class,()->source.withVerifiedHistory(changed)).getMessage());
    }
    @Test void materializationKeepsAuthenticatedSupplementalHistoryOutsideThePacket() {
        var f=new V53SelectionFixture(3,"REPLACE",5);var original=f.capsule.verify();var bridge=f.bridge(1,5);
        assertFalse(original.packet.objectNames().contains(bridge.statement.digest()));
        var historical=original.retainingVerifiedAncestry(List.of(bridge));var raw=new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements,Set.of());
        var materialized=historical.materialization(original.packet,f.capsule.source.images,List.of(raw));
        materialized.verifyAncestry(MembershipGenerationPlan.ancestry(List.of(raw)),List.of(lower(raw)));
        assertThrows(IllegalArgumentException.class,()->original.materialization(original.packet,f.capsule.source.images,List.of(raw)));
    }
}
