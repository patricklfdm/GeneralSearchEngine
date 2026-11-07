package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53AuxiliaryWire.History.*;

class V53AuxiliaryWireTest {
    @TempDir Path temp;
    static final Map<String,Object> FIRST=Map.of("event","first"),LATER=Map.of("event","later");

    @Test void everyAuxiliaryHistoryKeepsItsOriginalNameCapacityAndCut()throws Exception {
        assertEquals(List.of(8*1024*1024,1024*1024,1024*1024,8*1024*1024,64*1024*1024),
                Arrays.stream(V53AuxiliaryWire.History.values()).map(h->h.maximum).toList());
        for(boolean spooled:List.of(false,true)) {
            Path root=Files.createDirectory(temp.resolve("mode-"+spooled));
            try(var group=new V53AuxiliaryWire(root,spooled)) {
                for(var history:V53AuxiliaryWire.History.values()) {
                    var rows=group.open(history);assertEquals(spooled,rows instanceof V53EvidenceSpool);
                    rows.add(FIRST);group.snapshot(history);rows.add(LATER);
                    assertEquals(List.of(FIRST,LATER),rows);
                }
            }
            for(var history:V53AuxiliaryWire.History.values()) {
                assertArrayEquals(V53EvidenceArray.encode(List.of(FIRST),4096),Files.readAllBytes(root.resolve(history.file)));
                if(spooled)assertArrayEquals(V53EvidenceArray.encode(List.of(FIRST,LATER),4096),Files.readAllBytes(root.resolve(V53AuxiliaryWire.STAGING).resolve(history.file)));
            }
            assertEquals(spooled,Files.exists(root.resolve(V53AuxiliaryWire.STAGING)));
        }
    }
    @Test void scopeChecksRejectDuplicateOpenMissingHistoryAndSecondSnapshot()throws Exception {
        for(boolean spooled:List.of(false,true))try(var group=new V53AuxiliaryWire(Files.createDirectory(temp.resolve("mode-"+spooled)),spooled)) {
            assertThrows(IllegalArgumentException.class,()->group.snapshot(HEAD));group.open(HEAD);
            assertThrows(IllegalArgumentException.class,()->group.open(HEAD));group.snapshot(HEAD);
            assertThrows(IllegalArgumentException.class,()->group.snapshot(HEAD));
        }
    }
    @Test void partialExecutionClosesItsSpoolWithoutInventingAnEarlierSnapshot()throws Exception {
        var group=new V53AuxiliaryWire(temp,true);var rows=group.open(INTENT);rows.add(FIRST);group.close();
        assertFalse(Files.exists(temp.resolve(INTENT.file)));
        assertArrayEquals(V53EvidenceArray.encode(List.of(FIRST),4096),Files.readAllBytes(temp.resolve(V53AuxiliaryWire.STAGING).resolve(INTENT.file)));
        assertThrows(IllegalArgumentException.class,()->rows.add(LATER));
    }
    @Test void existingSnapshotIsNeverOverwrittenInEitherMode()throws Exception {
        for(boolean spooled:List.of(false,true)) {
            Path root=Files.createDirectory(temp.resolve("mode-"+spooled));Files.writeString(root.resolve(ACK.file),"original");
            var group=new V53AuxiliaryWire(root,spooled);group.open(ACK).add(FIRST);
            if(spooled)assertThrows(java.io.UncheckedIOException.class,()->group.snapshot(ACK));
            else assertThrows(FileAlreadyExistsException.class,()->group.snapshot(ACK));
            if(spooled)assertInstanceOf(java.io.UncheckedIOException.class,assertThrows(IllegalStateException.class,group::close).getCause());else group.close();
            assertEquals("original",Files.readString(root.resolve(ACK.file)));
        }
    }
    @Test void closeDrainsEverySpoolDespiteMultipleFailuresIncludingASharedException()throws Exception {
        var group=new V53AuxiliaryWire(temp,true);var shared=new IllegalStateException("shared observer failure");
        var bad=new HashMap<String,Object>() {@Override public Set<Map.Entry<String,Object>> entrySet(){throw shared;}};
        var one=group.open(INTENT);var two=group.open(ACK);var good=group.open(HEAD);
        assertSame(shared,assertThrows(IllegalStateException.class,()->one.add(bad)));
        assertSame(shared,assertThrows(IllegalStateException.class,()->two.add(bad)));good.add(FIRST);
        var closed=assertThrows(IllegalStateException.class,group::close);assertSame(shared,closed.getCause());
        assertEquals(1,closed.getSuppressed().length);assertSame(shared,closed.getSuppressed()[0].getCause());group.close();
        for(var rows:List.of(one,two,good))assertThrows(IllegalArgumentException.class,()->rows.add(LATER));
        assertEquals("[",Files.readString(temp.resolve(V53AuxiliaryWire.STAGING).resolve(INTENT.file)));
        assertArrayEquals(V53EvidenceArray.encode(List.of(FIRST),4096),Files.readAllBytes(temp.resolve(V53AuxiliaryWire.STAGING).resolve(HEAD.file)));
    }
    @Test void closeKeepsDistinctFailureCausesAndContinuesClosing()throws Exception {
        var group=new V53AuxiliaryWire(temp,true);var one=group.open(ACK);var two=group.open(HEAD);
        RuntimeException first=assertThrows(RuntimeException.class,()->one.add(Map.of("bad-key",1)));
        RuntimeException second=assertThrows(RuntimeException.class,()->two.add(Map.of("bad-key",2)));
        var closed=assertThrows(IllegalStateException.class,group::close);assertSame(first,closed.getCause());
        assertEquals(1,closed.getSuppressed().length);assertSame(second,closed.getSuppressed()[0].getCause());
    }
    @Test void stagingMustBeNewAndMayNotBeASymlink()throws Exception {
        Path outside=Files.createDirectory(temp.resolve("outside"));Files.writeString(outside.resolve(ACK.file),"original");
        Path root=Files.createDirectory(temp.resolve("root"));Files.createSymbolicLink(root.resolve(V53AuxiliaryWire.STAGING),outside);
        try(var group=new V53AuxiliaryWire(root,true)){assertThrows(FileAlreadyExistsException.class,()->group.open(ACK));}
        assertEquals("original",Files.readString(outside.resolve(ACK.file)));
    }
    @Test void producerCanContinueAfterTheSnapshotWithoutChangingItsEarlierRows()throws Exception {
        try(var group=new V53AuxiliaryWire(temp,true);var executor=Executors.newSingleThreadExecutor()) {
            var rows=group.open(RETENTION);rows.add(FIRST);group.snapshot(RETENTION);
            var task=executor.submit(()->{for(int i=0;i<1000;i++)rows.add(Map.of("index",(long)i));});task.get(30,TimeUnit.SECONDS);
            assertEquals(1001,rows.size());assertEquals(999L,rows.getLast().get("index"));
            assertArrayEquals(V53EvidenceArray.encode(List.of(FIRST),4096),Files.readAllBytes(temp.resolve(RETENTION.file)));
        }
    }
}
