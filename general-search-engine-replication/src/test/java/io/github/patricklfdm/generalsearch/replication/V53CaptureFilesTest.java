package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.io.RandomAccessFile;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Low-heap inventory and safety components, not maximum native qualification. */
class V53CaptureFilesTest {
    @TempDir Path temp;

    @Test void metadataMatchesLegacyAndRejectsChangedOrAddedOriginalMembers()throws Exception {
        Files.createDirectory(temp.resolve("empty"));Files.write(temp.resolve("image"),new byte[]{1,2,3});
        var files=new V53CaptureFiles(temp);assertEquals(V53GrantCapture.inventory(temp),files.inventory());
        assertThrows(UnsupportedOperationException.class,()->files.inventory().put("other",Map.of()));
        Files.write(temp.resolve("image"),new byte[]{3,2,1});
        assertThrows(IllegalArgumentException.class,files::unchanged);
        var replaced=new V53CaptureFiles(temp);Files.createFile(temp.resolve("extra"));
        assertThrows(IllegalArgumentException.class,replaced::unchanged);
    }

    @Test void rejectsLinksSpecialFilesAndOversizedMembersBeforeReading()throws Exception {
        Path file=Files.write(temp.resolve("file"),new byte[]{1});Path extra=temp.resolve("extra");
        Files.createSymbolicLink(extra,file);assertThrows(Exception.class,()->new V53CaptureFiles(temp));Files.delete(extra);
        Files.createLink(extra,file);assertThrows(Exception.class,()->new V53CaptureFiles(temp));Files.delete(extra);
        var fifo=new ProcessBuilder("mkfifo",extra.toString()).start();assertTrue(fifo.waitFor(10,TimeUnit.SECONDS));assertEquals(0,fifo.exitValue());
        assertThrows(Exception.class,()->new V53CaptureFiles(temp));Files.delete(extra);
        try(var out=new RandomAccessFile(file.toFile(),"rw")){out.setLength(V53GrantCapture.MAXIMUM_FILE+1L);}
        assertThrows(IllegalArgumentException.class,()->new V53CaptureFiles(temp));
    }

    @Test void refusesInvalidSegmentedPolicyBeforeCreatingEvidence()throws Exception {
        assertThrows(IllegalArgumentException.class,()->new V53GrantCapture(temp,new ArrayList<>(),
                MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.SEGMENTED_BACKUP));
        assertFalse(Files.exists(temp.resolve(V53GrantCapture.DIRECTORY)));
    }

    @Test void rejectsMemberDepthAndAmbiguousPortableNames()throws Exception {
        Path directory=Files.createDirectory(temp.resolve("a"));Files.createFile(directory.resolve("b"));
        Path ambiguous=Files.createFile(temp.resolve("a\\b"));
        assertThrows(IllegalArgumentException.class,()->new V53CaptureFiles(temp));Files.delete(ambiguous);
        Path nested=temp;
        for(int i=0;i<8;i++)nested=Files.createDirectory(nested.resolve("x"));
        Files.createFile(nested.resolve("too-deep"));
        assertThrows(IllegalArgumentException.class,()->new V53CaptureFiles(temp));
    }

    @Test void streams320MiBUnder32MiBHeapButLegacyStillRejects()throws Exception {
        for(int i=0;i<5;i++)try(var out=new RandomAccessFile(temp.resolve("image-"+i).toFile(),"rw")){out.setLength(64L*1024*1024);}
        Path output=Files.createTempFile("v53-capture-stream-",".log");
        try {
            var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-Xmx32m","-XX:-UsePerfData","-cp",
                    System.getProperty("java.class.path"),Probe.class.getName(),temp.toString()).redirectErrorStream(true).redirectOutput(output.toFile()).start();
            try {assertTrue(process.waitFor(60,TimeUnit.SECONDS),"streaming probe timeout");assertEquals(0,process.exitValue(),Files.readString(output));}
            finally {if(process.isAlive())process.destroyForcibly();}
        }finally {Files.deleteIfExists(output);}
        assertThrows(IllegalArgumentException.class,()->V53GrantCapture.inventory(temp));
    }

    public static final class Probe {
        public static void main(String[] args)throws Exception {
            var files=new V53CaptureFiles(Path.of(args[0]));files.unchanged();
            if(files.inventory().size()!=5)throw new AssertionError("streaming inventory members");
            System.out.println("v53CaptureStreaming=PASS bytes=335544320 heap=33554432");
        }
    }
}
