package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextBackingRetirementTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static Path base;
    static final List<String> CUTS=V53ContextSourceReleaseTest.CUTS;
    @BeforeAll static void original()throws Exception {
        V53ContextCaptureTest.fixtures=Files.createDirectory(fixtures.resolve("seed"));V53ContextCaptureTest.retainedOriginal();
        base=V53ContextCaptureTest.base;
    }
    static MembershipGrantJournal open(Path node,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {
        return V53ContextCaptureTest.open(node,r,cut);
    }
    Path copy(String name)throws Exception {Path p=temp.resolve(name);V53JournalApplicationTest.copy(base.resolve("reopened"),p);return p;}
    static Map<String,Object> ballot(long counter)throws Exception {return V53ContextCaptureTest.ballot(counter);}
    static String capture(MembershipGrantJournal owner,long counter)throws Exception {return (String)owner.prepareCurrent(ballot(counter)).value().get("basisId");}
    static void pinned(Path node,MembershipGrantJournal owner,String backing)throws Exception {
        assertArrayEquals(Files.readAllBytes(base.resolve("reopened/pending.accept")),owner.retainPendingContext().vote().bytes());
        assertTrue(Files.isDirectory(node.resolve("sources").resolve(V53ContextSourceReleaseTest.backing)));
        assertEquals(backing,MembershipPendingContext.backingBasis(MembershipPendingContext.decode(Files.readAllBytes(node.resolve("pending.context")))).value().get("basisId"));
    }
    @Test void repeatedCaptureRetiresOnlyCoveredBackingWithinFrozenImageBound()throws Exception {
        Path node=copy("cycle"),raw=Path.of("target/v53-context-backing-retirement/run-"+UUID.randomUUID());Files.createDirectories(raw);
        V53JournalApplicationTest.copy(base,raw.resolve("reference"));var r=V53ContextRetirementTest.resources();String previous=null;
        for(long counter=22;counter<=28;counter++) {
            Path round=Files.createDirectory(raw.resolve("round-"+counter));var events=new ArrayList<String>();
            try(var owner=open(node,r,events::add)) {
                events.clear();String next=capture(owner,counter);events.add("EXPLICIT_GRANT_RETURNED");
                assertEquals(previous==null?6:7,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                V53ContextRetirementTest.snapshotOwned(node,round.resolve("captured"));
                if(previous!=null) {
                    byte[] context=Files.readAllBytes(node.resolve("pending.context"));
                    owner.planSourceRetirement(previous);owner.retireSource(previous);
                    assertFalse(Files.exists(node.resolve("sources").resolve(previous)));assertArrayEquals(context,Files.readAllBytes(node.resolve("pending.context")));
                }
                assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));pinned(node,owner,next);
                var before=V53BootstrapProgressResumeTest.safeFiles(node);
                assertThrows(IllegalArgumentException.class,()->owner.planSourceRetirement(next));
                assertThrows(IllegalArgumentException.class,()->owner.retireSource(next));
                assertThrows(IllegalArgumentException.class,()->owner.planSourceRetirement(V53ContextSourceReleaseTest.backing));
                assertThrows(IllegalArgumentException.class,()->owner.retireSource(V53ContextSourceReleaseTest.backing));
                assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
                previous=next;
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,round.resolve("retired"));
            Files.write(round.resolve("events.json"),canonical(events,131072));
        }
        try(var owner=open(node,r,e->{})){pinned(node,owner,previous);assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));}
        assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("reopened"));
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-backing-retirement-v1","status","PASS",
                "rounds",List.of(22,23,24,25,26,27,28),"peakImages",7,"steadyImages",6,"freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextBackingRetirementEvidence="+raw.toAbsolutePath());
    }
    @Test void everyDeletionCutReopensAfterRepeatedInterruption()throws Exception {
        Path seed=copy("cuts-seed");var r=V53ContextRetirementTest.resources();String old,newest;
        try(var owner=open(seed,r,e->{})){old=capture(owner,22);newest=capture(owner,23);}
        Path raw=Path.of("target/v53-context-backing-retirement-cuts/run-"+UUID.randomUUID());Files.createDirectories(raw);
        V53JournalApplicationTest.copy(base,raw.resolve("reference"));V53JournalApplicationTest.copy(seed,raw.resolve("initial"));
        for(String point:CUTS) {
            Path node=temp.resolve(point),row=Files.createDirectory(raw.resolve(point));V53JournalApplicationTest.copy(seed,node);
            var first=new ArrayList<String>();var second=new ArrayList<String>();var resume=new ArrayList<String>();boolean[] armed={false};
            try(var owner=open(node,r,e->{first.add(e);if(armed[0] && e.equals(point))throw new IOException("retirement cut");})) {
                first.clear();armed[0]=true;assertEquals("retirement cut",assertThrows(IOException.class,()->owner.retireSource(old)).getMessage());
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,row.resolve("crash"));
            assertEquals("second cut",assertThrows(IOException.class,()->open(node,r,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("second cut");})).getMessage());
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,row.resolve("recovery-crash"));
            try(var owner=open(node,r,resume::add)) {
                if(Files.exists(node.resolve("sources").resolve(old)))owner.retireSource(old);
                pinned(node,owner,newest);assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,row.resolve("final"));
            for(var events:List.of(first,second,resume))V53JournalContextTest.noAck(events);
            Files.write(row.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",resume),131072));
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-backing-retirement-cuts-v1","status","PASS",
                "cuts",CUTS,"interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextBackingRetirementCuts="+raw.toAbsolutePath());
    }
    @Test void savedDecisionSurvivesTwoDeletionInterruptionsWithoutOriginalJournalFrames()throws Exception {
        Path node=copy("twice");var r=V53ContextRetirementTest.resources();String old,newest;boolean[] armed={false};
        try(var owner=open(node,r,e->{if(armed[0] && e.equals("SOURCE_RETIREMENT_FILE_DELETED"))throw new IOException("first deletion");})) {
            old=capture(owner,22);newest=capture(owner,23);armed[0]=true;
            assertEquals("first deletion",assertThrows(IOException.class,()->owner.retireSource(old)).getMessage());
        }
        assertEquals(0,r.usage().leases());
        assertEquals("second deletion",assertThrows(IOException.class,()->open(node,r,e->{if(e.equals("SOURCE_RETIREMENT_DIRECTORY_DELETED"))throw new IOException("second deletion");})).getMessage());
        assertEquals(0,r.usage().leases());
        try(var owner=open(node,r,e->{})){pinned(node,owner,newest);assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));capture(owner,24);}
        assertEquals(0,r.usage().leases());
    }
    @Test void higherObservationRemainsFencedAcrossIntermediateCleanup()throws Exception {
        Path node=copy("fence");var r=V53ContextRetirementTest.resources();var events=new ArrayList<String>();
        try(var owner=open(node,r,events::add)) {
            String old=capture(owner,22),newest=capture(owner,23);owner.observeCurrent(ballot(29));events.clear();owner.retireSource(old);
            pinned(node,owner,newest);V53JournalContextTest.noAck(events);
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(ballot(23)));
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(ballot(28)));
            capture(owner,29);
        }assertEquals(0,r.usage().leases());
    }
    @Test void changedContextBackingAndOriginalVoteRefuseBeforeDeletion()throws Exception {
        for(String change:List.of("context","backing","floor","vote","intermediate")) {
            Path node=copy(change);var r=V53ContextRetirementTest.resources();String old,newest;
            try(var owner=open(node,r,e->{})){old=capture(owner,22);newest=capture(owner,23);}
            Path path=node.resolve(switch(change){case "context"->"pending.context";case "backing"->"sources/"+newest+"/source.gscp";
                case "floor"->"floor-copies/floor.gsr";case "intermediate"->"sources/"+old+"/source.gscp";default->"pending.accept";});
            byte[] bytes=Files.readAllBytes(path);bytes[bytes.length-1]^=1;Files.write(path,bytes);
            var before=V53ReplayFilesTest.files(node);
            assertThrows(Exception.class,()->{try(var owner=open(node,r,e->{})){owner.retireSource(old);}});
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,r.usage().leases());
        }
    }
    @Test void changedSavedDecisionCannotAuthorizeCoveredOrPinnedSource()throws Exception {
        Path seed=copy("decision-seed");var r=V53ContextRetirementTest.resources();boolean[] armed={false};
        try(var owner=open(seed,r,e->{if(armed[0] && e.equals("SOURCE_RETIREMENT_JOURNAL_PRUNED"))throw new IOException("decision cut");})) {
            String old=capture(owner,22);capture(owner,23);armed[0]=true;assertThrows(IOException.class,()->owner.retireSource(old));
        }
        assertEquals(0,r.usage().leases());
        for(String change:List.of("accepted","installed-ballot","backing-ballot")) {
            Path node=temp.resolve("decision-"+change);V53JournalApplicationTest.copy(seed,node);
            var saved=new MembershipSourceRetirementFiles(node).decision().orElseThrow();
            var p=new TreeMap<>(saved.promise().value());var b=new TreeMap<>(saved.basis().value());
            if(change.equals("accepted"))b.put("accepted",null);
            else {var ballot=new TreeMap<>(object(p.get("ballot")));ballot.put("counter",change.equals("installed-ballot")?21L:23L);p.put("ballot",ballot);b.put("ballot",ballot);}
            var altered=new MembershipSourceRetirementFiles.Decision(saved.record(),decode(encode("records","PROMISE",p),"records","PROMISE"),
                    decode(encode("records","BASIS",b),"records","BASIS"),saved.capsule());
            Files.write(node.resolve(MembershipSourceRetirementFiles.FILE),altered.bytes());var before=V53ReplayFilesTest.files(node);
            assertEquals("context source retirement requires covered intermediate backing",assertThrows(IllegalArgumentException.class,()->open(node,r,e->{})).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,r.usage().leases());
        }
    }
}
