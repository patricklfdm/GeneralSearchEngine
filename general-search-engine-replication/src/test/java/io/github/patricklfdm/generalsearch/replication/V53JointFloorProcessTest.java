package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.canonical;
import static org.junit.jupiter.api.Assertions.*;

/** IPC record framing only; not process-death protocol qualification. */
class V53JointFloorProcessTest {
    @TempDir Path temp;
    @Test void incomingAndReceivingParentsExistBeforeOwnerEndpoints()throws Exception {
        Path root=temp.resolve("scratch");V53JointFloorWorker.prepareScratch(root);
        assertFalse(Files.exists(root.resolve("incoming")));
        assertEquals(root.resolve("incoming").toString(),AdmissionPaths.binding(root.resolve("incoming")).get("path"));
        assertEquals(root.resolve("outgoing/source-001").toString(),AdmissionPaths.binding(root.resolve("outgoing/source-001")).get("path"));
        Files.writeString(root.resolve("outgoing/retained"),"keep");
        assertThrows(FileAlreadyExistsException.class,()->V53JointFloorWorker.prepareScratch(root));
        assertEquals("keep",Files.readString(root.resolve("outgoing/retained")));
    }
    private static byte[] line(String kind,Object value) {
        return (new String(canonical(Map.of("kind",kind,"value",value),16*1024*1024),StandardCharsets.UTF_8)+"\n").getBytes(StandardCharsets.UTF_8);
    }
    @Test void fragmentedLargeRowsRemainCompleteAndOriginal()throws Exception {
        byte[] first=line("EVENT",Map.of("event","FIRST","bytes","x".repeat(32769))),second=line("CUT",Map.of("point","FLOOR_MEMBER_FORCED"));
        var source=new ByteArrayOutputStream();source.write(first);source.write(second);byte[] original=source.toByteArray();
        var collected=new ArrayList<Map<String,Object>>();var retained=new ByteArrayOutputStream();
        try(var input=new FilterInputStream(new ByteArrayInputStream(original)) {
            @Override public int read(byte[] b,int off,int len)throws IOException{return super.read(b,off,Math.min(len,7));}
        }) {V53JointFloorProcess.copy(input,retained,collected::add);}
        assertArrayEquals(original,retained.toByteArray());assertEquals(2,collected.size());
        assertEquals("x".repeat(32769),((Map<?,?>)collected.getFirst().get("value")).get("bytes"));assertEquals("CUT",collected.getLast().get("kind"));
    }
    @Test void incompleteLastRecordIsRetainedAndRefused()throws Exception {
        byte[] complete=line("STARTED",Map.of("pid",17));var source=new ByteArrayOutputStream();source.write(complete);source.write("{\"kind\":".getBytes(StandardCharsets.UTF_8));
        var retained=new ByteArrayOutputStream();var received=new ArrayList<Map<String,Object>>();
        var error=assertThrows(IllegalArgumentException.class,()->V53JointFloorProcess.copy(new ByteArrayInputStream(source.toByteArray()),retained,received::add));
        assertEquals("joint floor process incomplete original line",error.getMessage());assertArrayEquals(source.toByteArray(),retained.toByteArray());assertEquals(1,received.size());
    }
    @Test void unknownOrNoncanonicalRecordsNeverBecomeControls() {
        for(String text:List.of("{\"kind\":\"PASS\",\"value\":{}}\n","{\"value\":{},\"kind\":\"CUT\"}\n","{\"kind\":\"CUT\",\"kind\":\"CUT\",\"value\":{}}\n")) {
            var received=new ArrayList<Map<String,Object>>();
            Class<? extends RuntimeException> expected=text.contains("PASS")?IllegalArgumentException.class:ReplicationException.class;
            assertThrows(expected,()->V53JointFloorProcess.copy(new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)),new ByteArrayOutputStream(),received::add));
            assertTrue(received.isEmpty());
        }
    }
}
