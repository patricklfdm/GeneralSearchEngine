package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53LearnerGenerationClaimTest {
    @Test void countClaimPrecedesSelectionWithoutDuplicatingOrReleasingOriginalBytes() {
        var r=new MembershipResources(HEADROOM+Unit.LEARNER.bytes,Unit.LEARNER.bytes,1024);
        try(var original=r.reserve(Unit.LEARNER,"original",Unit.LEARNER.bytes)) {
            var before=r.usage();
            try(var claim=original.prepareGeneration("prepared")) {
                claim.requireSource(original);
                var foreign=new MembershipResources(512*MIB);
                try(var other=foreign.reserve(Unit.LEARNER,"original",Unit.LEARNER.bytes)) {
                    assertThrows(IllegalArgumentException.class,()->claim.requireSource(other));
                }
                assertEquals(before.metadata(),r.usage().metadata());assertEquals(before.staging(),r.usage().staging());
                assertEquals(1,r.usage().counts().get(Unit.LEARNER));assertEquals(1,r.usage().counts().get(Unit.GENERATION));
                assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.LEARNER,"second",1));
                assertThrows(IllegalArgumentException.class,()->original.prepareGeneration("duplicate"));
                claim.commit();assertEquals(before.metadata(),r.usage().metadata());assertEquals(0,r.usage().staging());
                assertFalse(r.usage().counts().containsKey(Unit.LEARNER));assertEquals(1,r.usage().counts().get(Unit.GENERATION));
                assertThrows(IllegalArgumentException.class,claim::commit);
                assertThrows(IllegalArgumentException.class,()->original.reserveStorage(Unit.LEARNER.bytes));
            }
        }
        assertEquals(0,r.usage().leases());assertEquals(0,r.usage().metadata());
    }
    @Test void outstandingClaimCannotBeStolenByAConcurrentReservation() {
        var r=new MembershipResources(512*MIB);
        try(var original=r.reserve(Unit.LEARNER,"original",10);var existing=r.reserve(Unit.GENERATION,"other",10);
                var claim=original.prepareGeneration("prepared")) {
            assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.GENERATION,"third",1));
            assertThrows(IllegalArgumentException.class,()->r.reserve(Unit.GENERATION,"prepared",1));
            claim.commit();assertEquals(2,r.usage().counts().get(Unit.GENERATION));
            try(var next=r.reserve(Unit.LEARNER,"next",10)){assertEquals(1,r.usage().counts().get(Unit.LEARNER));}
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void cancelledClaimPreservesReceivingOwnershipAndSourceCloseRevokesAClaim() {
        var r=new MembershipResources(512*MIB);var source=r.reserve(Unit.LEARNER,"original",10);var before=r.usage();
        source.prepareGeneration("cancelled").close();assertEquals(before,r.usage());
        var claim=source.prepareGeneration("prepared");source.close();assertEquals(0,r.usage().leases());
        assertThrows(IllegalArgumentException.class,claim::commit);claim.close();
        assertThrows(IllegalArgumentException.class,()->source.prepareGeneration("closed"));
    }
    @Test void fullGenerationCapacityAndWrongKindsRefuseWithoutAccountingChanges() {
        var r=new MembershipResources(512*MIB);
        try(var source=r.reserve(Unit.LEARNER,"original",10);var first=r.reserve(Unit.GENERATION,"first",10);var second=r.reserve(Unit.GENERATION,"second",10)) {
            var before=r.usage();assertThrows(IllegalArgumentException.class,()->source.prepareGeneration("third"));assertEquals(before,r.usage());
            assertThrows(IllegalArgumentException.class,()->first.prepareGeneration("wrong"));
        }
        assertEquals(0,r.usage().leases());
    }
}
