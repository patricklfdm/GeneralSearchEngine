package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** A whole native PREPARE 1/2/3, install and original cold-reopen history.
 * Kept as an independent final hosted qualification unit. */
class V53LearnerSlotNetworkTest {
    @TempDir Path temp;
    @Test void nativeThirdRevisionInstallsAndReopensWhileSecondRemainsCurrent()throws Exception {
        var history=new V53CurrentHeadNetworkTest();history.temp=temp;history.run(true);
    }
}
