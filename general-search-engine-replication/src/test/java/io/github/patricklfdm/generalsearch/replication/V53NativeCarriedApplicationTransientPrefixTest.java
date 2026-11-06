package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Both original process lifetimes with application and maintenance file captures. */
class V53NativeCarriedApplicationTransientPrefixTest {
    @TempDir Path temp;
    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;fixture.runApplicationTransients(mode,kind);
    }
    @Test void haltIntentApplicationTransientPrefixes()throws Exception {run("INTENT","halt");}
    @Test void killIntentApplicationTransientPrefixes()throws Exception {run("INTENT","kill");}
    @Test void haltFinalApplicationTransientPrefixes()throws Exception {run("FINAL","halt");}
    @Test void killFinalApplicationTransientPrefixes()throws Exception {run("FINAL","kill");}
}
