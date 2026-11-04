package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;

/** One complete native history per ordinal/cut. No synthetic disk repair,
 * partial file truncation, injected transport replies or process-death claim. */
@EnabledIfSystemProperty(named="v53.native.partial.joint",matches=".+")
class V53NativePartialJointFloorTest {
    @TempDir Path temp;

    @Test void originalPartialCopyResumesBeforeFinalAndStableBarrier()throws Exception {
        String value=System.getProperty("v53.native.partial.joint");
        String[] fields=value.split(",",-1);
        if(fields.length!=2 || !fields[0].matches("[1-4]"))
            throw new IllegalArgumentException("native joint floor exact case");
        var cut=new V53JointFloorRecoveryTest.WriterCut(Integer.parseInt(fields[0]),fields[1]);
        var fixture=new V53JointFloorRecoveryTest();fixture.temp=temp;fixture.run(cut);
    }
}
