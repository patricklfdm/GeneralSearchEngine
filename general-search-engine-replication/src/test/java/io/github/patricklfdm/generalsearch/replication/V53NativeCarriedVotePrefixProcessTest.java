package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Explicit long-running composition entry; retained for final-source qualification. */
class V53NativeCarriedVotePrefixProcessTest {
    @TempDir Path temp;
    @Test void finalProofKill()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("PROOF_RENAMED","kill","FINAL",true,true,true,true,true);
    }
    @Test void intentAcceptHalt()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("ACCEPT_RENAMED","halt","INTENT",true,true,true,true,true);
    }
}
