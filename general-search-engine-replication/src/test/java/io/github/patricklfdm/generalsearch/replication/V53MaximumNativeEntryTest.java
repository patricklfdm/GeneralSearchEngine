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
        keys.add(V53MaximumNativeQualification.REQUEST_TIMEOUT_PROPERTY);keys.add(V53MaximumNativeQualification.ROUND_PROPERTY);
        var previous=new HashMap<String,String>();for(String key:keys)previous.put(key,System.getProperty(key));
        try {
            for(String key:V53BackupJoiningQualification.OBSERVATIONS)System.setProperty(key,"true");
            System.setProperty(V53MaximumNativeQualification.REQUEST_TIMEOUT_PROPERTY,"300000");
            System.setProperty(V53MaximumNativeQualification.ROUND_PROPERTY,"72000");
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
    @Test void maximumWaitIsExplicitAndOnlyTheRequestWaitDiffers() {
        configured(()->{
            assertEquals(30_000,V53RoundDriverTest.controlBounds().requestTimeoutMillis());
            assertEquals(V53RoundDriverTest.controlBounds(300_000),V53MaximumNativeQualification.checkConfiguration());
            for(String timeout:List.of("30000","600000","")) {
                System.setProperty(V53MaximumNativeQualification.REQUEST_TIMEOUT_PROPERTY,timeout);
                assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration);
            }
            System.clearProperty(V53MaximumNativeQualification.REQUEST_TIMEOUT_PROPERTY);
            assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration);
        });
    }
    @Test void maximumRoundRequiresTwentyHoursAndNeverRenewsAChildBudget()throws Exception {
        configured(()->{
            for(String value:List.of("2400","43200","86400","")) {
                System.setProperty(V53MaximumNativeQualification.ROUND_PROPERTY,value);
                assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration);
            }
            System.clearProperty(V53MaximumNativeQualification.ROUND_PROPERTY);
            assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration);
        });
        var annotation=V53MaximumNativeQualification.class.getDeclaredMethod("maximumImageCompletesRequiredFourReplacement")
                .getAnnotation(org.junit.jupiter.api.Timeout.class);
        long limit=java.util.concurrent.TimeUnit.HOURS.toNanos(20);
        assertEquals(limit,annotation.unit().toNanos(annotation.value()));
        var max=new V53JoiningIntentExportTest.RunTiming(true,10);
        assertEquals(limit,max.remaining(10,100));
        assertEquals(1,max.remaining(10+limit-1,100));
        assertThrows(AssertionError.class,()->max.remaining(10+limit,100));
        assertThrows(AssertionError.class,()->max.remaining(9,100));
        assertEquals(100,new V53JoiningIntentExportTest.RunTiming(false,10).remaining(10+limit,100));
    }
    @Test void maximumEntryDoesNotAcceptAnInjectedSourceFault() {
        configured(()->{
            System.setProperty("v53.joining.sourceFault","CHUNK");
            assertThrows(AssertionError.class,V53MaximumNativeQualification::checkConfiguration);
        });
    }
}
