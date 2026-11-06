package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53ApplicationMaintenanceCaptureTest {
    @Test void onlyWholeMaintenanceOrOriginalResourceLayoutIsAdmitted() {
        for(String kind:new String[]{"INTENT","FINAL"})for(boolean first:new boolean[]{false,true}) {
            int life=first?1:2;
            for(int count:new int[]{5,8})assertDoesNotThrow(()->V53NativeCarriedProcessWorker.applicationCaptureCase(
                    first,!first,life,kind,"APPLY_ACK_DIRECTORY_FORCED",count));
            for(int count:new int[]{4,6,7,9,10,11,12})assertThrows(IllegalArgumentException.class,
                    ()->V53NativeCarriedProcessWorker.applicationCaptureCase(first,!first,life,kind,"APPLY_ACK_DIRECTORY_FORCED",count));
        }
    }
    @Test void wrongLifetimeKindCutOrTwoApplicationSidesRefuse() {
        for(boolean first:new boolean[]{false,true}) {
            assertThrows(IllegalArgumentException.class,()->V53NativeCarriedProcessWorker.applicationCaptureCase(
                    first,!first,first?2:1,"INTENT","APPLY_ACK_DIRECTORY_FORCED",8));
            for(String kind:new String[]{"DATA","other"})assertThrows(IllegalArgumentException.class,
                    ()->V53NativeCarriedProcessWorker.applicationCaptureCase(first,!first,first?1:2,kind,"APPLY_ACK_DIRECTORY_FORCED",8));
            for(String cut:new String[]{"ACCEPT_RENAMED","PROOF_RENAMED"})assertThrows(IllegalArgumentException.class,
                    ()->V53NativeCarriedProcessWorker.applicationCaptureCase(first,!first,first?1:2,"FINAL",cut,8));
        }
        assertThrows(IllegalArgumentException.class,()->V53NativeCarriedProcessWorker.applicationCaptureCase(true,true,1,"INTENT","APPLY_ACK_DIRECTORY_FORCED",8));
    }
    @Test void ordinaryProcessEntriesKeepTheirOwnValidation() {
        assertDoesNotThrow(()->V53NativeCarriedProcessWorker.applicationCaptureCase(false,false,1,"DATA","PROOF_RENAMED",12));
    }
}
