package io.github.patricklfdm.generalsearch.replication;

import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Higher PROMISE is an explicit fixture boundary, not a newly enabled campaign API. */
class V53ContextDurableFenceTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static Path base;
    @BeforeAll static void original()throws Exception {
        V53ContextSourceReleaseTest.fixtures=Files.createDirectory(fixtures.resolve("seed"));V53ContextSourceReleaseTest.originalRetirement();
        var producer=new V53ContextSourceReleaseTest();producer.temp=Files.createDirectory(fixtures.resolve("source"));base=producer.releaseScenario();
    }
    static Decoded appendFence(Path node)throws Exception {
        var value=new TreeMap<>(decode(V53PendingContextTest.parts(Files.readAllBytes(node.resolve("pending.context"))).segments().get(2),"records","PROMISE").value());
        var ballot=new TreeMap<>(object(value.get("ballot")));ballot.put("counter",22L);
        ballot.put("proposer","node-2");ballot.put("incarnation",V53DeclarationsTest.node(2).storageId().toString());
        value.put("ballot",ballot);value.put("basisId",UUID.randomUUID().toString());
        var promise=decode(encode("records","PROMISE",value),"records","PROMISE");
        try(var channel=FileChannel.open(node.resolve("grants.gsr"),StandardOpenOption.WRITE,StandardOpenOption.APPEND)) {AdmissionPaths.write(channel,promise.bytes());channel.force(true);}
        AdmissionPaths.forceDirectory(node);return promise;
    }
    static MembershipGrantJournal open(Path node,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {return V53ContextSourceReleaseTest.open(node,r,cut);}
    Path copy(String source,String name)throws Exception {Path node=temp.resolve(name);V53JournalApplicationTest.copy(base.resolve(source),node);return node;}
    static void check(MembershipGrantJournal owner,Decoded fence,byte[] vote)throws Exception {
        assertArrayEquals(fence.bytes(),owner.promised().orElseThrow().bytes());assertTrue(owner.originalBasis().isEmpty());assertTrue(owner.originalSelection().isEmpty());
        assertArrayEquals(vote,owner.retainPendingContext().vote().bytes());assertEquals(MembershipPendingAccept.decode(vote).certificate().digest(),owner.currentCertificate().orElseThrow().digest());
    }
    @Test void higherDurablePromisePreservesExactBackingAcrossAllThreeRetentionStages()throws Exception {
        Path evidence=Path.of("target/v53-context-durable-fence/run-"+UUID.randomUUID());Files.createDirectories(evidence);V53JournalApplicationTest.copy(base,evidence.resolve("reference"));
        var rows=new ArrayList<Map<String,Object>>();
        for(String stage:List.of("initial","retired","reopened")) {
            String source=stage.equals("reopened")?stage:"original-retirement/"+stage;
            Path node=copy(source,stage),raw=Files.createDirectory(evidence.resolve(stage));var higher=appendFence(node);
            byte[] vote=Files.readAllBytes(node.resolve("pending.accept"));var before=V53BootstrapProgressResumeTest.safeFiles(node);V53JournalApplicationTest.copy(node,raw.resolve("initial"));
            var r=V53ContextRetirementTest.resources();var events=new ArrayList<String>();
            try(var owner=open(node,r,events::add)) {
                check(owner,higher,vote);
                assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(V53ContextRetirementTest.seed.entry(),V53ContextRetirementTest.seed.payload()));
                assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(object(higher.value().get("ballot"))));
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
            try(var owner=open(node,r,events::add)){check(owner,higher,vote);}
            assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));V53JournalContextTest.noAck(events);
            V53JournalApplicationTest.copy(node,raw.resolve("final"));Files.write(raw.resolve("fence.gsr"),higher.bytes());Files.write(raw.resolve("events.json"),canonical(events,65536));
            rows.add(Map.of("case",stage,"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-durable-fence-v1","status","PASS","cases",rows,
                "promiseInput","forced-fixture-frame","runtimeEnabled",false,"newCampaignEnabled",false),16384));
        System.out.println("v53ContextDurableFenceEvidence="+evidence.toAbsolutePath());
    }
    @Test void repeatedResealInterruptionAndCleanupPreserveHigherPromiseWithoutOldAck()throws Exception {
        Path node=copy("original-retirement/retired","cleanup");var higher=appendFence(node);byte[] vote=Files.readAllBytes(node.resolve("pending.accept"));var r=V53ContextRetirementTest.resources();
        for(String point:List.of("CONTEXT_SOURCE_PARENT_FORCED","CONTEXT_ACTIVE_PARENT_FORCED")) {
            var before=V53BootstrapProgressResumeTest.safeFiles(node);
            assertThrows(java.io.IOException.class,()->open(node,r,e->{if(e.equals(point))throw new java.io.IOException("reseal cut");}));
            assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));assertEquals(0,r.usage().leases());
        }
        var events=new ArrayList<String>();
        try(var owner=open(node,r,events::add)) {
            check(owner,higher,vote);owner.retireSource(V53ContextSourceReleaseTest.predecessor);check(owner,higher,vote);
            assertFalse(Files.exists(node.resolve("sources").resolve(V53ContextSourceReleaseTest.predecessor)));
            assertTrue(Files.exists(node.resolve("sources").resolve(V53ContextSourceReleaseTest.backing)));
            assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(V53ContextRetirementTest.seed.entry(),V53ContextRetirementTest.seed.payload()));
            V53JournalContextTest.noAck(events);
        }
        assertEquals(0,r.usage().leases());try(var owner=open(node,r,events::add)){check(owner,higher,vote);}assertEquals(0,r.usage().leases());V53JournalContextTest.noAck(events);
    }
    @Test void changedOrMissingBackingCannotBeSubstitutedByLatestPromise()throws Exception {
        for(String kind:List.of("basis","source","context")) {
            Path node=copy("reopened",kind);appendFence(node);
            if(kind.equals("source"))Files.delete(node.resolve("sources").resolve(V53ContextSourceReleaseTest.backing).resolve("source.gscp"));
            else if(kind.equals("context")) {
                Path p=node.resolve("pending.context");byte[] raw=Files.readAllBytes(p);raw[raw.length-1]^=1;Files.write(p,raw);
            }else {
                var parts=V53PendingContextTest.parts(Files.readAllBytes(node.resolve("pending.context")));byte[] journal=Files.readAllBytes(node.resolve("grants.gsr"));
                byte[] basis=parts.segments().get(3);var out=new java.io.ByteArrayOutputStream();int at=0;
                while(at<journal.length){int length=HEADER+java.nio.ByteBuffer.wrap(journal,at+12,4).getInt();byte[] frame=Arrays.copyOfRange(journal,at,at+length);if(!Arrays.equals(frame,basis))out.writeBytes(frame);at+=length;}Files.write(node.resolve("grants.gsr"),out.toByteArray());
            }
            var before=V53BootstrapProgressResumeTest.safeFiles(node);var r=V53ContextRetirementTest.resources();
            assertThrows(Exception.class,()->open(node,r,e->{}));assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
        }
    }
    @Test void laterPromiseMustStillNameAnEligibleDurableProposer()throws Exception {
        for(String change:List.of("proposer","incarnation","view")) {
            Path node=copy("reopened","foreign-"+change);byte[] prior=Files.readAllBytes(node.resolve("grants.gsr"));var higher=appendFence(node);
            var value=new TreeMap<>(higher.value());var ballot=new TreeMap<>(object(value.get("ballot")));
            if(change.equals("view"))value.put("view","00".repeat(32));
            else {ballot.put(change,change.equals("proposer")?"node-7":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");value.put("ballot",ballot);}
            var out=new java.io.ByteArrayOutputStream();out.writeBytes(prior);out.writeBytes(encode("records","PROMISE",value));Files.write(node.resolve("grants.gsr"),out.toByteArray());
            var before=V53BootstrapProgressResumeTest.safeFiles(node);var r=V53ContextRetirementTest.resources();
            var failure=assertThrows(IllegalArgumentException.class,()->{try(var ignored=open(node,r,e->{})) {}});
            assertEquals(change.equals("view")?"retained context backing/installed/latest order changed":"ballot durable identity",failure.getMessage());
            assertEquals(0,r.usage().leases());assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
        }
    }
}
