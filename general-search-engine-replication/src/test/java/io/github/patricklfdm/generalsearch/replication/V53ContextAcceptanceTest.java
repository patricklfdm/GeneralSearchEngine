package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextAcceptanceTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static Path base;
    static final List<String> CUTS=List.of("CONTEXT_ACCEPT_VALIDATED","ACCEPT_CANDIDATE_CREATED","ACCEPT_PREFIX_WRITTEN",
            "ACCEPT_CANDIDATE_WRITTEN","ACCEPT_CANDIDATE_FORCED","ACCEPT_CANDIDATE_PARENT_FORCED","ACCEPT_RENAMED",
            "ACCEPT_PARENT_FORCED","ACCEPT_ACTIVE_FORCED","ACCEPT_ACTIVE_PARENT_FORCED","CONTEXT_ACCEPT_SUCCESSOR_FORCED",
            "CONTEXT_REDUNDANT_DELETED","CONTEXT_REDUNDANT_PARENT_FORCED","CONTEXT_ACCEPT_CLEARED",
            "FLOOR_RELEASE_AUTHORITY_CREATED","FLOOR_RELEASE_AUTHORITY_WRITTEN","FLOOR_RELEASE_AUTHORITY_FORCED","FLOOR_RELEASE_PARENT_FORCED",
            "FLOOR_RELEASE_RELINQUISHED","FLOOR_RELEASE_FILE_DELETED","FLOOR_RELEASE_COPY_DELETED","FLOOR_RELEASE_PROPOSAL_CLEARED",
            "FLOOR_RELEASE_AUTHORITY_CLEARED","FLOOR_RELEASE_CLEARED","FLOOR_RELEASE_BEFORE_RETURN","CONTEXT_ACCEPT_BEFORE_RETURN");
    @BeforeAll static void retiredOriginal()throws Exception {
        V53ContextSourceReleaseTest.fixtures=Files.createDirectory(fixtures.resolve("source-seed"));V53ContextSourceReleaseTest.originalRetirement();
        var producer=new V53ContextSourceReleaseTest();producer.temp=Files.createDirectory(fixtures.resolve("source-release"));
        base=producer.releaseScenario();
    }
    Path copy(String name)throws Exception {Path result=temp.resolve(name);V53JournalApplicationTest.copy(base.resolve("reopened"),result);return result;}
    static MembershipGrantJournal open(Path node,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return V53ContextRetirementTest.open(node,1,resources,cut);
    }
    static MembershipContext.Owned accept(MembershipGrantJournal owner)throws Exception {
        return owner.acceptRetainedCurrent(V53ContextRetirementTest.seed.entry(),V53ContextRetirementTest.seed.payload());
    }
    static void completed(Path node,Map<String,String> before)throws Exception {
        var wanted=new TreeMap<>(before);wanted.remove(MembershipPendingContextFiles.FILE);wanted.remove(MembershipPendingAccept.FILE);
        wanted.keySet().removeIf(p->p.equals("floor-copies") || p.startsWith("floor-copies/"));
        var actual=new TreeMap<>(V53BootstrapProgressResumeTest.safeFiles(node));actual.remove(MembershipPendingAccept.FILE);
        assertEquals(wanted,actual);assertFalse(Files.exists(node.resolve(MembershipPendingAccept.NEXT)));
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
        assertArrayEquals(V53ContextRetirementTest.seed.entry().bytes(),vote.entry().bytes());assertArrayEquals(V53ContextRetirementTest.seed.payload(),vote.payload());
        assertNull(vote.proof());assertNull(vote.certificate());assertEquals(21L,object(vote.accept().value().get("ballot")).get("counter"));
        assertEquals(20L,object(vote.entry().value().get("origin")).get("counter"));
    }
    @Test void exactSuccessorIsForcedBeforeContextWithdrawalAndBothInterruptionAttemptsRecover()throws Exception {
        Path evidence=Path.of("target/v53-context-acceptance/run-"+UUID.randomUUID());Files.createDirectories(evidence);
        V53JournalApplicationTest.copy(base,evidence.resolve("original-source-release"));var rows=new ArrayList<Map<String,Object>>();
        for(int i=0;i<CUTS.size();i++) {
            String point=CUTS.get(i);Path node=copy("cut-"+i),raw=Files.createDirectory(evidence.resolve(String.format("case-%02d",i)));
            var before=V53BootstrapProgressResumeTest.safeFiles(node);var r=V53ContextRetirementTest.resources();var first=new ArrayList<String>();boolean[] armed={false};
            try(var owner=open(node,r,e->{if(armed[0]){first.add(e);if(e.equals(point))throw new IOException("first cut");}})) {
                armed[0]=true;assertEquals("first cut",assertThrows(IOException.class,()->accept(owner)).getMessage());
            }
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("first"));
            var second=new ArrayList<String>();
            assertEquals("second cut",assertThrows(IOException.class,()->{
                try(var owner=open(node,r,e->{second.add(e);if(e.equals("ACCEPT_ACTIVE_FORCED"))throw new IOException("second cut");})){accept(owner);}
            }).getMessage());
            assertEquals(0,r.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("second"));
            var resumed=new ArrayList<String>();
            try(var owner=open(node,r,resumed::add)) {
                var owned=accept(owner);assertEquals(owned,accept(owner));assertTrue(owner.currentCertificate().isEmpty());
                assertEquals(MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept"))).accept().digest(),owned.record());
                assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            assertEquals(0,r.usage().leases());completed(node,before);V53JournalApplicationTest.copy(node,raw.resolve("final"));
            Files.write(raw.resolve("events.json"),canonical(Map.of("first",first,"second",second,"resumed",resumed),1024*1024));
            rows.add(Map.of("case",raw.getFileName().toString(),"cut",point,"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-acceptance-v1","status","PASS","cases",rows,
                "freshProcesses",false,"runtimeEnabled",false,"sourceRetirement",true),16384));
        System.out.println("v53ContextAcceptanceEvidence="+evidence.toAbsolutePath());
    }
    @Test void changedEntryPayloadAndLaterObservationRefuseBeforeAnyReplacement()throws Exception {
        Path node=copy("refuse");var r=V53ContextRetirementTest.resources();var before=V53BootstrapProgressResumeTest.safeFiles(node);
        try(var owner=open(node,r,e->{})) {
            var entry=V53ContextRetirementTest.seed.entry();var value=new TreeMap<>(entry.value());value.put("origin",owner.promised().orElseThrow().value().get("ballot"));
            assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(decode(encode("records","ENTRY",value),"records","ENTRY"),V53ContextRetirementTest.seed.payload()));
            assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(entry,new byte[0]));
            var next=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));next.put("counter",24L);owner.observeCurrent(next);
            assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,()->accept(owner)).getMessage());
        }
        assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
    }
    @Test void missingOriginalOrForeignCandidateCannotAuthorizeWithdrawal()throws Exception {
        for(String kind:List.of("source","context","candidate","valid-foreign-candidate")) {
            Path node=copy(kind);var r=V53ContextRetirementTest.resources();
            if(kind.equals("source")) {
                try(var files=Files.walk(node.resolve("sources"))){Files.delete(files.filter(p->p.getFileName().toString().equals("source.gscp")).findFirst().orElseThrow());}
            }else if(kind.equals("context"))Files.writeString(node.resolve(MembershipPendingContextFiles.FILE),"torn");
            else if(kind.equals("valid-foreign-candidate")) {
                var old=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                Path current=node.resolve("generations").resolve((String)selector.value().get("generation"));
                var promise=decode(Files.readAllBytes(current.resolve("promise.gsr")),"records","PROMISE");
                var selected=decode(Files.readAllBytes(current.resolve("selected.gsr")),"records","SELECTED");
                var ballot=new TreeMap<>(object(promise.value().get("ballot")));ballot.put("counter",22L);
                var acceptance=new TreeMap<>(old.accept().value());acceptance.put("ballot",ballot);
                var foreign=new MembershipPendingAccept.Vote(selector,promise,selected,old.entry(),decode(encode("records","ACCEPT",acceptance),"records","ACCEPT"),old.payload());
                Files.write(node.resolve(MembershipPendingAccept.NEXT),foreign.bytes());
            }
            else Files.writeString(node.resolve(MembershipPendingAccept.NEXT),"foreign");
            var before=V53BootstrapProgressResumeTest.safeFiles(node);assertThrows(Exception.class,()->{try(var owner=open(node,r,e->{})){accept(owner);}});
            assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
        }
    }
    @Test void laterObservationAtEachAuthorityHandoffCannotReturnAnAcknowledgement()throws Exception {
        for(String point:List.of("CONTEXT_ACCEPT_VALIDATED","ACCEPT_RENAMED","CONTEXT_REDUNDANT_PARENT_FORCED","FLOOR_RELEASE_BEFORE_RETURN")) {
            Path node=copy("fenced-"+point);var r=V53ContextRetirementTest.resources();MembershipGrantJournal[] live={null};boolean[] hit={false};
            try(var owner=open(node,r,event->{if(event.equals(point) && live[0]!=null) {
                hit[0]=true;var high=new TreeMap<>(object(live[0].promised().orElseThrow().value().get("ballot")));high.put("counter",22L);live[0].observeCurrent(high);
            }})) {
                live[0]=owner;
                assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,()->accept(owner)).getMessage());
                assertTrue(hit[0],point);
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void extraReservationsCannotReturnAckAndExactRetryCompletesWithoutRollback()throws Exception {
        Path node=copy("pressure");var r=V53ContextRetirementTest.resources();var events=new ArrayList<String>();var before=V53BootstrapProgressResumeTest.safeFiles(node);
        try(var owner=open(node,r,events::add);
            var extra1=r.reserve(MembershipResources.Unit.APPLICATION,"external-pressure-1",MembershipResources.Unit.APPLICATION.bytes);
            var extra2=r.reserve(MembershipResources.Unit.APPLICATION,"external-pressure-2",MembershipResources.Unit.APPLICATION.bytes)) {
            events.clear();assertEquals("resource ownership/count",assertThrows(IllegalArgumentException.class,()->accept(owner)).getMessage());
            assertFalse(events.contains("CONTEXT_ACCEPT_BEFORE_RETURN"));V53JournalContextTest.noAck(events);
        }
        assertEquals(0,r.usage().leases());completed(node,before);
        try(var owner=open(node,r,e->{})){assertEquals(accept(owner),accept(owner));assertEquals(6,r.usage().counts().get(MembershipResources.Unit.APPLICATION));}
        assertEquals(0,r.usage().leases());completed(node,before);
    }
}
