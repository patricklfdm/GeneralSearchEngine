package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Interrupted application bytes, with the complete original resource history. */
class V53NativeCarriedApplicationPrefixProcessTest {
    @TempDir Path temp;
    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;fixture.runApplicationCut(mode,kind);
    }
    @Test void haltIntentApplicationPrefixes()throws Exception {run("INTENT","halt");}
    @Test void killIntentApplicationPrefixes()throws Exception {run("INTENT","kill");}
    @Test void haltFinalApplicationPrefixes()throws Exception {run("FINAL","halt");}
    @Test void killFinalApplicationPrefixes()throws Exception {run("FINAL","kill");}
}
