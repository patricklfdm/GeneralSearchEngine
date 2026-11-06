package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Original crash/reopen histories with complete maintenance file prefixes. */
class V53NativeCarriedFloorPrefixProcessTest {
    @TempDir Path temp;
    @Test void killFinalProofRenameFloorPrefixes()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("PROOF_RENAMED","kill","FINAL",true,true,true);
    }
    @Test void haltIntentAcceptRenameFloorPrefixes()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("ACCEPT_RENAMED","halt","INTENT",true,true,true);
    }
}
