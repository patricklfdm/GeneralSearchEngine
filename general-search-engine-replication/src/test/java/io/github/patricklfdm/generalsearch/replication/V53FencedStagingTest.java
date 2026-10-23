package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Recovery may remove derived staging under a later observation, never the original authority. */
class V53FencedStagingTest {
    @TempDir static Path fixtures;
    @TempDir Path temporary;
    static V53StagedApplicationTest.Seed seed;
    static final List<String> CUTS=List.of("before", "STAGED_RETIREMENT_AUTHORITY_VALIDATED",
            "SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN", "SUPERSEDED_END_AUTHORITY_FORCED",
            "SUPERSEDED_END_FILE_DELETED", "SUPERSEDED_END_RETIREMENT_DELETED", "STAGED_RETIREMENT_BEFORE_RETURN");

    @BeforeAll static void installedCarriedCertificate()throws Exception {
        seed=V53StagedApplicationTest.seed(fixtures.resolve("original"),Set.of(1));
        var f=seed.fixture().f;
        try(var store=f.open(1)){V53StagedApplicationTest.apply(store,seed);}
        var others=V53StagedApplicationTest.otherSources(seed);var images=V53StagedApplicationTest.images(seed);
        try(var store=f.open(1)){V53StagedApplicationTest.install(store,seed,others,images);}
        assertEquals(0,f.resources.usage().leases());
    }
    Path copy(String name)throws Exception {
        Path node=temporary.resolve(name);V53JournalApplicationTest.copy(seed.fixture().f.node(1),node);return node;
    }
    static Map<String,String> protectedFiles(Path node)throws IOException {
        var result=new TreeMap<>(V53ReplayFilesTest.files(node));
        result.keySet().removeIf(p->p.equals(MembershipAppliedEndFiles.DIRECTORY) || p.startsWith(MembershipAppliedEndFiles.DIRECTORY+"/")
                || p.equals(MembershipReplayFiles.DIRECTORY) || p.startsWith(MembershipReplayFiles.DIRECTORY+"/"));return result;
    }
    static Map<String,Object> ballot(long value) {
        var result=new TreeMap<>(V53StagedApplicationTest.nextBallot(seed));result.put("counter",value);return result;
    }
    static MembershipGrantJournal open(Path node,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return V53StagedApplicationTest.open(node,1,seed,resources,cut);
    }
    static void staleWritesRemainFenced(MembershipGrantJournal store,Path node)throws Exception {
        var before=V53ReplayFilesTest.files(node);
        assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,
                ()->store.acceptCurrent(seed.entry(),seed.payload())).getMessage());
        assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,
                ()->store.prepareCurrent(V53StagedApplicationTest.nextBallot(seed))).getMessage());
        assertThrows(IllegalArgumentException.class,()->V53StagedApplicationTest.apply(store,seed));
        assertEquals(before,V53ReplayFilesTest.files(node));
    }

    @Test void observationBeforeAndDuringEveryRetirementBoundaryDoesNotCancelRecoveryOrReviveVoting()throws Exception {
        Path evidence=Path.of("target/v53-fenced-staging").resolve("run-"+UUID.randomUUID());Files.createDirectories(evidence);
        var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String point:CUTS) {
                Path node=copy(point),path=Files.createDirectory(evidence.resolve(point));
                V53JournalApplicationTest.copy(node,path.resolve("initial"));
                var before=protectedFiles(node);var resources=V53JournalContextTest.resources();var events=new ArrayList<String>();
                MembershipGrantJournal[] active={null};boolean[] hit={false};
                try(var store=open(node,resources,event->{
                    events.add(event);if(event.equals(point)) {
                        hit[0]=true;active[0].observeCurrent(ballot(22));active[0].observeCurrent(ballot(24));active[0].observeCurrent(ballot(23));
                        events.add("TEST_OBSERVED_24");
                    }
                })) {
                    active[0]=store;events.clear();
                    if(point.equals("before")){hit[0]=true;store.observeCurrent(ballot(24));events.add("TEST_OBSERVED_24");}
                    V53StagedApplicationTest.retire(store,seed);assertTrue(hit[0],point);V53StagedApplicationTest.noStaging(node);
                    staleWritesRemainFenced(store,node);V53StagedApplicationTest.retire(store,seed);
                    V53JournalContextTest.noAck(events);
                }
                assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
                V53JournalApplicationTest.copy(node,path.resolve("final"));
                Files.write(path.resolve("events.json"),canonical(events,65536));
                rows.add(Map.of("cut",point,"status","PASS","observed",24L,"oldWritesRejected",true));
            }
        }finally {
            Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-fenced-staging-v1","status",rows.size()==CUTS.size()?"PASS":"FAIL",
                    "cases",rows,"freshProcesses",false,"oldAckReturned",false,"transferredLifetime",false),16384));
            System.out.println("v53FencedStagingEvidence="+evidence.toAbsolutePath());
        }
    }

    @Test void twiceInterruptedCleanupCanFinishAfterNewObservationsInEachOwner()throws Exception {
        for(String point:List.of("SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN","SUPERSEDED_END_AUTHORITY_FORCED","SUPERSEDED_END_FILE_DELETED")) {
            Path node=copy("interrupt-"+point);var before=protectedFiles(node);var resources=V53JournalContextTest.resources();
            for(int attempt=0;attempt<2;attempt++) {
                String stop=attempt==0?point:"SUPERSEDED_END_AUTHORITY_FORCED";
                try(var store=open(node,resources,event->{if(event.equals(stop))throw new IOException("recovery cut");})) {
                    store.observeCurrent(ballot(22+attempt));
                    assertEquals("recovery cut",assertThrows(IOException.class,()->V53StagedApplicationTest.retire(store,seed)).getMessage());
                }
                assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
            }
            try(var store=open(node,resources,event->{})) {
                store.observeCurrent(ballot(24));V53StagedApplicationTest.retire(store,seed);V53StagedApplicationTest.noStaging(node);
                staleWritesRemainFenced(store,node);
            }
            assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
        }
    }

    @Test void recoveryRejectsChangedOriginalInodeEvenWhenBytesAndObservedBallotAreUnchanged()throws Exception {
        Path node=copy("inode");var resources=V53JournalContextTest.resources();var events=new ArrayList<String>();
        try(var store=open(node,resources,event->{
            events.add(event);if(event.equals("SUPERSEDED_END_AUTHORITY_FORCED")) {
                Path vote=node.resolve(MembershipPendingAccept.FILE),replacement=temporary.resolve("same-bytes");
                Files.write(replacement,Files.readAllBytes(vote));Files.move(replacement,vote,StandardCopyOption.REPLACE_EXISTING);
            }
        })) {
            store.observeCurrent(ballot(24));events.clear();assertThrows(IllegalArgumentException.class,()->V53StagedApplicationTest.retire(store,seed));
            assertTrue(events.contains("SUPERSEDED_END_AUTHORITY_FORCED"));
            assertTrue(Files.exists(node.resolve("applied-end/application.image")),"original change must stop before staged member deletion");
            V53JournalContextTest.noAck(events);
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void cleanupThenContextRetentionAndRedundantWithdrawalPreserveTheObservedFence()throws Exception {
        Path node=copy("context");var resources=V53JournalContextTest.resources();var f=seed.fixture().f;var events=new ArrayList<String>();
        try(var store=MembershipGrantJournal.openContextual(node,f.initial.application.f.f.f.root(),V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,events::add)) {
            store.observeCurrent(ballot(24));events.clear();
            assertThrows(IllegalArgumentException.class,store::retainPendingContext,"staged sources remain pinned until cleanup");
            V53StagedApplicationTest.retire(store,seed);var original=store.retainPendingContext();
            assertArrayEquals(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)),original.vote().bytes());
            store.discardRedundantPendingContext();staleWritesRemainFenced(store,node);V53JournalContextTest.noAck(events);
        }
        assertEquals(0,resources.usage().leases());
    }
}
