package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextSourceReleaseTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static Path base;static String predecessor,backing;
    static final List<String> CUTS=List.of("SOURCE_RETIREMENT_CREATED","SOURCE_RETIREMENT_WRITTEN",
            "SOURCE_RETIREMENT_FORCED","SOURCE_RETIREMENT_PARENT_FORCED","JOURNAL_ROTATION_CREATED","JOURNAL_ROTATION_WRITTEN","JOURNAL_ROTATION_FORCED","JOURNAL_ROTATION_RENAMED","JOURNAL_ROTATION_PARENT_FORCED",
            "SOURCE_RETIREMENT_JOURNAL_PRUNED","SOURCE_RETIREMENT_FILE_DELETED","SOURCE_RETIREMENT_DIRECTORY_DELETED",
            "SOURCE_RETIREMENT_CLEARED","SOURCE_RETIREMENT_BEFORE_RETURN");
    @BeforeAll static void originalRetirement()throws Exception {
        V53ContextRetirementTest.fixtures=Files.createDirectory(fixtures.resolve("seed"));V53ContextRetirementTest.actualOwners();
        var producer=new V53ContextRetirementTest();producer.temporary=Files.createDirectory(fixtures.resolve("retirement"));base=producer.completeScenario();
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(base.resolve("retired/pending.accept")));
        predecessor=(String)vote.promise().value().get("basisId");
        var r=V53ContextRetirementTest.resources();try(var owner=open(base.resolve("retired"),r,e->{})){backing=(String)owner.promised().orElseThrow().value().get("basisId");}
    }
    static MembershipGrantJournal open(Path node,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {return V53ContextRetirementTest.open(node,1,resources,cut);}
    Path copy(String name)throws Exception {Path result=temp.resolve(name);V53JournalApplicationTest.copy(base.resolve("retired"),result);return result;}
    static void done(Path node,MembershipGrantJournal owner)throws Exception {
        assertFalse(Files.exists(node.resolve("sources").resolve(predecessor)));assertTrue(Files.isDirectory(node.resolve("sources").resolve(backing)));
        assertArrayEquals(Files.readAllBytes(base.resolve("retired/pending.context")),Files.readAllBytes(node.resolve("pending.context")));
        assertArrayEquals(Files.readAllBytes(base.resolve("retired/pending.accept")),owner.retainPendingContext().vote().bytes());
        assertEquals(V53ContextRetirementTest.seed.phased().certificate().digest(),owner.currentCertificate().orElseThrow().digest());
    }
    @Test void exactSeparateBackingAllowsOriginalSourceRetirementAndReopen()throws Exception {releaseScenario();}
    Path releaseScenario()throws Exception {
        Path node=copy("clean"),evidence=Path.of("target/v53-context-source-release/run-"+UUID.randomUUID());Files.createDirectories(evidence);
        V53JournalApplicationTest.copy(base,evidence.resolve("original-retirement"));var r=V53ContextRetirementTest.resources();var events=new ArrayList<String>();int before,after;
        try(var owner=open(node,r,events::add)) {
            events.clear();before=r.usage().counts().get(MembershipResources.Unit.APPLICATION);
            var plan=owner.planSourceRetirement(predecessor);assertEquals(predecessor,plan.basisId);
            assertArrayEquals(plan.record.bytes(),owner.retireSource(predecessor).bytes());done(node,owner);
            after=r.usage().counts().get(MembershipResources.Unit.APPLICATION);assertTrue(after<before);
            assertThrows(IllegalArgumentException.class,()->owner.planSourceRetirement(backing));
            assertThrows(IllegalArgumentException.class,()->owner.retireSource(backing));
            new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
        }
        assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,evidence.resolve("released"));
        try(var owner=open(node,r,events::add)){done(node,owner);assertEquals(after,r.usage().counts().get(MembershipResources.Unit.APPLICATION));}
        assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,evidence.resolve("reopened"));V53JournalContextTest.noAck(events);
        Files.write(evidence.resolve("events.json"),canonical(events,1024*1024));Files.write(evidence.resolve("receipt.json"),canonical(Map.of(
                "schema","gse-v53-context-source-release-v1","status","PASS","predecessor",predecessor,"backing",backing,
                "beforeImages",before,"afterImages",after,"freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextSourceReleaseEvidence="+evidence.toAbsolutePath());return evidence;
    }
    @Test void repeatedInterruptionPreservesContextAndCompletesTheSameDeletion()throws Exception {
        Path evidence=Path.of("target/v53-context-source-release-cuts/run-"+UUID.randomUUID());Files.createDirectories(evidence);
        V53JournalApplicationTest.copy(base,evidence.resolve("original-retirement"));
        for(String point:CUTS) {
            Path node=copy(point),raw=Files.createDirectory(evidence.resolve(point));var r=V53ContextRetirementTest.resources();boolean[] hit={false};
            var first=new ArrayList<String>();var second=new ArrayList<String>();var resume=new ArrayList<String>();
            try(var owner=open(node,r,e->{first.add(e);if(e.equals(point)){hit[0]=true;throw new IOException("first cut");}})) {
                first.clear();
                assertEquals("first cut",assertThrows(IOException.class,()->owner.retireSource(predecessor)).getMessage());assertTrue(hit[0],point);
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("crash"));
            assertEquals("second cut",assertThrows(IOException.class,()->open(node,r,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("second cut");})).getMessage());
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("recovery-crash"));
            try(var owner=open(node,r,resume::add)) {
                if(Files.exists(node.resolve("sources").resolve(predecessor)))owner.retireSource(predecessor);done(node,owner);
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("final"));
            for(var events:List.of(first,second,resume))V53JournalContextTest.noAck(events);
            Files.write(raw.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",resume),65536));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-source-release-cuts-v1","status","PASS",
                "cuts",CUTS,"interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextSourceReleaseCuts="+evidence.toAbsolutePath());
    }
    @Test void incompleteAuthorityCannotDeleteEitherSource()throws Exception {
        for(String change:List.of("context","torn-context","source","torn-source","floor","vote")) {
            Path node=copy("bad-"+change);var r=V53ContextRetirementTest.resources();
            Path path=node.resolve(switch(change) {
                case "context","torn-context"->"pending.context";
                case "source","torn-source"->"sources/"+backing+"/source.gscp";
                case "floor"->"floor-copies/floor.gsr";
                default->"pending.accept";
            });
            if(change.startsWith("torn-")){byte[] bytes=Files.readAllBytes(path);Files.write(path,Arrays.copyOf(bytes,bytes.length/2));}else Files.delete(path);
            var before=V53ReplayFilesTest.files(node);
            assertThrows(Exception.class,()->{try(var owner=open(node,r,e->{})){owner.retireSource(predecessor);}});
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,r.usage().leases());
            assertTrue(Files.isDirectory(node.resolve("sources").resolve(predecessor)));assertTrue(Files.isDirectory(node.resolve("sources").resolve(backing)));
        }
        Path initial=temp.resolve("generation-pinned");V53JournalApplicationTest.copy(base.resolve("initial"),initial);
        var r=V53ContextRetirementTest.resources();var before=V53ReplayFilesTest.files(initial);
        try(var owner=open(initial,r,e->{})) {
            assertThrows(IllegalArgumentException.class,()->owner.planSourceRetirement(predecessor));
            assertThrows(IllegalArgumentException.class,()->owner.retireSource(predecessor));
        }
        assertEquals(before,V53ReplayFilesTest.files(initial));assertEquals(0,r.usage().leases());
    }
    @Test void cleanupPreservesHigherObservationAndDoesNotAuthorizeAcknowledgement()throws Exception {
        Path node=copy("higher");var r=V53ContextRetirementTest.resources();var events=new ArrayList<String>();
        try(var owner=open(node,r,events::add)) {
            var high=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));high.put("counter",22L);
            owner.observeCurrent(high);events.clear();owner.retireSource(predecessor);done(node,owner);
            assertThrows(IllegalArgumentException.class,()->owner.acceptCurrent(V53ContextRetirementTest.seed.entry(),V53ContextRetirementTest.seed.payload()));
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(high));V53JournalContextTest.noAck(events);
        }
        assertEquals(0,r.usage().leases());
    }
}
