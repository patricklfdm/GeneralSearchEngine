package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Real filesystem/TCP/typed preparation, with an independent process testing
 * exclusion after inspections and forces. Historical quorum fixtures do not
 * qualify native joined-member voting. */
class V53LearnerInspectionOwnershipTest {
    @TempDir Path temp;
    @Test void initialHeadIntentAndDormantStageKeepOriginalLocks()throws Exception {exercise(false);}
    @Test void promotedHeadRetirementIntentAndDormantStageKeepOriginalLocks()throws Exception {exercise(true);}
    private void exercise(boolean promoted)throws Exception {
        var helper=new V53LearnerIntentTest();helper.temp=temp;var probe=new V53MembershipOwnershipTest();
        try(var f=helper.fixture("JOINT",3,"ADD",promoted)) {
            var locks=new ArrayList<Path>();locks.add(f.local.source.request.replicaDirectory().resolve("replica.lock"));
            locks.add(f.local.source.request.operationDirectory().resolve("operation.lock"));
            Path typed=promoted?MembershipLearnerSuccessor.typedDirectory(f.local.summary):f.local.typed();
            if(promoted)locks.add(MembershipLearnerSuccessor.directory(f.local.summary).resolve(MembershipLearnerSuccessor.LOCK));
            locks.add(typed.resolve("preparation.lock"));probe.probe(locks.toArray(Path[]::new));
            try(var intent=V53LearnerIntentTest.retain(f,e->{})) {
                Path source=MembershipLearnerIntent.directory(f.local.summary).resolve("source");
                locks.add(source.resolve("source.gscp"));
                try(var paths=Files.list(source)){locks.addAll(paths.filter(p->p.toString().endsWith(".image")).toList());}
                intent.forced().check();probe.probe(locks.toArray(Path[]::new));
                try(var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{})) {
                    stage.readyCapability().check();probe.probe(locks.toArray(Path[]::new));
                }
                intent.forced().check();probe.probe(locks.toArray(Path[]::new));
            }
        }
    }
}
