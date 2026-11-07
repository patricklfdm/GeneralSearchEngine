package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SegmentedEvidenceTest {
    @TempDir Path temp;
    static final Map<String,Object> ROW=Map.of("node","node-1","event","\n\u03bb\"");
    Map<String,Object> index(Path root,String name)throws Exception{return object(parse(Files.readAllBytes(root.resolve(name)),V53SegmentedEvidence.ROW_BYTES));}

    @Test void snapshotsKeepExactPrefixWhileLaterRowsContinue()throws Exception {
        Path root=temp.resolve("original");var nested=new ArrayList<>(List.of("before"));var row=new HashMap<String,Object>();row.put("values",nested);
        try(var spool=new V53SegmentedEvidence(root,4096)) {
            spool.snapshot("empty");spool.add(ROW);spool.add(row);spool.snapshot("before-change");
            byte[] prefix=Files.readAllBytes(root.resolve("cuts/before-change.json"));
            nested.set(0,"after");row.clear();spool.add(Map.of("end",true));
            assertEquals(ROW,spool.getFirst());assertEquals(Map.of("values",List.of("before")),spool.get(1));
            assertEquals(3,spool.stream().count());assertArrayEquals(prefix,Files.readAllBytes(root.resolve("cuts/before-change.json")));
            assertFalse(Files.exists(root.resolve("complete.json")));
        }
        var complete=index(root,"complete.json");assertEquals(3L,complete.get("rows"));
        assertEquals(0L,index(root,"cuts/empty.json").get("rows"));
        var prefix=index(root,"cuts/before-change.json");assertEquals(2L,prefix.get("rows"));
        assertEquals(list(prefix.get("segments")),list(complete.get("segments")).subList(0,1));
        byte[] expected=(new String(canonical(ROW,4096),java.nio.charset.StandardCharsets.US_ASCII)+"\n{\"values\":[\"before\"]}\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        assertArrayEquals(expected,Files.readAllBytes(root.resolve("segments/segment-0000.jsonl")));
    }
    @Test void byteCapCountsNewlinesAndRefusalCannotSealPartialHistory()throws Exception {
        long bytes=canonical(ROW,4096).length+1L;Path root=temp.resolve("exact");
        var spool=new V53SegmentedEvidence(root,bytes);spool.add(ROW);spool.close();assertEquals(bytes,index(root,"complete.json").get("bytes"));
        root=temp.resolve("failed");spool=new V53SegmentedEvidence(root,bytes);spool.add(ROW);var failed=spool;
        assertEquals("segmented evidence byte capacity",assertThrows(RuntimeException.class,()->failed.add(ROW)).getMessage());
        assertThrows(RuntimeException.class,failed::close);failed.close();assertFalse(Files.exists(root.resolve("complete.json")));
        assertEquals(1,failed.size());assertThrows(RuntimeException.class,()->failed.get(0));
    }
    @Test void emptyArchiveAndInvalidLimitsCannotExpandTheFormat()throws Exception {
        Path root=temp.resolve("empty");try(var ignored=new V53SegmentedEvidence(root,0)){}
        assertEquals(0L,index(root,"complete.json").get("bytes"));assertEquals(List.of(),index(root,"complete.json").get("segments"));
        for(long limit:new long[]{-1,V53SegmentedEvidence.MAXIMUM+1})assertThrows(RuntimeException.class,()->new V53SegmentedEvidence(temp.resolve("invalid"),limit));
        assertFalse(Files.exists(temp.resolve("invalid")));assertThrows(FileAlreadyExistsException.class,()->new V53SegmentedEvidence(root,1));
    }
    @Test void rowCapRemainsIndependentOfTheLargerByteAllowance()throws Exception {
        Path root=temp.resolve("rows");var spool=new V53SegmentedEvidence(root,V53SegmentedEvidence.MAXIMUM);
        for(int i=0;i<V53EvidenceArray.HISTORY_ROWS;i++)spool.add(Map.of());
        assertEquals("segmented evidence row capacity",assertThrows(RuntimeException.class,()->spool.add(Map.of())).getMessage());
        assertThrows(RuntimeException.class,spool::close);assertFalse(Files.exists(root.resolve("complete.json")));
    }
    @Test void malformedRowsCannotBeSkippedAndOriginalExceptionIsPreserved()throws Exception {
        Path root=temp.resolve("bad");var spool=new V53SegmentedEvidence(root,4096);
        var error=assertThrows(RuntimeException.class,()->{try(spool){spool.add(ROW);spool.add(Map.of("bad-key",1));}});
        assertEquals(1,error.getSuppressed().length);assertSame(error,error.getSuppressed()[0].getCause());
        assertFalse(Files.exists(root.resolve("complete.json")));
    }
    @Test void snapshotsCannotBeOverwrittenOrEscapedAndTheirCountIsBounded()throws Exception {
        for(String name:List.of("../outside","repeat","overflow")) {
            Path root=temp.resolve(name.equals("../outside")?"path":name);var spool=new V53SegmentedEvidence(root,4096);spool.add(ROW);
            if(name.equals("repeat"))spool.snapshot(name);
            if(name.equals("overflow"))for(int i=0;i<V53SegmentedEvidence.CUTS;i++)spool.snapshot("cut-"+i);
            assertEquals("segmented evidence cut",assertThrows(RuntimeException.class,()->spool.snapshot(name)).getMessage());
            assertThrows(RuntimeException.class,spool::close);assertFalse(Files.exists(root.resolve("complete.json")));
        }
    }
    @Test void contentAndSavedCutTamperingPreventTheFinalSeal()throws Exception {
        for(String target:List.of("active","sealed","cut")) {
            Path root=temp.resolve(target);var spool=new V53SegmentedEvidence(root,4096);spool.add(ROW);
            if(!target.equals("active"))spool.snapshot("prefix");
            Path path=root.resolve(target.equals("cut")?"cuts/prefix.json":"segments/segment-0000.jsonl");
            byte[] bytes=Files.readAllBytes(path);bytes[2]=(byte)(bytes[2]=='x'?'y':'x');Files.write(path,bytes);
            assertEquals("segmented evidence content changed",assertThrows(RuntimeException.class,spool::close).getMessage());
            assertFalse(Files.exists(root.resolve("complete.json")));
        }
    }
    @Test void replacementAndSymlinkCannotStandInForObservedFiles()throws Exception {
        for(boolean link:List.of(false,true)) {
            Path root=temp.resolve("replace-"+link);var spool=new V53SegmentedEvidence(root,4096);spool.add(ROW);
            Path path=root.resolve("segments/segment-0000.jsonl"),retained=temp.resolve("retained-"+link);Files.move(path,retained);
            if(link)Files.createSymbolicLink(path,retained);else Files.copy(retained,path);
            assertThrows(RuntimeException.class,()->spool.get(0));assertThrows(RuntimeException.class,spool::close);
            assertFalse(Files.exists(root.resolve("complete.json")));assertTrue(Files.size(retained)>0);
        }
    }
    @Test void largerThanOldWireCapacityWithSmallHeapAndImmutableCuts()throws Exception {
        Path parent=Files.createDirectories(Path.of("target/v53-segmented-evidence"));String id="probe-"+UUID.randomUUID();
        Path root=parent.resolve(id),log=parent.resolve(id+".log");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin","java").toString(),"-Xmx32m","-cp",
            System.getProperty("surefire.test.class.path",System.getProperty("java.class.path")),HeapProbe.class.getName(),root.toString())
            .redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            assertTrue(process.waitFor(120,TimeUnit.SECONDS),"bounded segmented probe did not finish");
            assertEquals(0,process.exitValue(),Files.readString(log));var complete=index(root,"complete.json");
            assertTrue(number(complete.get("bytes"))>V53EvidenceArray.WIRE_BYTES);assertTrue(list(complete.get("segments")).size()>=3);
            System.out.println("v53SegmentedEvidence="+root.toAbsolutePath());
        }finally{if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
    }
    public static final class HeapProbe {
        public static void main(String[] args)throws Exception {
            Path root=Path.of(args[0]);var row=Map.<String,Object>of("body","x".repeat(60*1024));
            try(var spool=new V53SegmentedEvidence(root,128L*1024*1024)) {
                for(int i=0;i<1600;i++){spool.add(row);if(i==99)spool.snapshot("first-hundred");}
                if(spool.size()!=1600 || !spool.get(0).equals(row) || !spool.get(1599).equals(row))throw new AssertionError("row mismatch");
            }
            System.out.println("rows=1600");
        }
    }
}
