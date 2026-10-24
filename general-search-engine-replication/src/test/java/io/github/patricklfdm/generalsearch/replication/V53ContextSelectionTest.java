package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextSelectionTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static V53ContextPublicationTest.Scenario reference;
    static Path prepared;
    static final List<String> CUTS=List.of("SELECTED_BEFORE_WRITE","SELECTED_WRITTEN","SELECTED_FORCED","SELECTED_BEFORE_RETURN");
    @BeforeAll static void prepareGroup()throws Exception {
        reference=new V53ContextPublicationTest().scenario();prepared=fixtures.resolve("prepared");
        V53JournalApplicationTest.copy(reference.evidence().resolve("carried-snapshots/source-retired"),prepared);
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(prepared,n,e->{})){owner.prepareCurrent(ballot(22));}
    }
    static Map<String,Object> ballot(long n){return reference.seed().fixture().f.initial.application.f.f.f.fixture.source.ballot(n);}
    static MembershipGrantJournal open(Path group,int n,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=reference.seed().fixture().f;assertEquals(0,f.resources.usage().leases());
        return MembershipGrantJournal.openContextual(group.resolve("node-"+n),f.initial.application.f.f.f.root(),V53DeclarationsTest.node(n),f.resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,e->{V53RetirementImagesTest.bounded(f.resources);cut.at(e);});
    }
    static List<MembershipSelection.Source> sources(Path group)throws Exception {
        var values=new ArrayList<MembershipSelection.Source>();for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})){values.add(owner.originalSource());}return values;
    }
    Path copy(String name)throws Exception {Path p=temp.resolve(name);V53JournalApplicationTest.copy(prepared,p);return p;}
    static void stable(Path group,int n,MembershipGrantJournal owner)throws Exception {
        Path initial=reference.evidence().resolve("carried-snapshots/source-retired/node-"+n),node=group.resolve("node-"+n);
        assertArrayEquals(Files.readAllBytes(initial.resolve("pending.accept")),owner.retainPendingContext().vote().bytes());
        assertArrayEquals(Files.readAllBytes(initial.resolve("selector.gsr")),Files.readAllBytes(node.resolve("selector.gsr")));
        assertEquals(6,reference.seed().fixture().f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
    }
    @Test void actualQuorumFixesOneCarriedSelectionAndContinuesWithNewCapturedBallot()throws Exception {
        Path group=copy("clean"),raw=Path.of("target/v53-context-selection/run-"+UUID.randomUUID());Files.createDirectories(raw);
        V53JournalApplicationTest.copy(reference.evidence(),raw.resolve("reference"));V53JournalApplicationTest.copy(group,raw.resolve("prepared"));
        var offered=sources(group);byte[] selected=null;
        for(int n:V53ContextPublicationTest.NODES) {
            var events=new ArrayList<String>();Path node=group.resolve("node-"+n);
            try(var owner=open(group,n,events::add)) {
                events.clear();var decision=owner.selectCurrent(offered,List.of());events.add("EXPLICIT_SELECTED_RETURNED");
                if(selected!=null)assertArrayEquals(selected,decision.bytes());selected=decision.bytes();
                assertEquals(reference.seed().entry().digest(),decision.value().get("nextEntry"));
                assertArrayEquals(decision.bytes(),owner.selectCurrent(offered,List.of()).bytes());events.add("EXPLICIT_SELECTED_RETURNED");
                var before=V53BootstrapProgressResumeTest.safeFiles(node);
                var other=offered.subList(0,2);assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(other,List.of()));
                assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));stable(group,n,owner);
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());Files.write(raw.resolve("events-"+n+".json"),canonical(events,65536));
        }
        V53JournalApplicationTest.copy(group,raw.resolve("selected"));
        var old=new TreeMap<Integer,String>();
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            old.put(n,(String)owner.originalBasis().orElseThrow().value().get("basisId"));owner.prepareCurrent(ballot(23));
        }
        V53JournalApplicationTest.copy(group,raw.resolve("next-prepared"));offered=sources(group);
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            owner.selectCurrent(offered,List.of());owner.retireSource(old.get(n));stable(group,n,owner);
        }
        V53JournalApplicationTest.copy(group,raw.resolve("continued"));
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-selection-v1","status","PASS","nodes",3,
                "ballots",List.of(22,23),"installedBallot",21,"originalVote",20,"freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextSelectionEvidence="+raw.toAbsolutePath());
    }
    @Test void everySelectionCutReopensWithoutAnImplicitResponse()throws Exception {
        Path raw=Path.of("target/v53-context-selection-cuts/run-"+UUID.randomUUID());Files.createDirectories(raw);
        V53JournalApplicationTest.copy(reference.evidence(),raw.resolve("reference"));V53JournalApplicationTest.copy(prepared,raw.resolve("prepared"));
        for(String point:CUTS) {
            Path group=copy(point),row=Files.createDirectory(raw.resolve(point));var offered=sources(group);var first=new ArrayList<String>();boolean[] armed={false};
            try(var owner=open(group,1,e->{first.add(e);if(armed[0] && e.equals(point))throw new IOException("selection cut");})) {
                first.clear();armed[0]=true;assertEquals("selection cut",assertThrows(IOException.class,()->owner.selectCurrent(offered,List.of())).getMessage());
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());V53JournalApplicationTest.copy(group.resolve("node-1"),row.resolve("crash"));
            var second=new ArrayList<String>();assertEquals("again",assertThrows(IOException.class,()->open(group,1,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("again");})).getMessage());
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());V53JournalApplicationTest.copy(group.resolve("node-1"),row.resolve("recovery-crash"));
            var resumed=new ArrayList<String>();
            try(var owner=open(group,1,resumed::add)) {
                assertFalse(resumed.contains("SELECTED_BEFORE_RETURN"));V53JournalContextTest.noAck(resumed);resumed.add("OPEN_RETURNED");
                var decision=owner.selectCurrent(offered,List.of());resumed.add("EXPLICIT_SELECTED_RETURNED");
                assertArrayEquals(decision.bytes(),owner.selectCurrent(offered,List.of()).bytes());resumed.add("EXPLICIT_SELECTED_RETURNED");stable(group,1,owner);
                new V53MembershipOwnershipTest().probe(group.resolve("node-1/replica.lock"));
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());V53JournalApplicationTest.copy(group.resolve("node-1"),row.resolve("final"));
            Files.write(row.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",resumed),131072));
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-selection-cuts-v1","status","PASS","cuts",CUTS,
                "interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextSelectionCuts="+raw.toAbsolutePath());
    }
    @Test void higherObservationFencesOriginalSelectionReturn()throws Exception {
        for(String point:CUTS) {
            Path group=copy("fence-"+point);var offered=sources(group);var ref=new MembershipGrantJournal[1];
            try(var owner=open(group,1,e->{if(ref[0]!=null && e.equals(point))ref[0].observeCurrent(ballot(23));})) {
                ref[0]=owner;assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(offered,List.of()));
            }
            var events=new ArrayList<String>();try(var owner=open(group,1,events::add)) {
                assertFalse(events.contains("SELECTED_BEFORE_RETURN"));V53JournalContextTest.noAck(events);stable(group,1,owner);
                assertEquals(!point.equals("SELECTED_BEFORE_WRITE"),owner.originalSelection().isPresent());
            }assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
        }
    }
    @Test void unmarkedHigherPromiseCannotUseThePreviousCapturedQuorum()throws Exception {
        Path group=copy("unmarked");var offered=sources(group);boolean[] armed={false};
        try(var owner=open(group,1,e->{if(armed[0] && e.equals("PROMISE_FORCED"))throw new IOException("unmarked");})) {
            armed[0]=true;assertThrows(IOException.class,()->owner.prepareCurrent(ballot(23)));
        }
        try(var owner=open(group,1,e->{})) {
            var before=V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-1"));
            assertEquals("context selection requires latest protected capture",assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(offered,List.of())).getMessage());
            assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-1")));owner.prepareCurrent(ballot(24));
        }assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
    }
    @Test void installedBackingDoesNotBecomeAnotherSelectionPermission()throws Exception {
        Path group=temp.resolve("installed");V53JournalApplicationTest.copy(reference.evidence().resolve("carried-snapshots/source-retired"),group);var offered=sources(group);
        try(var owner=open(group,1,e->{})) {
            var before=V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-1"));
            assertEquals("context selection requires latest protected capture",assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(offered,List.of())).getMessage());
            assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-1")));
        }assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
    }
}
