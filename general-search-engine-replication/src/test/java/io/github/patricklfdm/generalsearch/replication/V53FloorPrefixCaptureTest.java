package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53FloorPrefixCaptureTest {
    @TempDir Path temp;
    @Test void actualFloorCreationHandoffAndReleaseKeepWriterAndExactOriginalBytes()throws Exception {
        var helper=new V53FloorTest();helper.temp=temp;
        Path replica=temp.resolve("replica"),raw=Files.createDirectory(temp.resolve("raw"));
        var local=helper.copy(replica,3,0,1);var peer=helper.copy(temp.resolve("peer"),3,0,2);
        var f=new V53CurrentGenerationFixture(3,0,false);var resources=helper.resources();
        var capture=new V53RemoveRetirementCapture(raw,temp.resolve("captures"),true);
        var events=new ArrayList<Map<String,Object>>();
        try(var store=MembershipGrantJournal.openMaintenance(replica,f.root(),V53DeclarationsTest.node(1),resources,f::verify,point->{
            int at=events.size();events.add(Map.of("node","node-1","event",point));capture.at("node-1",replica,point,at);
        })) {
            store.establishFloor(List.of(local,peer),copy->{});store.releaseFloor();
            new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
        }
        capture.finishProcess(f.root().manifestDigest(),2,"CLOSED",canonical(events,1024*1024));
        assertEquals(0,resources.usage().leases());assertFalse(Files.exists(replica.resolve("floor-copies")));
        var points=new HashSet<String>();int count=0;
        try(var files=Files.list(capture.root)) {
            for(Path file:files.filter(p->p.getFileName().toString().startsWith("capture-")).toList()) {
                var value=object(parse(Files.readAllBytes(file),1024*1024));String point=(String)value.get("point");points.add(point);count++;
                assertEquals(V53RemoveRetirementCapture.FLOOR_SCHEMA,value.get("schema"));
                assertEquals(point.startsWith("FLOOR_RELEASE_")?"floor-release":"floor",value.get("kind"));
                assertEquals(point,events.get(Math.toIntExact(number(value.get("eventIndex")))).get("event"));
                var names=list(value.get("files")).stream().map(v->object(v).get("name")).toList();
                if(point.equals("FLOOR_BEFORE_RETURN"))assertTrue(names.contains("floor-copies/floor.gsr"));
                if(point.equals("FLOOR_RELEASE_BEFORE_RETURN"))assertFalse(names.contains("floor-copies"));
            }
        }
        var header=object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096));
        assertEquals(V53RemoveRetirementCapture.PROCESS_FLOOR_SCHEMA,header.get("schema"));assertEquals((long)count,header.get("captures"));
        assertTrue(points.containsAll(Set.of("FLOOR_RESERVED","FLOOR_COPY_HANDED_OFF","FLOOR_RELEASE_RELINQUISHED","FLOOR_RELEASE_FILE_DELETED")));
        assertFalse(points.contains("FLOOR_COPY_BEFORE_RETURN"));
    }
    @Test void separateFloorTransactionsCannotBeRelabelledOrClosedEarly()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("raw")),replica=Files.createDirectory(temp.resolve("replica"));
        Files.write(replica.resolve("empty"),new byte[0]);var capture=new V53RemoveRetirementCapture(raw,temp.resolve("captures"),true);
        capture.at("node-1",replica,"FLOOR_COPY_BEFORE_RETURN",0);
        capture.at("node-1",replica,"RETIREMENT_OLD_FILES_FORCED",1);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"FLOOR_PROPOSAL_WRITTEN",2));
        capture.at("node-1",replica,"FLOOR_RESERVED",3);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"FLOOR_RELEASE_AUTHORITY_CREATED",4));
        assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]));
        capture.at("node-1",replica,"FLOOR_BEFORE_RETURN",5);
        capture.at("node-1",replica,"FLOOR_RELEASE_AUTHORITY_CREATED",6);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"FLOOR_RELEASE_AUTHORITY_WRITTEN",6));
        capture.at("node-1",replica,"FLOOR_RELEASE_BEFORE_RETURN",7);
        assertThrows(IllegalArgumentException.class,()->capture.finishCarried("FINAL"));
        capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]);
    }
}
