package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** One continuous native reservation and PREPARE 1/2/3 history. Intended as an
 * independent hosted unit; compilation is not execution or physical replay. */
class V53LearnerSlotHeadNetworkTest {
    @TempDir Path temp;
    @Test void nativeThirdRevisionSelectsRetiresAndReopensWithoutTheOldSource()throws Exception {
        var history=new V53CurrentHeadNetworkTest();history.temp=temp;history.run(true,true);
    }
}
