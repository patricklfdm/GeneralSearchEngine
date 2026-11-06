package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Explicit long-running composition entry; retained for final-source qualification. */
class V53NativeCarriedReplayPrefixProcessTest {
    @TempDir Path temp;
    @Test void finalProofKill()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("PROOF_RENAMED","kill","FINAL",true,true,true,true,true,true,true,true);
    }
    @Test void intentAcceptHalt()throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("ACCEPT_RENAMED","halt","INTENT",true,true,true,true,true,true,true,true);
    }
    @Test void intentAcceptKill()throws Exception {run("INTENT","ACCEPT_RENAMED","kill");}
    @Test void intentProofHalt()throws Exception {run("INTENT","PROOF_RENAMED","halt");}
    @Test void intentProofKill()throws Exception {run("INTENT","PROOF_RENAMED","kill");}
    @Test void finalAcceptHalt()throws Exception {run("FINAL","ACCEPT_RENAMED","halt");}
    @Test void finalAcceptKill()throws Exception {run("FINAL","ACCEPT_RENAMED","kill");}
    @Test void finalProofHalt()throws Exception {run("FINAL","PROOF_RENAMED","halt");}
    private void run(String kind,String cut,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run(cut,mode,kind,true,true,true,true,true,true,true,true);
    }
}
