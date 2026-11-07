package io.github.patricklfdm.generalsearch.replication;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/** Configuration rejection only; never executes the long native qualification. */
class V53BackupJoiningQualificationTest {
    @Test void everyOriginalObservationIsRequiredBeforeStartingTheHistory() {
        Map<String,String> before=new HashMap<>();
        var keys=new java.util.ArrayList<>(V53BackupJoiningQualification.OBSERVATIONS);keys.add("v53.joining.sourceFault");
        for(String key:keys)before.put(key,System.getProperty(key));
        try {
            for(String key:V53BackupJoiningQualification.OBSERVATIONS)System.setProperty(key,"true");
            System.clearProperty("v53.joining.sourceFault");V53BackupJoiningQualification.checkConfiguration();
            for(String key:V53BackupJoiningQualification.OBSERVATIONS) {
                for(String value:new String[]{null,"false","yes","1"}) {
                    if(value==null)System.clearProperty(key);else System.setProperty(key,value);
                    assertThrows(AssertionError.class,V53BackupJoiningQualification::checkConfiguration,key);
                }
                System.setProperty(key,"true");
            }
            System.setProperty("v53.joining.sourceFault","CHUNK");
            assertThrows(AssertionError.class,V53BackupJoiningQualification::checkConfiguration);
        }finally {
            for(String key:keys) {
                String value=before.get(key);if(value==null)System.clearProperty(key);else System.setProperty(key,value);
            }
        }
    }
}
