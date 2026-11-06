package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Original context command applied, whole-group death before publication, original disks. */
class V53NativeCarriedApplicationProcessTest {
    @TempDir Path temp;
    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;
        fixture.run("APPLY_ACK_DIRECTORY_FORCED",mode,kind);
    }
    @Test void haltIntentApplicationAck()throws Exception {run("INTENT","halt");}
    @Test void killIntentApplicationAck()throws Exception {run("INTENT","kill");}
    @Test void haltFinalApplicationAck()throws Exception {run("FINAL","halt");}
    @Test void killFinalApplicationAck()throws Exception {run("FINAL","kill");}
}
