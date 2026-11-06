package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CampaignPrefixCaptureTest {
    @TempDir Path temp;
    @Test void originalGrantSelectionAndInstallationRetainPrefixesAndWriter()throws Exception {
        Path replica=temp.resolve("replica"),raw=Files.createDirectory(temp.resolve("raw"));
        var f=new V53GenerationInstallFixture(3,0,1,true);f.initial.provision(replica);
        var capture=new V53RemoveRetirementCapture(raw,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.CAMPAIGN);
        var events=new ArrayList<Map<String,Object>>();var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var store=MembershipGrantJournal.openCapturing(replica,f.root(),V53DeclarationsTest.node(1),resources,f::verify,point->{
            int at=events.size();events.add(Map.of("node","node-1","event",point));capture.at("node-1",replica,point,at);
        })) {
            store.prepareCurrent(f.initial.fixture.source.ballot(20));store.selectCurrent(f.offers(store,20),f.bridges);
            store.installCurrent(f.offers(store,20),f.bridges,f.images());
            new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
        }
        capture.finishProcess(f.root().manifestDigest(),2,"CLOSED",canonical(events,1024*1024));
        var kinds=new HashSet<String>();var points=new HashSet<String>();
        try(var files=Files.list(capture.root)) {
            for(var file:files.filter(p->p.getFileName().toString().startsWith("capture-")).toList()) {
                var value=object(parse(Files.readAllBytes(file),1024*1024));
                assertEquals(V53RemoveRetirementCapture.CAMPAIGN_SCHEMA,value.get("schema"));
                kinds.add((String)value.get("kind"));points.add((String)value.get("point"));
                assertEquals(value.get("point"),events.get(Math.toIntExact(number(value.get("eventIndex")))).get("event"));
            }
        }
        assertEquals(Set.of("grant","selected","install"),kinds);
        assertTrue(points.containsAll(Set.of("CAPTURE_INTENT_PREFIX_WRITTEN","SOURCE_PACKET_PREFIX_WRITTEN","BASIS_PREFIX_WRITTEN",
                "SELECTED_FORCED","INSTALL_SELECTOR_WRITTEN","INSTALL_BEFORE_RETURN")));
        assertEquals(0,resources.usage().leases());
    }
    @Test void selectedReturnRequiresItsOwnInstallationAndCannotFinishEarly()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("raw")),replica=Files.createDirectory(temp.resolve("replica"));
        Files.write(replica.resolve("value"),new byte[0]);
        var capture=new V53RemoveRetirementCapture(raw,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.CAMPAIGN);
        capture.at("node-1",replica,"INSTALL_RESERVED",0); // publication/recovery installation outside a selection
        capture.at("node-1",replica,"FLOOR_RESERVED",1);
        capture.at("node-1",replica,"SELECTED_BEFORE_WRITE",2);
        capture.at("node-1",replica,"SELECTED_BEFORE_RETURN",3);
        assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"PROMISE_BEFORE_WRITE",4));
        capture.at("node-1",replica,"INSTALL_RESERVED",5);capture.at("node-1",replica,"INSTALL_BEFORE_RETURN",6);
        capture.at("node-1",replica,"INSTALL_RESERVED",7);
        capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]);
        var header=object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096));
        assertEquals(4L,header.get("captures"));assertEquals(V53RemoveRetirementCapture.PROCESS_CAMPAIGN_SCHEMA,header.get("schema"));
    }
    @Test void allocatorAndGrantTransactionsCannotOverlapOrUseLegacySchema()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("raw")),replica=Files.createDirectory(temp.resolve("replica"));
        Files.write(replica.resolve("value"),new byte[0]);
        var capture=new V53RemoveRetirementCapture(raw,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.CAMPAIGN);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"ALLOCATOR_WRITTEN",0));
        capture.at("node-1",replica,"ALLOCATOR_BEFORE_WRITE",1);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"PROMISE_BEFORE_WRITE",2));
        capture.at("node-1",replica,"ALLOCATOR_BEFORE_RETURN",3);
        capture.at("node-1",replica,"PROMISE_BEFORE_WRITE",4);capture.at("node-1",replica,"GRANT_BEFORE_RETURN",5);
        assertThrows(IllegalArgumentException.class,()->capture.finishCarried("INTENT"));
        capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]);
    }
}
