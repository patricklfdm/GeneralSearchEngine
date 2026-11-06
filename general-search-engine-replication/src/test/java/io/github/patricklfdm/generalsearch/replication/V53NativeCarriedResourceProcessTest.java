package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Original carried histories plus actual per-JVM resource observations. */
class V53NativeCarriedResourceProcessTest {
    @TempDir Path temp;
    @Test void killFinalProofRenameObserved()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("PROOF_RENAMED","kill","FINAL",true);
    }
    @Test void haltIntentAcceptRenameObserved()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("ACCEPT_RENAMED","halt","INTENT",true);
    }
}
