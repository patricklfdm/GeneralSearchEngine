package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** One native PREPARE 1–6 history; never split revisions across hosted workers.
 * An executed Java PASS still needs original wire/physical replay qualification. */
class V53LearnerAlternationNetworkTest {
    @TempDir Path temp;
    @Test void nativeSixRevisionsAlternateFixedSlotsAndColdReopenWithinOneReservation()throws Exception {
        var history=new V53CurrentHeadNetworkTest();history.temp=temp;history.run(true,true,true);
    }
}
