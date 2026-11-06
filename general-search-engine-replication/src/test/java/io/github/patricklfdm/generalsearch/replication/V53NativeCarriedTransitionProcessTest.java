package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** One admitted REMOVE, whole-group death during its inherited command, original disks. */
class V53NativeCarriedTransitionProcessTest {
    @TempDir Path temp;
    private void run(String kind,String cut,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;fixture.run(cut,mode,kind);
    }
    @Test void haltIntentAcceptRename()throws Exception {run("INTENT","ACCEPT_RENAMED","halt");}
    @Test void killIntentAcceptRename()throws Exception {run("INTENT","ACCEPT_RENAMED","kill");}
    @Test void haltIntentProofRename()throws Exception {run("INTENT","PROOF_RENAMED","halt");}
    @Test void killIntentProofRename()throws Exception {run("INTENT","PROOF_RENAMED","kill");}
    @Test void haltFinalAcceptRename()throws Exception {run("FINAL","ACCEPT_RENAMED","halt");}
    @Test void killFinalAcceptRename()throws Exception {run("FINAL","ACCEPT_RENAMED","kill");}
    @Test void haltFinalProofRename()throws Exception {run("FINAL","PROOF_RENAMED","halt");}
    @Test void killFinalProofRename()throws Exception {run("FINAL","PROOF_RENAMED","kill");}
}
