package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53WireArchiveTest {
    @TempDir Path temp;
    static final Map<String,Object> ROW=Map.of("row",1L);

    @Test void allSixHistoriesKeepOriginalLogicalNamesAndAuxiliaryCuts()throws Exception {
        var archive=new V53WireArchive(temp,V53SegmentedEvidence.MAXIMUM);var main=archive.open("wire.json");main.add(ROW);
        try(archive;var auxiliary=new V53AuxiliaryWire(temp,true,archive)) {
            for(var history:V53AuxiliaryWire.History.values()) {
                var rows=auxiliary.open(history);assertInstanceOf(V53SegmentedEvidence.class,rows);
                rows.add(ROW);auxiliary.snapshot(history);rows.add(Map.of("later",true));
                assertFalse(Files.exists(temp.resolve(history.file)));
            }
            main.add(Map.of("last",true));
        }
        Path root=temp.resolve(V53WireArchive.DIRECTORY);var index=object(parse(Files.readAllBytes(root.resolve("index.json")),65536));
        assertEquals(V53WireArchive.SCHEMA,index.get("schema"));assertEquals(6,list(index.get("histories")).size());
        for(var entry:list(index.get("histories"))) {
            var row=object(entry);String name=(String)row.get("file");Path base=root.resolve(V53WireArchive.directory(name));
            assertEquals(hash(Files.readAllBytes(base.resolve("complete.json"))),row.get("completeSha256"));
            assertEquals(2L,object(parse(Files.readAllBytes(base.resolve("complete.json")),65536)).get("rows"));
            if(name.equals("wire.json"))assertNull(row.get("observedSha256"));
            else {
                byte[] cut=Files.readAllBytes(base.resolve("cuts/observed.json"));
                assertEquals(hash(cut),row.get("observedSha256"));assertEquals(1L,object(parse(cut,65536)).get("rows"));
            }
        }
        long bytes=0;try(var files=Files.walk(root)){for(Path p:files.filter(Files::isRegularFile).toList())bytes+=Files.size(p);}
        assertEquals(bytes,archive.capturedBytes());assertFalse(Files.exists(temp.resolve("wire.json")));
        assertFalse(Files.exists(temp.resolve(V53AuxiliaryWire.STAGING)));
    }
    @Test void sharedByteRefusalPoisonsOtherHistoriesWithoutMultiplyingCapacity()throws Exception {
        long one=canonical(ROW,1024).length+1L;var archive=new V53WireArchive(temp,2*one);
        var main=archive.open("wire.json");var other=archive.open("joining-intent-wire.json");main.add(ROW);other.add(ROW);
        assertEquals("segmented evidence shared byte capacity",assertThrows(RuntimeException.class,()->main.add(ROW)).getMessage());
        assertEquals("segmented evidence shared budget failed",assertThrows(RuntimeException.class,()->other.add(ROW)).getMessage());
        assertThrows(RuntimeException.class,archive::close);archive.close();
        assertFalse(Files.exists(temp.resolve(V53WireArchive.DIRECTORY).resolve("index.json")));
    }
    @Test void metadataIsChargedEvenForAnEmptyWireHistory()throws Exception {
        var archive=new V53WireArchive(temp,0);archive.open("wire.json");
        assertEquals("segmented evidence shared byte capacity",assertThrows(RuntimeException.class,archive::close).getMessage());
        assertFalse(Files.exists(temp.resolve(V53WireArchive.DIRECTORY).resolve("index.json")));
    }
    @Test void missingAuxiliarySnapshotIsRetainedAsMissingAndNeverInvented()throws Exception {
        try(var archive=new V53WireArchive(temp,4096)) {archive.open("wire.json").add(ROW);archive.open("joining-head-wire.json").add(ROW);}
        Path root=temp.resolve(V53WireArchive.DIRECTORY);var index=object(parse(Files.readAllBytes(root.resolve("index.json")),65536));
        for(var row:list(index.get("histories")))assertNull(object(row).get("observedSha256"));
        assertFalse(Files.exists(root.resolve("joining-head-wire/cuts/observed.json")));
    }
    @Test void legacyConflictAndInvalidLogicalHistoryCannotProduceAnIndex()throws Exception {
        Files.writeString(temp.resolve("wire.json"),"original");
        assertThrows(RuntimeException.class,()->new V53WireArchive(temp,4096));assertFalse(Files.exists(temp.resolve(V53WireArchive.DIRECTORY)));
        assertEquals("original",Files.readString(temp.resolve("wire.json")));
        Path other=Files.createDirectory(temp.resolve("other"));var archive=new V53WireArchive(other,4096);archive.open("wire.json");
        assertThrows(RuntimeException.class,()->archive.open("../outside.json"));assertThrows(RuntimeException.class,archive::close);
        assertFalse(Files.exists(other.resolve(V53WireArchive.DIRECTORY).resolve("index.json")));
    }
    @Test void failureDrainsOtherHistoriesButCannotAdmitTheSuccessfulSubset()throws Exception {
        var archive=new V53WireArchive(temp,4096);var main=archive.open("wire.json");var other=archive.open("joining-ack-wire.json");
        assertThrows(RuntimeException.class,()->main.add(Map.of("bad-key",1)));other.add(ROW);
        assertThrows(RuntimeException.class,archive::close);assertThrows(RuntimeException.class,()->other.add(ROW));
        Path root=temp.resolve(V53WireArchive.DIRECTORY);assertTrue(Files.isRegularFile(root.resolve("joining-ack-wire/complete.json")));
        assertFalse(Files.exists(root.resolve("index.json")));
    }
}
