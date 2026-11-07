package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.CleanupMode;
import org.junit.jupiter.api.io.TempDir;

/** Whole maximum-image REMOVE history. Use only the capacity-admitted entry. */
class V53MaximumQueueQualification {
    @TempDir(factory=V53MaximumNativeQualification.WorkspaceTemporaryDirectory.class,cleanup=CleanupMode.ON_SUCCESS) Path temp;
    @Test void maximumImageFinishesAfterJointQueuePressure()throws Exception {
        var history=new V53QueueCompletionQualification();history.temp=temp;history.maximumImage();
    }
}
