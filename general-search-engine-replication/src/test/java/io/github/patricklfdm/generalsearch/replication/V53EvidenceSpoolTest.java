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
        assertThrows(IllegalStateException.class,spool::close);spool.close();
        assertArrayEquals(before,Files.readAllBytes(path));assertFalse(Files.readString(path).endsWith("]"));
    }
    @Test void rowCountRefusalIsIndependentOfByteCapacity()throws Exception {
        Path path=temp.resolve("wire.json");var spool=new V53EvidenceSpool(path,1024*1024);
        for(int i=0;i<V53EvidenceArray.HISTORY_ROWS;i++)spool.add(Map.of());
        assertEquals(V53EvidenceArray.HISTORY_ROWS,spool.size());assertEquals(Map.of(),spool.getLast());
        assertEquals("evidence spool row capacity",assertThrows(IllegalArgumentException.class,()->spool.add(Map.of())).getMessage());
        assertThrows(IllegalStateException.class,spool::close);
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
            assertThrows(IllegalStateException.class,spool::close);assertArrayEquals(observed,Files.readAllBytes(path));
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
        assertSame(failure,assertThrows(IllegalStateException.class,spool::close).getCause());
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
    @Test void snapshotsFreezeTheirOwnPrefixWhileLaterCallbacksContinue()throws Exception {
        Path path=temp.resolve("wire.json"),first=temp.resolve("first.json"),second=temp.resolve("second.json");
        var later=Map.<String,Object>of("event","later");
        try(var spool=new V53EvidenceSpool(path,4096)) {
            spool.add(ROW);spool.snapshot(first);byte[] original=Files.readAllBytes(first);
            spool.add(later);spool.snapshot(second);assertEquals(2,spool.size());assertEquals(later,spool.getLast());
            assertArrayEquals(V53EvidenceArray.encode(List.of(ROW),4096),original);
            assertArrayEquals(original,Files.readAllBytes(first));
            assertArrayEquals(V53EvidenceArray.encode(List.of(ROW,later),4096),Files.readAllBytes(second));
        }
        assertEquals(-1,Files.mismatch(path,second));
    }
    @Test void emptySnapshotDoesNotEndTheWriterAndClosedWriterCannotSnapshot()throws Exception {
        Path path=temp.resolve("wire.json"),empty=temp.resolve("empty.json");var spool=new V53EvidenceSpool(path,1024);
        spool.snapshot(empty);assertEquals("[]",Files.readString(empty));spool.add(ROW);spool.close();
        assertThrows(IllegalArgumentException.class,()->spool.snapshot(temp.resolve("after.json")));
        assertFalse(Files.exists(temp.resolve("after.json")));assertEquals("[]",Files.readString(empty));
    }
    @Test void snapshotCannotOverwriteExistingEvidenceOrFollowLinks()throws Exception {
        for(boolean link:List.of(false,true)) {
            Path source=temp.resolve("wire-"+link),existing=temp.resolve("old-"+link);Files.writeString(existing,"original");
            Path destination=existing;
            if(link){destination=temp.resolve("link");Files.createSymbolicLink(destination,existing);}
            var spool=new V53EvidenceSpool(source,1024);spool.add(ROW);Path output=destination;
            assertThrows(java.io.UncheckedIOException.class,()->spool.snapshot(output));
            assertInstanceOf(java.io.UncheckedIOException.class,assertThrows(IllegalStateException.class,spool::close).getCause());
            assertEquals("original",Files.readString(existing));
            assertFalse(Files.readString(source).endsWith("]"));
        }
    }
    @Test void sameLengthContentChangesFailReadSnapshotAndClose()throws Exception {
        for(String operation:List.of("read","snapshot","close")) {
            Path source=temp.resolve(operation);var spool=new V53EvidenceSpool(source,1024);spool.add(Map.of("event","first"));
            String original=Files.readString(source);Files.writeString(source,original.replace("first","other"));
            var action=(org.junit.jupiter.api.function.Executable)()->{
                switch(operation) {
                    case "read"->spool.getFirst();
                    case "snapshot"->spool.snapshot(temp.resolve("snapshot.json"));
                    default->spool.close();
                }
            };
            assertEquals("evidence spool content changed",assertThrows(IllegalArgumentException.class,action).getMessage());
            if(!operation.equals("close"))assertThrows(IllegalStateException.class,spool::close);
            assertFalse(Files.readString(source).endsWith("]"));
        }
        assertFalse(Files.readString(temp.resolve("snapshot.json")).endsWith("]"));
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
    @Test void concurrentPreAppendObserversSeeTheExactIndexAndOriginalOrder()throws Exception {
        Path path=temp.resolve("events.json");var observed=new ArrayList<Map<String,Object>>();
        var reference=new java.util.concurrent.atomic.AtomicReference<V53EvidenceSpool>();
        try(var spool=new V53EvidenceSpool(path,1024*1024,(index,row)->{
            assertTrue(Thread.holdsLock(reference.get()));assertEquals(index,reference.get().size());
            assertEquals(observed.size(),index);observed.add(Map.copyOf(row));
        });var pool=Executors.newFixedThreadPool(4)) {
            reference.set(spool);var tasks=new ArrayList<Future<?>>();
            for(int owner=0;owner<4;owner++){int id=owner;tasks.add(pool.submit(()->{
                for(int i=0;i<100;i++)spool.add(Map.of("node","node-"+id,"event","at-"+i));
            }));}
            for(var task:tasks)task.get(30,TimeUnit.SECONDS);
            assertEquals(400,observed.size());assertEquals(observed,spool);
        }
        assertArrayEquals(V53EvidenceArray.encode(observed,1024*1024),Files.readAllBytes(path));
    }
    @Test void invalidAppendCannotAdvanceTheObserverIndexOrProduceASeal()throws Exception {
        Path path=temp.resolve("events.json");var indices=new ArrayList<Integer>();
        var spool=new V53EvidenceSpool(path,V53EvidenceArray.encode(List.of(ROW),4096).length,(index,row)->indices.add(index));
        spool.add(ROW);assertThrows(IllegalArgumentException.class,()->spool.add(ROW));assertEquals(List.of(0),indices);
        assertThrows(RuntimeException.class,spool::close);
        assertThrows(IllegalArgumentException.class,()->spool.sealedSha256(path));
    }
    @Test void observerExceptionsAndErrorsLeaveUnsealedOriginals()throws Exception {
        for(boolean error:List.of(false,true)) {
            Path path=temp.resolve("events-"+error);Throwable failure=error?new AssertionError("capture"):new IllegalArgumentException("capture");
            var spool=new V53EvidenceSpool(path,4096,(index,row)->{
                if(index==1){if(failure instanceof Error e)throw e;throw (RuntimeException)failure;}
            });
            spool.add(ROW);byte[] before=Files.readAllBytes(path);
            assertSame(failure,assertThrows(Throwable.class,()->spool.add(ROW)));
            assertThrows(IllegalStateException.class,()->spool.add(ROW));assertThrows(RuntimeException.class,spool::close);
            assertArrayEquals(before,Files.readAllBytes(path));
            assertThrows(IllegalArgumentException.class,()->spool.sealedSha256(path));
        }
    }
    @Test void tryWithResourcesKeepsTheOriginalObserverFailure()throws Exception {
        var original=new IllegalArgumentException("original observer failure");Path path=temp.resolve("events.json");
        var spool=new V53EvidenceSpool(path,4096,(index,row)->{throw original;});
        var thrown=assertThrows(RuntimeException.class,()->{try(spool){spool.add(ROW);}});
        assertSame(original,thrown);assertEquals(1,thrown.getSuppressed().length);
        assertSame(original,thrown.getSuppressed()[0].getCause());
        assertThrows(IllegalArgumentException.class,()->spool.sealedSha256(path));assertEquals("[",Files.readString(path));
    }
    @Test void caughtRecursiveMutationCannotRestoreEligibility()throws Exception {
        for(String mutation:List.of("append","snapshot","close")) {
            Path path=temp.resolve("events-"+mutation);var reference=new java.util.concurrent.atomic.AtomicReference<V53EvidenceSpool>();
            var spool=new V53EvidenceSpool(path,4096,(index,row)->{
                try {
                    switch(mutation) {
                        case "append" -> reference.get().add(ROW);
                        case "snapshot" -> reference.get().snapshot(temp.resolve("snapshot"));
                        case "close" -> reference.get().close();
                    }
                }catch(Exception ignored){}
            });reference.set(spool);
            assertThrows(RuntimeException.class,()->spool.add(ROW));
            try{spool.close();}catch(RuntimeException ignored){}
            assertEquals("[",Files.readString(path));assertFalse(Files.exists(temp.resolve("snapshot")));
            assertThrows(IllegalArgumentException.class,()->spool.sealedSha256(path));
        }
    }
    @Test void sealBindsTheCompleteBytesAfterSnapshotsAndOnlyTheOriginalPath()throws Exception {
        for(boolean empty:List.of(false,true)) {
            Path path=temp.resolve("events-"+empty);var spool=new V53EvidenceSpool(path,4096);
            assertThrows(IllegalArgumentException.class,()->spool.sealedSha256(path));
            if(!empty){spool.add(ROW);spool.snapshot(temp.resolve("prefix"));spool.add(Map.of("event","CLOSE"));}
            spool.close();String expected=io.github.patricklfdm.generalsearch.replication.MembershipFormat.hash(Files.readAllBytes(path));
            assertEquals(expected,spool.sealedSha256(path));spool.close();assertEquals(expected,spool.sealedSha256(path));
            assertThrows(IllegalArgumentException.class,()->spool.sealedSha256(temp.resolve("foreign")));
        }
    }
    public static final class HeapProbe {
        public static void main(String[] args)throws Exception {
            Path path=Path.of(args[0]),prefix=path.resolveSibling("prefix.json"),complete=path.resolveSibling("complete.json");
            int[] observed={0};var spool=new V53EvidenceSpool(path,V53EvidenceArray.WIRE_BYTES,(index,row)->{
                if(index!=observed[0]++ || !row.get("index").equals((long)index))throw new IllegalStateException("observer order");
            });
            try(spool) {
                for(int i=0;i<200;i++) {
                    spool.add(Map.of("index",(long)i,"bytes",i+"x".repeat(300*1024)));
                    if(i==99)spool.snapshot(prefix);
                }
                spool.snapshot(complete);
                for(int i=0;i<200;i++)if(!spool.get(i).get("index").equals((long)i))throw new IllegalStateException("row order");
            }
            if(Files.size(prefix)<25L*1024*1024 || Files.size(prefix)>=Files.size(complete) || Files.mismatch(path,complete)!=-1)
                throw new IllegalStateException("snapshot prefix/output");
            var digest=java.security.MessageDigest.getInstance("SHA-256");
            try(var input=Files.newInputStream(path)){byte[] buffer=new byte[65536];int count;while((count=input.read(buffer))!=-1)digest.update(buffer,0,count);}
            if(observed[0]!=200 || !spool.sealedSha256(path).equals(HexFormat.of().formatHex(digest.digest())))
                throw new IllegalStateException("sealed history hash");
            System.out.println("rows=200");
        }
    }
}
