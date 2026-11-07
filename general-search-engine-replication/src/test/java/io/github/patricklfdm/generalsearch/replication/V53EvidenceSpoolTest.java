package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53EvidenceSpoolTest {
    @TempDir Path temp;
    static final Map<String,Object> ROW=Map.of("node","node-1","event","\n\u03bb\"");

    @Test void identicalCanonicalBytesAndOrderedReadback()throws Exception {
        var rows=List.of(ROW,Map.<String,Object>of("calls",List.of(1L,2L)),Map.<String,Object>of("empty",List.of()));
        Path path=temp.resolve("wire.json");
        try(var spool=new V53EvidenceSpool(path,4096)) {
            for(var row:rows)spool.add(row);
            assertEquals(rows,spool);assertEquals(rows,spool.stream().toList());
            assertTrue(Files.size(path)>1);assertFalse(Files.readString(path).endsWith("]"));
        }
        assertArrayEquals(V53EvidenceArray.encode(rows,4096),Files.readAllBytes(path));
    }
    @Test void recordsAreSnapshottedWithoutRetainingMutableProducerMaps()throws Exception {
        var nested=new ArrayList<>(List.of("before"));var row=new HashMap<String,Object>();row.put("value",nested);
        Path path=temp.resolve("wire.json");
        try(var spool=new V53EvidenceSpool(path,4096)) {
            spool.add(row);nested.set(0,"after");row.clear();
            assertEquals(Map.of("value",List.of("before")),spool.getFirst());
        }
        assertEquals("[{\"value\":[\"before\"]}]",Files.readString(path));
    }
    @Test void exactByteLimitIncludesBothDelimitersAndCommas()throws Exception {
        var rows=List.of(ROW,ROW);byte[] expected=V53EvidenceArray.encode(rows,4096);Path path=temp.resolve("exact");
        try(var spool=new V53EvidenceSpool(path,expected.length)){spool.addAll(rows);}
        assertArrayEquals(expected,Files.readAllBytes(path));
        try(var empty=new V53EvidenceSpool(temp.resolve("empty"),2)){assertEquals(0,empty.size());}
        assertEquals("[]",Files.readString(temp.resolve("empty")));
        assertThrows(IllegalArgumentException.class,()->new V53EvidenceSpool(temp.resolve("invalid"),1));
        assertFalse(Files.exists(temp.resolve("invalid")));
    }
    @Test void byteRefusalPoisonsCloseAndPreservesThePartialFile()throws Exception {
        Path path=temp.resolve("wire.json");var spool=new V53EvidenceSpool(path,V53EvidenceArray.encode(List.of(ROW),4096).length);
        spool.add(ROW);byte[] before=Files.readAllBytes(path);
        assertEquals("evidence spool byte capacity",assertThrows(IllegalArgumentException.class,()->spool.add(ROW)).getMessage());
        assertThrows(IllegalStateException.class,()->spool.add(ROW));assertThrows(IllegalStateException.class,()->spool.get(0));
        assertThrows(IllegalArgumentException.class,spool::close);spool.close();
        assertArrayEquals(before,Files.readAllBytes(path));assertFalse(Files.readString(path).endsWith("]"));
    }
    @Test void rowCountRefusalIsIndependentOfByteCapacity()throws Exception {
        Path path=temp.resolve("wire.json");var spool=new V53EvidenceSpool(path,1024*1024);
        for(int i=0;i<V53EvidenceArray.HISTORY_ROWS;i++)spool.add(Map.of());
        assertEquals(V53EvidenceArray.HISTORY_ROWS,spool.size());assertEquals(Map.of(),spool.getLast());
        assertEquals("evidence spool row capacity",assertThrows(IllegalArgumentException.class,()->spool.add(Map.of())).getMessage());
        assertThrows(IllegalArgumentException.class,spool::close);
    }
    @Test void malformedRowsKeepProtocolEncodingLimitsAndCannotBeDropped()throws Exception {
        Object nested="leaf";for(int i=0;i<17;i++)nested=List.of(nested);
        var bad=List.of(Map.<String,Object>of("bad-key",1),Map.<String,Object>of("tokens",Collections.nCopies(70_000,"x")),
                Map.<String,Object>of("bytes","x".repeat(16*1024*1024)),Map.<String,Object>of("depth",nested));
        for(int i=0;i<bad.size();i++) {
            Path path=temp.resolve("bad-"+i);var spool=new V53EvidenceSpool(path,64*1024*1024);var row=bad.get(i);
            assertThrows(RuntimeException.class,()->spool.add(row));
            assertThrows(RuntimeException.class,spool::close);assertEquals("[",Files.readString(path));
        }
    }
    @Test void existingFilesAndLinksAreNotOverwritten()throws Exception {
        Path file=temp.resolve("existing"),link=temp.resolve("linked");Files.writeString(file,"original");Files.createSymbolicLink(link,file);
        assertThrows(FileAlreadyExistsException.class,()->new V53EvidenceSpool(file,1024));
        assertThrows(FileAlreadyExistsException.class,()->new V53EvidenceSpool(link,1024));assertEquals("original",Files.readString(file));
    }
    @Test void observerErrorCannotBeCaughtAndConvertedToACompleteHistory()throws Exception {
        Path path=temp.resolve("wire.json");var spool=new V53EvidenceSpool(path,1024);
        var original=new AssertionError("observer failed");
        var row=new HashMap<String,Object>() {
            @Override public Set<Map.Entry<String,Object>> entrySet(){throw original;}
        };
        assertSame(original,assertThrows(AssertionError.class,()->spool.add(row)));
        assertSame(original,assertThrows(IllegalStateException.class,spool::close).getCause());
        assertEquals("[",Files.readString(path));
    }
    @Test void replacementAndExternalExtentChangesCannotBecomeCompleteEvidence()throws Exception {
        for(boolean replace:List.of(false,true)) {
            Path path=temp.resolve("wire-"+replace);var spool=new V53EvidenceSpool(path,1024);spool.add(ROW);
            if(replace){Files.move(path,temp.resolve("original"));Files.writeString(path,"x".repeat((int)Files.size(temp.resolve("original"))));}
            else Files.writeString(path,"x",StandardOpenOption.APPEND);
            byte[] observed=Files.readAllBytes(path);
            assertEquals("evidence spool file changed",assertThrows(IllegalArgumentException.class,()->spool.add(ROW)).getMessage());
            assertThrows(IllegalArgumentException.class,spool::close);assertArrayEquals(observed,Files.readAllBytes(path));
        }
    }
    @Test void closeDetectsReplacementEvenWithoutAnotherAppend()throws Exception {
        Path path=temp.resolve("wire.json");var spool=new V53EvidenceSpool(path,1024);spool.add(ROW);
        Files.move(path,temp.resolve("retained"));Files.writeString(path,"[]");
        assertThrows(IllegalArgumentException.class,spool::close);assertEquals("[]",Files.readString(path));
    }
    @Test void missingPathIoFailurePreservesTheOriginalPartialEvidence()throws Exception {
        Path path=temp.resolve("wire.json"),retained=temp.resolve("retained");var spool=new V53EvidenceSpool(path,1024);spool.add(ROW);
        Files.move(path,retained);byte[] original=Files.readAllBytes(retained);
        var failure=assertThrows(java.io.UncheckedIOException.class,()->spool.add(ROW));
        assertInstanceOf(NoSuchFileException.class,failure.getCause());
        assertSame(failure,assertThrows(java.io.UncheckedIOException.class,spool::close));
        assertArrayEquals(original,Files.readAllBytes(retained));assertFalse(Files.exists(path));
    }
    @Test void concurrentCallbacksPreserveEveryRowAndEachProducerOrder()throws Exception {
        Path path=temp.resolve("wire.json");
        try(var spool=new V53EvidenceSpool(path,1024*1024);var pool=Executors.newFixedThreadPool(4)) {
            var tasks=new ArrayList<Future<?>>();
            for(int owner=0;owner<4;owner++){int id=owner;tasks.add(pool.submit(()->{for(int i=0;i<250;i++)spool.add(Map.of("owner",(long)id,"index",(long)i));}));}
            for(var task:tasks)task.get(30,TimeUnit.SECONDS);
            assertEquals(1000,spool.size());var seen=new int[4];
            for(var row:spool)assertEquals((long)seen[((Long)row.get("owner")).intValue()]++,row.get("index"));
            assertArrayEquals(new int[]{250,250,250,250},seen);
        }
        assertTrue(Files.readString(path).endsWith("]"));
    }
    @Test void closeIsIdempotentAndFurtherAccessCannotWrite()throws Exception {
        Path path=temp.resolve("wire.json");var spool=new V53EvidenceSpool(path,1024);spool.add(ROW);spool.close();byte[] before=Files.readAllBytes(path);
        spool.close();assertThrows(IllegalArgumentException.class,()->spool.add(ROW));assertThrows(IllegalArgumentException.class,()->spool.get(0));
        assertArrayEquals(before,Files.readAllBytes(path));
    }
    @Test void completeHistoryCanExceedTheCollectorHeap()throws Exception {
        Path path=temp.resolve("large.json"),log=temp.resolve("child.log");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin","java").toString(),"-Xmx32m","-cp",
                System.getProperty("surefire.test.class.path",System.getProperty("java.class.path")),HeapProbe.class.getName(),path.toString())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            assertTrue(process.waitFor(90,TimeUnit.SECONDS),"bounded heap probe did not finish");
            assertEquals(0,process.exitValue(),Files.readString(log));assertEquals("rows=200\n",Files.readString(log));
            assertTrue(Files.size(path)>50L*1024*1024);assertTrue(Files.size(path)<V53EvidenceArray.WIRE_BYTES);
        }finally{if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
    }
    public static final class HeapProbe {
        public static void main(String[] args)throws Exception {
            try(var spool=new V53EvidenceSpool(Path.of(args[0]),V53EvidenceArray.WIRE_BYTES)) {
                for(int i=0;i<200;i++)spool.add(Map.of("index",(long)i,"bytes",i+"x".repeat(300*1024)));
                for(int i=0;i<200;i++)if(!spool.get(i).get("index").equals((long)i))throw new IllegalStateException("row order");
            }
            System.out.println("rows=200");
        }
    }
}
