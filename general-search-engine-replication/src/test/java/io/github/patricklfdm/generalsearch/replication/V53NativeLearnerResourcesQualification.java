package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Same complete native READY/CANCEL history, with original learner ownership
 * checkpoints through first close and cold reopen. */
class V53NativeLearnerResourcesQualification {
    @TempDir Path temp;
    V53LearnerCancellationQualification fixture;
    @Test void admittedCancellationAndColdReopenPreserveOriginalResourceLifetimes()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-native-learner-resources/run-"+UUID.randomUUID()));
        System.out.println("v53NativeLearnerResourcesEvidence="+root.toAbsolutePath());
        run(root);
    }
    void run(Path root)throws Exception {
        var capture=new V53LearnerResourceCapture(root.resolve("resources"));
        fixture=new V53LearnerCancellationQualification();fixture.temp=temp;boolean success=false;
        try {fixture.run(capture);success=true;}
        finally {
            capture.finish(fixture.retainedRaw,success);
            if(fixture.retainedRaw!=null && Files.exists(fixture.retainedRaw))Files.move(fixture.retainedRaw,root.resolve("original"));
        }
    }
}
