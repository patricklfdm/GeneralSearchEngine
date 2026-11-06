package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Original resource-observed child lifetimes with writer-held file prefixes. */
class V53NativeCarriedPrefixProcessTest {
    @TempDir Path temp;
    @Test void killFinalProofRenamePrefixes()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("PROOF_RENAMED","kill","FINAL",true,true);
    }
    @Test void haltIntentAcceptRenamePrefixes()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("ACCEPT_RENAMED","halt","INTENT",true,true);
    }
}
