package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Configuration components only. Never invokes the maximum native history. */
class V53MaximumNativeEntryTest {
    @TempDir(factory=V53MaximumNativeQualification.WorkspaceTemporaryDirectory.class) Path temp;
    @Test void junitPrivateStorageUsesTheWorkspaceVolume()throws Exception {
        Path root=Path.of("target/v53-maximum-native-work").toRealPath();
        assertEquals(root,temp.toRealPath().getParent());
        assertEquals(Files.getFileStore(root),Files.getFileStore(temp));
        Path member=temp.resolve("replica-member");Files.writeString(member,"private native work");
        assertEquals("private native work",Files.readString(member));
    }
    private void configured(Runnable action) {
        var keys=new ArrayList<>(V53BackupJoiningQualification.OBSERVATIONS);keys.add("v53.joining.sourceFault");
        var previous=new HashMap<String,String>();for(String key:keys)previous.put(key,System.getProperty(key));
        try {
            for(String key:V53BackupJoiningQualification.OBSERVATIONS)System.setProperty(key,"true");
            System.clearProperty("v53.joining.sourceFault");action.run();
        }finally {for(String key:keys){String value=previous.get(key);if(value==null)System.clearProperty(key);else System.setProperty(key,value);}}
    }
    @Test void maximumEntryRequiresEveryExistingCompleteObservation() {
        configured(()->{
            V53MaximumNativeQualification.checkConfiguration();
            for(String key:V53BackupJoiningQualification.OBSERVATIONS) {
                System.clearProperty(key);assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration,key);
                System.setProperty(key,"true");
            }
        });
    }
    @Test void maximumEntryDoesNotAcceptAnInjectedSourceFault() {
        configured(()->{
            System.setProperty("v53.joining.sourceFault","CHUNK");
            assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration);
        });
    }
}
