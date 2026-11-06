package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Complete native histories; optional receiver refusal never replaces a voter. */
class V53NativeApplicationRefusalTest {
    @TempDir Path temp;
    private void run(String kind,String mode)throws Exception {
        var fixture=new V53NativeCarriedProcessTest();fixture.temp=temp;fixture.runApplicationRefusals(mode,kind);
    }
    @Test void haltIntentWithSourceCountRefusal()throws Exception {run("INTENT","halt");}
    @Test void killFinalWithSourceCountRefusal()throws Exception {run("FINAL","kill");}
}
