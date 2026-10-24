package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextCaptureTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static Path base;
    static final List<String> CUTS=new ArrayList<>();
    static {
        CUTS.addAll(V53CaptureRecoveryWorker.CUTS.subList(0,20));CUTS.add("BASIS_PREFIX_WRITTEN");
        CUTS.addAll(List.of("CONTEXT_SOURCE_MEMBER_FORCED","CONTEXT_SOURCE_DIRECTORY_FORCED","CONTEXT_SOURCE_PARENT_FORCED",
                "CONTEXT_CANDIDATE_CREATED","CONTEXT_PREFIX_WRITTEN","CONTEXT_CANDIDATE_WRITTEN","CONTEXT_CANDIDATE_FORCED",
                "CONTEXT_CANDIDATE_PARENT_FORCED","CONTEXT_RENAMED","CONTEXT_PARENT_FORCED"));
        CUTS.addAll(V53CaptureRecoveryWorker.CUTS.subList(20,23));
    }
    @BeforeAll static void retainedOriginal()throws Exception {
        V53ContextSourceReleaseTest.fixtures=Files.createDirectory(fixtures.resolve("seed"));V53ContextSourceReleaseTest.originalRetirement();
        var producer=new V53ContextSourceReleaseTest();producer.temp=Files.createDirectory(fixtures.resolve("release"));base=producer.releaseScenario();
    }
    static MembershipGrantJournal open(Path path,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {return V53ContextSourceReleaseTest.open(path,r,cut);}
    Path copy(String name)throws Exception {Path path=temp.resolve(name);V53JournalApplicationTest.copy(base.resolve("reopened"),path);return path;}
    static Map<String,Object> ballot(long n)throws Exception {
        var context=MembershipPendingContext.decode(Files.readAllBytes(base.resolve("reopened/pending.context")));
        var value=new TreeMap<>(object(MembershipPendingContext.backingPromise(context).value().get("ballot")));value.put("counter",n);return value;
    }
    static void original(Path node,MembershipGrantJournal owner,byte[] vote)throws Exception {
        assertArrayEquals(vote,Files.readAllBytes(node.resolve("pending.accept")));assertArrayEquals(vote,owner.retainPendingContext().vote().bytes());
        assertEquals(MembershipPendingAccept.decode(vote).certificate().digest(),owner.currentCertificate().orElseThrow().digest());
    }
    @Test void actualProtectedCapturesRebindSameOriginalAndRespectImageBound()throws Exception {
        Path node=copy("clean");var r=V53ContextRetirementTest.resources();byte[] vote=Files.readAllBytes(node.resolve("pending.accept"));
        Path evidence=Path.of("target/v53-context-capture/run-"+UUID.randomUUID());Files.createDirectories(evidence);V53JournalApplicationTest.copy(base,evidence.resolve("reference"));
        for(long counter:List.of(22L,23L)) {
            var events=new ArrayList<String>();
            try(var owner=open(node,r,events::add)) {
                events.clear();
                var basis=owner.prepareCurrent(ballot(counter));events.add("EXPLICIT_GRANT_RETURNED");original(node,owner,vote);
                var context=MembershipPendingContext.decode(Files.readAllBytes(node.resolve("pending.context")));
                assertArrayEquals(basis.bytes(),MembershipPendingContext.backingBasis(context).bytes());
                assertArrayEquals(basis.bytes(),owner.prepareCurrent(ballot(counter)).bytes());events.add("EXPLICIT_GRANT_RETURNED");
                assertEquals(counter-16,r.usage().counts().get(MembershipResources.Unit.APPLICATION).longValue());
                assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(V53ContextRetirementTest.seed.entry(),V53ContextRetirementTest.seed.payload()));
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,evidence.resolve("round-"+counter));
            Files.write(evidence.resolve("events-"+counter+".json"),canonical(events,65536));
        }
        try(var owner=open(node,r,e->{})) {
            var before=V53BootstrapProgressResumeTest.safeFiles(node);var usage=r.usage();
            assertThrows(MembershipOperationException.class,()->owner.prepareCurrent(ballot(24)));
            assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));assertEquals(usage,r.usage());original(node,owner,vote);
        }assertEquals(0,r.usage().leases());
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-capture-v1","status","PASS","rounds",List.of(22,23),
                "maximumImages",7,"nextCapture","CAPACITY_EXCEEDED","runtimeEnabled",false,"selectedInstallEnabled",false),16384));
        System.out.println("v53ContextCaptureEvidence="+evidence.toAbsolutePath());
    }
    @Test void noMarkerAfterPromiseRequiresFreshBallotAndKeepsOriginal()throws Exception {
        for(String cut:List.of("PROMISE_WRITTEN","PROMISE_FORCED")) {
            Path node=copy(cut);var r=V53ContextRetirementTest.resources();byte[] vote=Files.readAllBytes(node.resolve("pending.accept"));boolean[] armed={false};
            try(var owner=open(node,r,e->{if(armed[0] && e.equals(cut))throw new IOException("unmarked promise");})) {
                armed[0]=true;assertThrows(IOException.class,()->owner.prepareCurrent(ballot(22)));
            }
            assertFalse(Files.exists(node.resolve("source.capture.gsr")));assertEquals(0,r.usage().leases());
            try(var owner=open(node,r,e->{})) {
                original(node,owner,vote);assertTrue(owner.originalBasis().isEmpty());assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(ballot(22)));
                owner.prepareCurrent(ballot(23));original(node,owner,vote);
            }assertEquals(0,r.usage().leases());
        }
    }
    @Test void interruptedSourceAndContextReplacementResumeBeforeGrantReplay()throws Exception {
        Path evidence=Path.of("target/v53-context-capture-cuts/run-"+UUID.randomUUID());Files.createDirectories(evidence);V53JournalApplicationTest.copy(base,evidence.resolve("reference"));
        for(String point:CUTS) {
            Path node=copy(point);var r=V53ContextRetirementTest.resources();byte[] vote=Files.readAllBytes(node.resolve("pending.accept"));boolean[] armed={false};
            Path raw=Files.createDirectory(evidence.resolve(point));var first=new ArrayList<String>();
            try(var owner=open(node,r,e->{first.add(e);if(armed[0] && e.equals(point))throw new IOException("capture cut");})) {
                first.clear();armed[0]=true;assertEquals("capture cut",assertThrows(IOException.class,()->owner.prepareCurrent(ballot(22))).getMessage());
            }assertEquals(0,r.usage().leases());
            V53JournalApplicationTest.copy(node,raw.resolve("crash"));var second=new ArrayList<String>();
            assertEquals("second capture cut",assertThrows(IOException.class,()->open(node,r,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("second capture cut");})).getMessage());
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("recovery-crash"));V53JournalContextTest.noAck(second);
            var events=new ArrayList<String>();
            try(var owner=open(node,r,events::add)) {
                V53JournalContextTest.noAck(events);events.add("OPEN_RETURNED");original(node,owner,vote);
                V53ContextRetirementTest.snapshotOwned(node,raw.resolve("reopened"));new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
                var basis=owner.originalBasis().orElseThrow();assertArrayEquals(basis.bytes(),owner.prepareCurrent(ballot(22)).bytes());events.add("EXPLICIT_GRANT_RETURNED");
                assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }assertEquals(0,r.usage().leases());assertFalse(Files.exists(node.resolve("source.capture.gsr")));assertFalse(Files.exists(node.resolve("pending.context.next")));
            V53JournalApplicationTest.copy(node,raw.resolve("final"));Files.write(raw.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",events),131072));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-capture-cuts-v1","status","PASS","cuts",CUTS,
                "interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));System.out.println("v53ContextCaptureCuts="+evidence.toAbsolutePath());
    }
    @Test void higherObservationFencesReturnAcrossSourceBasisAndContextForces()throws Exception {
        for(String point:List.of("SOURCE_DIRECTORY_FORCED","BASIS_FORCED","CONTEXT_RENAMED","GRANT_BEFORE_RETURN")) {
            Path node=copy("fence-"+point);var r=V53ContextRetirementTest.resources();var ref=new MembershipGrantJournal[1];var events=new ArrayList<String>();
            try(var owner=open(node,r,e->{events.add(e);if(ref[0]!=null && e.equals(point))ref[0].observeCurrent(uncheckedBallot(23));})) {
                ref[0]=owner;events.clear();assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(ballot(22)));
            }assertEquals(0,r.usage().leases());events.clear();
            try(var owner=open(node,r,events::add)){V53JournalContextTest.noAck(events);assertEquals(22L,object(owner.originalBasis().orElseThrow().value().get("ballot")).get("counter"));}
            assertEquals(0,r.usage().leases());
        }
    }
    private static Map<String,Object> uncheckedBallot(long n){try{return ballot(n);}catch(Exception e){throw new AssertionError(e);}}
    @Test void journalCompletionCapacityRefusesBeforePromiseAndKeepsOwnerUsable()throws Exception {
        Path node=copy("journal-capacity");var r=V53ContextRetirementTest.resources();var f=V53ContextRetirementTest.seed.fixture().f;
        try(var owner=MembershipGrantJournal.openContextual(node,f.initial.application.f.f.f.root(),V53DeclarationsTest.node(1),r,
                (root,packet,images)->MembershipCapsule.verify(root,packet,images,f.observations),3*1024*1024,e->{})) {
            var before=V53BootstrapProgressResumeTest.safeFiles(node);var usage=r.usage();
            var error=assertThrows(MembershipOperationException.class,()->owner.prepareCurrent(ballot(22)));
            assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));assertEquals(usage,r.usage());
            assertArrayEquals(Files.readAllBytes(node.resolve("pending.accept")),owner.retainPendingContext().vote().bytes());
        }assertEquals(0,r.usage().leases());
    }
    @Test void damagedSourceAfterBasisAndForeignCandidateNeverRepair()throws Exception {
        for(String kind:List.of("packet","image","backing","candidate","intent")) {
            Path node=copy("damage-"+kind);var r=V53ContextRetirementTest.resources();boolean[] armed={false};
            String point=kind.equals("candidate")?"CONTEXT_PREFIX_WRITTEN":"BASIS_PREFIX_WRITTEN";
            try(var owner=open(node,r,e->{if(armed[0] && e.equals(point))throw new IOException("capture cut");})) {
                armed[0]=true;assertThrows(IOException.class,()->owner.prepareCurrent(ballot(22)));
            }
            Path source;try(var entries=Files.list(node.resolve("sources"))){source=entries.filter(p->!p.getFileName().toString().equals(V53ContextSourceReleaseTest.backing)).findFirst().orElseThrow();}
            Path p;
            if(kind.equals("packet"))p=source.resolve("source.gscp");
            else if(kind.equals("image")){try(var entries=Files.list(source)){p=entries.filter(x->x.toString().endsWith(".image")).findFirst().orElseThrow();}}
            else if(kind.equals("backing"))p=node.resolve("sources").resolve(V53ContextSourceReleaseTest.backing).resolve("source.gscp");
            else p=node.resolve(kind.equals("candidate")?"pending.context.next":"source.capture.gsr");
            byte[] bytes=Files.readAllBytes(p);bytes[bytes.length-1]^=1;Files.write(p,bytes);var before=V53BootstrapProgressResumeTest.safeFiles(node);
            assertThrows(Exception.class,()->open(node,r,e->{}));assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
        }
    }
    @Test void wellFormedStaleContextCandidateRefusesBeforeAnyRecoveryWrite()throws Exception {
        Path node=copy("stale-candidate");var r=V53ContextRetirementTest.resources();boolean[] armed={false};
        try(var owner=open(node,r,e->{if(armed[0] && e.equals("SOURCE_PACKET_PREFIX_WRITTEN"))throw new IOException("capture cut");})) {
            armed[0]=true;assertThrows(IOException.class,()->owner.prepareCurrent(ballot(22)));
        }
        Files.write(node.resolve("pending.context.next"),Files.readAllBytes(node.resolve("pending.context")));
        var before=V53BootstrapProgressResumeTest.safeFiles(node);
        assertEquals("pending context candidate differs from exact request",assertThrows(IllegalArgumentException.class,()->open(node,r,e->{})).getMessage());
        assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));assertEquals(0,r.usage().leases());
    }
}
