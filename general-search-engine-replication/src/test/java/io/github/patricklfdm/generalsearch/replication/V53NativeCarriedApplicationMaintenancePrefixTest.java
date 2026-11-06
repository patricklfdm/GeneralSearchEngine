package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Both original process lifetimes with application and maintenance file captures. */
class V53NativeCarriedApplicationMaintenancePrefixTest {
    @TempDir Path temp;
    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;fixture.runApplicationMaintenance(mode,kind);
    }
    @Test void haltIntentApplicationMaintenancePrefixes()throws Exception {run("INTENT","halt");}
    @Test void killIntentApplicationMaintenancePrefixes()throws Exception {run("INTENT","kill");}
    @Test void haltFinalApplicationMaintenancePrefixes()throws Exception {run("FINAL","halt");}
    @Test void killFinalApplicationMaintenancePrefixes()throws Exception {run("FINAL","kill");}
}
