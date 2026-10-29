package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53JoinedNativeColdTest {
    @TempDir Path temp;
    @Test void originalColdRetirementTransfersItsRealLockGroupAndRestoredReservations()throws Exception {
        var h=new V53LearnerJoinedAdmissionTest();h.temp=temp;
        try(var f=h.fixture()) {
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})){retired.check();}
            }
            assertEquals(0,f.local.source.client.usage().leases());
            try(var retired=MembershipLearnerJoinedRetirement.recover(f.local.summary,f.local.source.client,f.local.captured,f.local.config,e->{})) {
                var before=f.local.source.client.usage();
                try(var owner=MembershipGrantJournal.openJoined(retired,f.local.captured,f.local.config,e->{
                    if(e.equals("JOINED_NATIVE_TRANSFERRED"))assertDoesNotThrow(()->new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock")));
                })) {
                    assertTrue(f.local.source.client.usage().staging()<before.staging());
                    retired.close();assertThrows(Exception.class,retired::check);
                    new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock"));
                    var id=f.local.config.localIdentity();
                    assertEquals("BASIS",owner.prepareCurrent(Map.of("counter",owner.reserveCounter(),"proposer",id.nodeId().value(),"incarnation",id.storageId().toString())).kind());
                }
            }
            assertEquals(0,f.local.source.client.usage().leases());
            try(var owner=MembershipGrantJournal.reopenJoined(f.local.summary,f.local.source.client,f.local.captured,f.local.config,e->{})) {
                assertTrue(owner.originalBasis().isPresent());
            }
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
}
