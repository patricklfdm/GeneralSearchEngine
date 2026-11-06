package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** One original two-JVM history: interrupted application, then old-end retirement. */
class V53NativeCarriedApplicationRecoveryPrefixTest {
    @TempDir Path temp;
    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;fixture.runApplicationRecovery(mode,kind);
    }
    @Test void haltIntentApplicationRecoveryPrefixes()throws Exception {run("INTENT","halt");}
    @Test void killIntentApplicationRecoveryPrefixes()throws Exception {run("INTENT","kill");}
    @Test void haltFinalApplicationRecoveryPrefixes()throws Exception {run("FINAL","halt");}
    @Test void killFinalApplicationRecoveryPrefixes()throws Exception {run("FINAL","kill");}
}
