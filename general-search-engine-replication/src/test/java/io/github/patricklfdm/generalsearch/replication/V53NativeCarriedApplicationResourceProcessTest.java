package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Application-ACK group death with original per-owner resource observations. */
class V53NativeCarriedApplicationResourceProcessTest {
    @TempDir Path temp;

    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("APPLY_ACK_DIRECTORY_FORCED",mode,kind,true);
    }

    @Test void haltIntentApplicationAckObserved()throws Exception {run("INTENT","halt");}
    @Test void killIntentApplicationAckObserved()throws Exception {run("INTENT","kill");}
    @Test void haltFinalApplicationAckObserved()throws Exception {run("FINAL","halt");}
    @Test void killFinalApplicationAckObserved()throws Exception {run("FINAL","kill");}
}
