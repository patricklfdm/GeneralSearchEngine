package io.github.patricklfdm.generalsearch.replication;

import java.io.RandomAccessFile;
import java.nio.file.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Sparse observation-envelope components; not valid maximum application images. */
class V53ReplicaCaptureLimitsTest {
    @TempDir Path temp;

    @Test void frozenResourceEnvelopeDoesNotChangeLegacyOrWholeOriginalLimits() {
        assertEquals(384L*1024*1024,MembershipResources.METADATA_LIMIT);
        assertEquals(7,MembershipResources.Unit.APPLICATION.count);
        assertEquals(64L*1024*1024,MembershipResources.Unit.APPLICATION.bytes);
        assertEquals(832L*1024*1024,V53CaptureFiles.SNAPSHOT_BYTES);
        assertEquals(256L*1024*1024,V53GrantCapture.MAXIMUM_BYTES);
        assertEquals(128L*1024*1024*1024,V53CaptureFiles.ORIGINAL_BYTES);
    }

    @Test void exactEnvelopeStreamsUnder32MiBHeapAndOneMoreByteFails()throws Exception {
        Path original=Files.createDirectory(temp.resolve("original"));
        for(int i=0;i<13;i++)try(var out=new RandomAccessFile(original.resolve("part-"+i).toFile(),"rw")) {
            out.setLength(64L*1024*1024);
        }
        Path log=temp.resolve("probe.log");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-Xmx32m","-XX:-UsePerfData","-cp",
                System.getProperty("java.class.path"),Probe.class.getName(),original.toString())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {assertTrue(process.waitFor(90,TimeUnit.SECONDS),"snapshot-envelope probe timeout");assertEquals(0,process.exitValue(),Files.readString(log));}
        finally {if(process.isAlive())process.destroyForcibly();}
        assertThrows(IllegalArgumentException.class,()->V53GrantCapture.inventory(original));
        Files.write(original.resolve("one-more"),new byte[]{1});
        assertEquals("capture byte capacity",assertThrows(IllegalArgumentException.class,()->new V53CaptureFiles(original)).getMessage());
    }

    public static final class Probe {
        public static void main(String[] args)throws Exception {
            var files=new V53CaptureFiles(Path.of(args[0]));files.unchanged();
            if(files.inventory().size()!=13)throw new AssertionError("snapshot-envelope inventory");
            System.out.println("v53ReplicaCapture=PASS bytes=872415232 heap=33554432 synthetic=true");
        }
    }
}
