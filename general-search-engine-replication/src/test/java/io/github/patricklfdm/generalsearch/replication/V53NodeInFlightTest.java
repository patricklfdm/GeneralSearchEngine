package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** One whole original history per cut/mode; never replay a mutation after loss. */
class V53NodeInFlightTest {
    @TempDir Path temp;
    void run(String point,String mode)throws Exception {
        var history=new V53NodeProcessTest();history.temp=temp;history.run(mode,point);
    }
    @Test void haltAfterAccept()throws Exception{run("ACCEPT_PARENT_FORCED","halt");}
    @Test void killAfterAccept()throws Exception{run("ACCEPT_PARENT_FORCED","kill");}
    @Test void haltAfterProof()throws Exception{run("PROOF_PARENT_FORCED","halt");}
    @Test void killAfterProof()throws Exception{run("PROOF_PARENT_FORCED","kill");}
}
