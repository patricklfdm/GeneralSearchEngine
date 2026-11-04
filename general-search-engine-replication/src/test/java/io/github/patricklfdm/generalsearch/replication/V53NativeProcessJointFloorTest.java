package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;

/** One whole original history. The worker dies; the required old voter returns
 * from the same roots and continues through FINAL and the stable BARRIER. */
@EnabledIfSystemProperty(named="v53.native.process.joint",matches=".+")
class V53NativeProcessJointFloorTest {
    @TempDir Path temp;

    @Test void originalProcessDeathResumesBeforeFinalAndStableBarrier()throws Exception {
        String[] fields=System.getProperty("v53.native.process.joint").split(",",-1);
        if(fields.length!=3 || !fields[0].matches("[1-4]"))throw new IllegalArgumentException("native process joint exact case");
        var cut=new V53JointFloorRecoveryTest.WriterCut(Integer.parseInt(fields[0]),fields[1]);
        var fixture=new V53JointFloorRecoveryTest();fixture.temp=temp;fixture.runProcess(cut,fields[2]);
    }
}
