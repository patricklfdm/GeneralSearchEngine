package io.github.patricklfdm.generalsearch.replication;

import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53LearnerBytePressureTest {
    @Test void limitsUseActualSourceMembersAndKeepTheTypedReservationDistinctFromPhysicalBytes() {
        var prepared=Map.of("source.gscp",new byte[80],"first.image",new byte[13]);
        var terminal=Map.of("source.gscp",new byte[100],"generation.gsr",new byte[33],"last.image",new byte[17]);
        long base=64*MembershipResources.MIB+163;
        assertEquals(base,V53NativeLearnerBytePressureQualification.steady(prepared,terminal));
        assertEquals(base,V53NativeLearnerBytePressureQualification.limit("pool-full",base,100,17));
        assertEquals(base+99,V53NativeLearnerBytePressureQualification.limit("packet-short",base,100,17));
        assertEquals(base+117,V53NativeLearnerBytePressureQualification.limit("source-exact",base,100,17));
        assertThrows(IllegalArgumentException.class,()->V53NativeLearnerBytePressureQualification.limit("other",base,100,17));
    }
}
