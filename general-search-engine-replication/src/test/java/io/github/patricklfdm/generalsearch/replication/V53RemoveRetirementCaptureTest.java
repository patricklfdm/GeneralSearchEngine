package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53RemoveRetirementCaptureTest {
    @TempDir Path temp;
    @Test void processCollectionBindsEmptyPreRetirementCrashAndRejectsUnfinishedTransactions()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("raw")),replica=Files.createDirectory(temp.resolve("authority"));
        Files.write(replica.resolve("empty"),new byte[0]);byte[] events=canonical(List.of(),4096);String root=hash(new byte[0]);
        var empty=new V53RemoveRetirementCapture(raw,temp.resolve("empty-prefix"));
        assertThrows(IllegalArgumentException.class,()->empty.finishProcess(root,2,"CUT_PREFIX",events));
        empty.finishProcess(root,1,"CUT_PREFIX",events);
        var value=object(parse(Files.readAllBytes(empty.root.resolve("collection.json")),4096));
        assertEquals(V53RemoveRetirementCapture.PROCESS_SCHEMA,value.get("schema"));assertEquals(0L,value.get("captures"));
        assertEquals(0L,value.get("storedBytes"));assertEquals(ProcessHandle.current().pid(),value.get("pid"));
        assertEquals(hash(events),value.get("eventsSha256"));assertEquals(root,value.get("root"));
        assertThrows(IllegalArgumentException.class,()->empty.finishProcess(root,1,"CUT_PREFIX",events));
        var pending=new V53RemoveRetirementCapture(raw,temp.resolve("pending-prefix"));
        pending.at("node-1",replica,"RETIREMENT_OLD_FILES_FORCED",0);
        assertThrows(IllegalArgumentException.class,()->pending.finishProcess(root,1,"CUT_PREFIX",events));
        pending.at("node-1",replica,"RETIREMENT_BEFORE_RETURN",1);
        pending.finishProcess(root,2,"CLOSED",events);
        assertEquals(2L,object(parse(Files.readAllBytes(pending.root.resolve("collection.json")),4096)).get("captures"));
    }
    @Test void capturesRealSourceRetirementWithoutChangingTheTraceOrWriterLock()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("run-source")),replica=temp.resolve("authority");
        String id=V53SourceReleaseWorker.provision(replica,3,0);var capture=new V53RemoveRetirementCapture(raw);
        var events=new ArrayList<Map<String,Object>>();var f=new V53CurrentGenerationFixture(3,0,false);
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openReclaiming(replica,f.root(),V53DeclarationsTest.node(1),resources,f::verify,point->{
            int at=events.size();events.add(Map.of("node","node-1","event",point));capture.at("node-1",replica,point,at);
        })) {
            owner.retireSource(id);new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
        }
        Files.write(raw.resolve("events.json"),canonical(events,1024*1024));Files.write(raw.resolve("transition-round-result.json"),new byte[0]);
        capture.finish("4-REMOVE");var header=object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096));
        assertEquals(15L,header.get("captures"));assertEquals(0,resources.usage().leases());
        assertEquals(hash(Files.readAllBytes(raw.resolve("events.json"))),header.get("eventsSha256"));
        assertTrue(events.stream().allMatch(row->row.keySet().equals(Set.of("node","event"))));
        assertThrows(IllegalArgumentException.class,()->capture.finish("4-REMOVE"));
        assertThrows(FileAlreadyExistsException.class,()->new V53RemoveRetirementCapture(raw));
    }
    @Test void capturesBorrowedGenerationIncludingThePartialBindingAndBothDeletionKinds()throws Exception {
        var fixture=new V53RetirementImagesTest();fixture.temp=temp;
        Path replica=fixture.provision("authority",5,0),raw=Files.createDirectory(temp.resolve("run-generation"));
        var capture=new V53RemoveRetirementCapture(raw);var events=new ArrayList<Map<String,Object>>();var index=new AtomicInteger();
        var used=fixture.resources();
        try(var owner=fixture.open(replica,5,0,used,point->{
            int at=index.getAndIncrement();events.add(Map.of("node","node-1","event",point));capture.at("node-1",replica,point,at);
        })) {owner.retireInactive();new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));}
        Files.write(raw.resolve("events.json"),canonical(events,1024*1024));Files.write(raw.resolve("transition-round-result.json"),new byte[0]);capture.finish("5-REMOVE");
        Set<String> points=new HashSet<>();
        try(var paths=Files.list(capture.root)) {
            for(Path p:paths.filter(v->v.getFileName().toString().startsWith("capture-")).toList()) {
                var value=object(parse(Files.readAllBytes(p),1024*1024));points.add((String)value.get("point"));
                assertEquals("generation",value.get("kind"));assertEquals(value.get("point"),events.get(Math.toIntExact(number(value.get("eventIndex")))).get("event"));
            }
        }
        assertTrue(points.containsAll(Set.of("RETIREMENT_BORROW_PREFIX_WRITTEN","RETIREMENT_FILE_DELETED","RETIREMENT_SAVED_FILE_DELETED","RETIREMENT_BEFORE_RETURN")));
        assertEquals(0,used.usage().leases());
    }
    @Test void refusesMissingStartNestedTransactionsReorderedCallbacksAndPrematureFinish()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("run")),replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("empty"),new byte[0]);
        var capture=new V53RemoveRetirementCapture(raw);
        capture.at("node-1",replica,"JOURNAL_ROTATION_CREATED",0);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"RETIREMENT_CREATED",1));
        capture.at("node-1",replica,"RETIREMENT_OLD_FILES_FORCED",2);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"RETIREMENT_OLD_FILES_FORCED",3));
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"SOURCE_RETIREMENT_CREATED",3));
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"RETIREMENT_CREATED",2));
        assertThrows(IllegalArgumentException.class,()->capture.finish("4-REMOVE"));
    }
    @Test void carriedCollectionBindsItsOwnKindAndResultAfterClosedTransactions()throws Exception {
        for(String kind:List.of("INTENT","FINAL")) {
            Path raw=Files.createDirectory(temp.resolve(kind)),replica=Files.createDirectory(temp.resolve(kind+"-replica"));
            Files.write(replica.resolve("empty"),new byte[0]);var capture=new V53RemoveRetirementCapture(raw);
            capture.at("node-1",replica,"RETIREMENT_OLD_FILES_FORCED",0);
            assertThrows(IllegalArgumentException.class,()->capture.finishCarried(kind));
            capture.at("node-1",replica,"RETIREMENT_BEFORE_RETURN",1);
            Files.write(raw.resolve("events.json"),canonical(List.of(),4096));
            Files.write(raw.resolve("transition-round-result.json"),canonical(Map.of("profile","4-REMOVE"),4096));
            assertThrows(ReplicationException.class,()->capture.finishCarried(kind));
            assertThrows(IllegalArgumentException.class,()->capture.finishCarried("4-REMOVE"));
            assertThrows(IllegalArgumentException.class,()->capture.finish(kind));
            byte[] result=canonical(Map.of("kind",kind),4096);Files.write(raw.resolve("carried-transition-result.json"),result);
            capture.finishCarried(kind);var header=object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096));
            assertEquals(V53RemoveRetirementCapture.CARRIED_SCHEMA,header.get("schema"));assertEquals(kind,header.get("profile"));
            assertEquals(hash(result),header.get("resultSha256"));assertEquals(2L,header.get("captures"));
            assertThrows(IllegalArgumentException.class,()->capture.finishCarried(kind));
        }
    }
}
