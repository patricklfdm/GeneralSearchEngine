package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53QueueEvidenceBudgetTest {
    @Test void legacyProfilesKeepTheirExistingLimit() {
        for(var source:MembershipBootstrapSource.values())
            assertEquals(V53EvidenceArray.WIRE_BYTES,V53NativeDispatchTest.admitWireLimit(source,V53EvidenceArray.WIRE_BYTES));
    }
    @Test void onlyTheExplicitBackupProfileCanUseTheQueueObservationEnvelope() {
        assertEquals(256*1024*1024,V53NativeDispatchTest.admitWireLimit(MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,256*1024*1024));
        assertThrows(IllegalArgumentException.class,()->V53NativeDispatchTest.admitWireLimit(MembershipBootstrapSource.EMPTY,256*1024*1024));
    }
    @Test void arbitraryLoweredOrRaisedLimitsCannotBeAdmitted() {
        for(var source:MembershipBootstrapSource.values())for(int requested:new int[]{0,-1,4096,64*1024*1024-1,256*1024*1024+1,Integer.MAX_VALUE})
            assertThrows(IllegalArgumentException.class,()->V53NativeDispatchTest.admitWireLimit(source,requested));
    }
    @Test void segmentedSelectionRequiresBackupAndCannotReinterpretAJsonLimit() {
        var layout=V53WireArchive.Layout.SEGMENTED_BACKUP;
        assertEquals(V53EvidenceArray.WIRE_BYTES,V53NativeDispatchTest.admitWireLimit(
                MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,V53EvidenceArray.WIRE_BYTES,layout));
        assertThrows(IllegalArgumentException.class,()->V53NativeDispatchTest.admitWireLimit(MembershipBootstrapSource.EMPTY,V53EvidenceArray.WIRE_BYTES,layout));
        assertThrows(IllegalArgumentException.class,()->V53NativeDispatchTest.admitWireLimit(MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,256*1024*1024,layout));
    }
}
