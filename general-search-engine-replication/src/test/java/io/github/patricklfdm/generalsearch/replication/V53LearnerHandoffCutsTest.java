package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Synchronous write/force cuts. This class is not halt/SIGKILL qualification. */
class V53LearnerHandoffCutsTest {
    @TempDir Path temp;
    @Test void onlyCompleteOriginalHandoffsCanResume()throws Exception {
        for(String point:List.of("LEARNER_HEAD_CANDIDATE_CREATED","LEARNER_HEAD_CANDIDATE_PREFIX_WRITTEN",
                "LEARNER_HEAD_CANDIDATE_FORCED","LEARNER_HEAD_RENAMED","LEARNER_HEAD_ACTIVE_FORCED","LEARNER_HEAD_BEFORE_RETURN")) {
            var h=new V53LearnerSuccessorTest();h.temp=temp;try(var f=h.fixture(3,"ADD")) {
                var reached=new AtomicBoolean();
                try(var prior=f.prepare(e->{})) {
                    var installed=h.install(f,prior.retainGeneration(),e->{if(e.equals(point)){reached.set(true);throw new IOException(e);}});
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,1),f.captured,f.config,e->{})) {
                        assertThrows(IOException.class,typed::promoteSuccessor);assertTrue(reached.get());
                    }
                }
                if(point.equals("LEARNER_HEAD_CANDIDATE_CREATED") || point.equals("LEARNER_HEAD_CANDIDATE_PREFIX_WRITTEN")) {
                    var before=V53ReplayFilesTest.files(f.base);var error=assertThrows(RuntimeException.class,f::reopen);
                    assertTrue(error instanceof IllegalArgumentException || error instanceof ReplicationException);assertEquals(before,V53ReplayFilesTest.files(f.base));
                }else {
                    f.reopen();
                    if(point.equals("LEARNER_HEAD_CANDIDATE_FORCED")) {
                        try(var prior=f.prepare(e->{});var typed=MembershipLearnerMaterialization.prepare(
                                MembershipLearnerPreparation.from(prior.retainGeneration().successor(),1),f.captured,f.config,e->{})){typed.promoteSuccessor().source();}
                    }else f.store.promotedSuccessor().source();
                }
            }
        }
    }
}
