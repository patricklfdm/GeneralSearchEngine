package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Real process loss after atomic rename, before forcing the parent directory. */
class V53NodeRenameProcessTest {
    @TempDir Path temp;
    void run(String point,String mode)throws Exception {
        var history=new V53NodeProcessTest();history.temp=temp;history.run(mode,point);
    }
    @Test void haltAfterAcceptRename()throws Exception{run("ACCEPT_RENAMED","halt");}
    @Test void killAfterAcceptRename()throws Exception{run("ACCEPT_RENAMED","kill");}
    @Test void haltAfterProofRename()throws Exception{run("PROOF_RENAMED","halt");}
    @Test void killAfterProofRename()throws Exception{run("PROOF_RENAMED","kill");}
}
