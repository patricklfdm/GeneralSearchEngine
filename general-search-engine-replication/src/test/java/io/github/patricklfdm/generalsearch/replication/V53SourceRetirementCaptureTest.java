package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SourceRetirementCaptureTest {
    @TempDir Path temp;
    @Test void retainsEveryRealPrefixAndPreservesTheWriterLock()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-source-retirement-capture/run-"+UUID.randomUUID()));
        Path replica=temp.resolve("authority");String id=V53SourceReleaseWorker.provision(replica,3,0);
        V53JournalApplicationTest.copy(replica,raw.resolve("initial"));
        V53JournalApplicationTest.copy(temp.resolve("inputs"),raw.resolve("inputs"));
        Files.copy(temp.resolve("fixture.json"),raw.resolve("fixture.json"));
        var events=new ArrayList<Map<String,Object>>();var capture=new V53SourceRetirementCapture(raw,events);
        var f=new V53CurrentGenerationFixture(3,0,false);var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openReclaiming(replica,f.root(),V53DeclarationsTest.node(1),resources,f::verify,point->{
            events.add(Map.of("node","node-1","scope","test-owner","event",point));
            capture.at("node-1","test-owner",replica,point);
        })) {
            owner.retireSource(id);
            new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
            assertFalse(Files.exists(replica.resolve("sources").resolve(id)));
        }
        assertEquals(0,resources.usage().leases());
        assertEquals(15,events.stream().filter(v->V53SourceRetirementCapture.EVENT.equals(v.get("event"))).count());
        V53JournalApplicationTest.copy(replica,raw.resolve("final"));
        Files.write(raw.resolve("events.json"),canonical(events,8*1024*1024),StandardOpenOption.CREATE_NEW);
        assertThrows(FileAlreadyExistsException.class,()->new V53SourceRetirementCapture(raw,new ArrayList<>()));
        System.out.println("v53SourceRetirementCaptureEvidence="+raw.toAbsolutePath());
    }
    @Test void refusesOrphanNestedOrForeignScopeWhileIgnoringUnrelatedRotation()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var capture=new V53SourceRetirementCapture(temp,events);
        Path replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("sources.retirement.gsr"),new byte[0]);
        capture.at("node-1","one",replica,"JOURNAL_ROTATION_CREATED");assertTrue(events.isEmpty());
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1","one",replica,"SOURCE_RETIREMENT_FORCED"));
        capture.at("node-1","one",replica,"SOURCE_RETIREMENT_CREATED");
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1","one",replica,"SOURCE_RETIREMENT_CREATED"));
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1","two",replica,"SOURCE_RETIREMENT_FORCED"));
        var trace=new V53JoiningTrace("node-4",events,new ArrayList<>());trace.retainRetirements(capture,replica);
        assertThrows(IllegalStateException.class,()->trace.retainRetirements(capture,replica));
    }
}
