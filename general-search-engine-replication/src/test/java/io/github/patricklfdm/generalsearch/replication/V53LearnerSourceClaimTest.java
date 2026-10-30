package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import io.github.patricklfdm.generalsearch.replication.MembershipResources.Lease;

class V53LearnerSourceClaimTest {
    @Test void sourceRetentionKeepsAllBytesChargedWithoutSpendingAGeneration() {
        var r=new MembershipResources(HEADROOM+Unit.LEARNER.bytes,Unit.LEARNER.bytes,1024);
        try(var original=r.reserve(Unit.LEARNER,"original",Unit.LEARNER.bytes)) {
            var before=r.usage();
            try(var claim=original.prepareSource("retained")) {
                claim.requireSource(original);assertEquals(before.metadata(),r.usage().metadata());assertEquals(before.staging(),r.usage().staging());
                assertEquals(1,r.usage().counts().get(Unit.LEARNER));assertEquals(1,r.usage().counts().get(Unit.SOURCE));
                assertFalse(r.usage().counts().containsKey(Unit.GENERATION));
                assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.LEARNER,"second",1));
                assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.SOURCE,"retained",1));
                assertThrows(IllegalArgumentException.class,()->original.prepareGeneration("competing"));
                assertThrows(IllegalArgumentException.class,()->original.prepareSource("duplicate"));
                assertThrows(IllegalArgumentException.class,()->r.requireCompleteStorage(Set.of(original)));
                assertThrows(IllegalArgumentException.class,()->r.transferStorage(Map.of(original,"moved")));
                claim.commit();assertEquals(before.metadata(),r.usage().metadata());assertEquals(before.staging(),r.usage().staging());
                assertEquals(before.leases(),r.usage().leases());assertFalse(r.usage().counts().containsKey(Unit.LEARNER));
                assertThrows(IllegalArgumentException.class,claim::commit);
                // Retention cannot hide the original staging bytes to admit another image.
                assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.APPLICATION,"overfull",1));
                r.requireCompleteStorage(Set.of(original));
            }
        }
        assertEquals(0,r.usage().leases());assertEquals(0,r.usage().metadata());assertEquals(0,r.usage().staging());
    }
    @Test void sourceClaimReservesTheSixthSlotBeforeConcurrentAcquisition() {
        var r=new MembershipResources(512*MIB);var occupied=new ArrayList<Lease>();
        try(var original=r.reserve(Unit.LEARNER,"original",10)) {
            for(int i=0;i<5;i++)occupied.add(r.reserve(Unit.SOURCE,"s"+i,10));
            try(var claim=original.prepareSource("retained")) {
                assertEquals(6,r.usage().counts().get(Unit.SOURCE));
                assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.SOURCE,"seventh",1));
                claim.commit();
                try(var next=r.reserve(Unit.LEARNER,"next",10);var first=r.reserve(Unit.GENERATION,"first",10);var second=r.reserve(Unit.GENERATION,"second",10)) {
                    assertEquals(2,r.usage().counts().get(Unit.GENERATION));assertEquals(6,r.usage().counts().get(Unit.SOURCE));
                    var before=r.usage();assertThrows(IllegalArgumentException.class,()->next.prepareSource("seventh"));assertEquals(before,r.usage());
                }
            }
        }finally{occupied.forEach(Lease::close);}
        assertEquals(0,r.usage().leases());
    }
    @Test void cancelledForeignAndRevokedClaimsNeverLoseTheOriginalCharge() {
        var r=new MembershipResources(512*MIB);var original=r.reserve(Unit.LEARNER,"original",10);var before=r.usage();
        original.prepareSource("aborted").close();assertEquals(before,r.usage());
        try(var other=new MembershipResources(512*MIB).reserve(Unit.LEARNER,"other",10);var claim=original.prepareSource("retained")) {
            assertThrows(IllegalArgumentException.class,()->claim.requireSource(other));
            original.close();assertEquals(0,r.usage().leases());assertThrows(IllegalArgumentException.class,claim::commit);
        }
        assertThrows(IllegalArgumentException.class,()->original.prepareSource("closed"));
        try(var source=r.reserve(Unit.SOURCE,"already-source",10);var receiver=r.reserve(Unit.LEARNER,"receiving",10);var generation=receiver.prepareGeneration("selecting")) {
            assertThrows(IllegalArgumentException.class,()->source.prepareSource("wrong-kind"));
            assertThrows(IllegalArgumentException.class,()->receiver.prepareSource("competing"));
        }
        assertEquals(0,r.usage().leases());
    }
}
