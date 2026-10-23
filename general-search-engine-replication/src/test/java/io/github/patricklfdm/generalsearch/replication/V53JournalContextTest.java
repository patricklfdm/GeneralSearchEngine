package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual local source/context owner; no source/generation deletion or transferred progress yet. */
class V53JournalContextTest {
    @TempDir static Path fixtureRoot;
    @TempDir Path temporary;
    static V53StagedApplicationTest.Seed seed;
    static MembershipRoot root;
    static MembershipIdentity identity=V53DeclarationsTest.node(1);
    static MembershipCurrentGeneration.Verifier verifier;
    static byte[] expected;
    static final List<String> CUTS=List.of("CONTEXT_OWNER_VALIDATED","CONTEXT_SOURCE_MEMBER_FORCED",
            "CONTEXT_SOURCE_DIRECTORY_FORCED","CONTEXT_SOURCE_PARENT_FORCED","CONTEXT_CANDIDATE_CREATED",
            "CONTEXT_PREFIX_WRITTEN","CONTEXT_CANDIDATE_WRITTEN","CONTEXT_CANDIDATE_FORCED",
            "CONTEXT_CANDIDATE_PARENT_FORCED","CONTEXT_RENAMED","CONTEXT_PARENT_FORCED","CONTEXT_OWNER_BEFORE_RETURN");

    @BeforeAll static void actualOwnerAndOriginalSource()throws Exception {
        seed=V53StagedApplicationTest.seed(fixtureRoot.resolve("seed"),Set.of(1));var f=seed.fixture().f;
        root=f.initial.application.f.f.f.root();verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,f.observations);
        var images=V53StagedApplicationTest.images(seed);var ballot=new TreeMap<>(V53StagedApplicationTest.nextBallot(seed));
        ballot.put("proposer","node-3");ballot.put("incarnation",V53DeclarationsTest.node(3).storageId().toString());
        var sources=new ArrayList<MembershipSelection.Source>();Decoded promise=null;
        for(int n:V53StagedApplicationTest.NODES)try(var store=f.open(n)) {
            store.prepareCurrent(ballot);sources.add(store.originalSource());if(n==1)promise=store.promised().orElseThrow();
        }
        for(int n:V53StagedApplicationTest.NODES)try(var store=f.open(n)) {
            store.selectCurrent(sources,List.of());store.installCurrent(sources,List.of(),images);
        }
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(f.node(1).resolve(MembershipPendingAccept.FILE)));
        expected=MembershipPendingContext.encode(MembershipPendingContext.create(root,identity,vote.selector(),originalFiles(f.node(1),vote),vote,
                promise,sources.getFirst(),images,verifier));assertEquals(0,f.resources.usage().leases());
    }
    static Map<String,byte[]> originalFiles(Path node,MembershipPendingAccept.Vote vote)throws Exception {
        var result=new TreeMap<String,byte[]>();Path generation=node.resolve("generations").resolve((String)vote.selector().value().get("generation"));
        try(var files=Files.list(generation)){for(Path path:files.toList())result.put(path.getFileName().toString(),Files.readAllBytes(path));}return result;
    }
    Path copy(String name)throws Exception {Path node=temporary.resolve(name);V53JournalApplicationTest.copy(seed.fixture().f.node(1),node);return node;}
    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    static MembershipGrantJournal open(Path node,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return open(node,resources,MembershipGrantJournal.MAXIMUM,cut);
    }
    static MembershipGrantJournal open(Path node,MembershipResources resources,int maximum,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openContextual(node,root,identity,resources,verifier,maximum,e->{
            assertTrue(resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=7);
            assertTrue(resources.usage().metadata()<=MembershipResources.METADATA_LIMIT);cut.at(e);
        });
    }
    static Map<String,String> protectedFiles(Path node)throws Exception {
        var result=new TreeMap<>(V53ReplayFilesTest.files(node));result.remove(MembershipPendingContextFiles.FILE);result.remove(MembershipPendingContextFiles.NEXT);return result;
    }
    static void noAck(List<String> events) {
        assertTrue(events.stream().noneMatch(e->e.startsWith("APPLY_ACK_") || Set.of("ACCEPT_BEFORE_RETURN","PROOF_BEFORE_RETURN",
                "CERTIFICATE_BEFORE_RETURN","GRANT_BEFORE_RETURN","INSTALL_BEFORE_RETURN","PUBLICATION_BEFORE_RETURN").contains(e)),events.toString());
    }
    static void exactContext(Path node,MembershipPendingContext.Reconstructed value)throws Exception {
        assertArrayEquals(expected,Files.readAllBytes(node.resolve(MembershipPendingContextFiles.FILE)));
        assertArrayEquals(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)),value.vote().bytes());
        V53PendingContextTest.sameFiles(originalFiles(node,value.vote()),value.originalFiles());
        assertFalse(Files.exists(node.resolve(MembershipPendingContextFiles.NEXT)));
    }

    @Test void actualOwnerSealsBackingBeforeContextAndReopensWithoutIssuingOldAck()throws Exception {
        Path node=copy("owner");var before=protectedFiles(node);var resources=resources();var events=new ArrayList<String>();
        try(var store=open(node,resources,events::add)) {
            events.clear();exactContext(node,store.retainPendingContext());
            assertTrue(events.indexOf("CONTEXT_SOURCE_PARENT_FORCED")<events.indexOf("CONTEXT_CANDIDATE_CREATED"));
            assertTrue(events.indexOf("CONTEXT_PARENT_FORCED")<events.indexOf("CONTEXT_OWNER_BEFORE_RETURN"));
            exactContext(node,store.retainPendingContext());noAck(events);
            var occupied=assertThrows(ReplicationException.class,()->open(node,resources(),e->{}));
            assertEquals(ReplicationException.Reason.STORAGE_FAILURE,occupied.reason());
            assertEquals("membership authority already owned in this process",occupied.getMessage());
            assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.JOURNAL));
        }
        assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());events.clear();
        try(var store=open(node,resources,events::add)){exactContext(node,store.retainPendingContext());noAck(events);}
        assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
    }

    @Test void everyContextAndBackingForceCutCanRecoverAfterASecondInterruption()throws Exception {
        Path evidence=Path.of("target/v53-journal-context").resolve("run-"+UUID.randomUUID());Files.createDirectories(evidence);
        var rows=new ArrayList<Map<String,Object>>();
        for(String cut:CUTS) {
            Path node=copy(cut);Path caseRoot=Files.createDirectory(evidence.resolve(cut));V53JournalApplicationTest.copy(node,caseRoot.resolve("initial"));
            var before=protectedFiles(node);var resources=resources();var events=new ArrayList<String>();var firstEvents=new ArrayList<String>();var secondEvents=new ArrayList<String>();
            try(var store=open(node,resources,e->{firstEvents.add(e);if(e.equals(cut))throw new IOException("first interruption: "+cut);})) {
                assertThrows(IOException.class,store::retainPendingContext);
            }
            V53JournalApplicationTest.copy(node,caseRoot.resolve("crash"));
            assertEquals(0,resources.usage().leases());var interrupted=new AtomicBoolean();
            try {
                try(var store=open(node,resources,e->{secondEvents.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED")){interrupted.set(true);throw new IOException("second interruption");}})) {
                    store.retainPendingContext();fail("second interruption missing");
                }
                fail("second interruption missing");
            }catch(IOException failure){assertEquals("second interruption",failure.getMessage());}
            V53JournalApplicationTest.copy(node,caseRoot.resolve("recovery-crash"));
            assertTrue(interrupted.get());assertEquals(0,resources.usage().leases());
            try(var store=open(node,resources,events::add)){exactContext(node,store.retainPendingContext());}
            noAck(events);assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
            V53JournalApplicationTest.copy(node,caseRoot.resolve("final"));
            Files.write(caseRoot.resolve("events.json"),canonical(Map.of("first",firstEvents,"recovery",secondEvents,"resume",events),16384));
            rows.add(Map.of("cut",cut,"status","PASS","contextSha256",hash(expected),"protectedFiles",before.size()));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-journal-context-local-v1","status","PASS",
                "cases",rows,"interruptions","injected-IOException","freshProcesses",false,"sourceOwnership","actual-local-force",
                "retirementAuthorized",false,"fullOwnerProgress",false,"runtimeEnabled",false),16384));
        System.out.println("v53JournalContextEvidence="+evidence.toAbsolutePath());
    }

    @Test void higherVolatileObservationAllowsRetentionButCannotReturnOldAuthorityOrMutatePinnedState()throws Exception {
        Path node=copy("higher");var before=protectedFiles(node);var resources=resources();var events=new ArrayList<String>();
        try(var store=open(node,resources,events::add)) {
            var high=new TreeMap<>(object(store.promised().orElseThrow().value().get("ballot")));high.put("counter",22L);store.observeCurrent(high);events.clear();
            exactContext(node,store.retainPendingContext());
            var calls=List.<org.junit.jupiter.api.function.Executable>of(()->store.prepareCurrent(high),()->store.acceptCurrent(seed.entry(),seed.payload()),
                    store::rotateJournal,store::releaseFloor,store::retireInactive,store::reserveCounter);
            for(var call:calls)assertThrows(IllegalArgumentException.class,call);noAck(events);
        }
        assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
    }

    @Test void contextCannotBeOpenedByEarlierOwnersAndDoesNotAuthorizeDeletingOriginalGeneration()throws Exception {
        Path node=copy("exclusive");var resources=resources();
        try(var store=open(node,resources,e->{})){store.retainPendingContext();}
        var before=V53ReplayFilesTest.files(node);
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openApplying(node,root,identity,resources,verifier,e->{}));
        assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
        Path generation=node.resolve("generations").resolve((String)vote.selector().value().get("generation"));Files.move(generation,temporary.resolve("retained-original"));
        var absent=V53ReplayFilesTest.files(node);assertThrows(IllegalArgumentException.class,()->open(node,resources,e->{}));
        assertEquals(absent,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
    }

    @Test void combinedJournalAdmissionPrecedesAnyContextWriteAndCorruptActiveCannotBeRepaired()throws Exception {
        Path node=copy("capacity");var resources=resources();var before=V53ReplayFilesTest.files(node);
        var vote=new MembershipPendingAccept(node);int maximum=Math.toIntExact(Files.size(node.resolve(MembershipGrantJournal.FILE))+vote.bytes()+vote.clearAllowance()
                +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA+expected.length-1);
        assertTrue(maximum>=MembershipGrantJournal.RESERVATION);
        try(var store=open(node,resources,maximum,e->{})) {
            assertEquals("combined context/grant journal completion capacity",assertThrows(IllegalArgumentException.class,store::retainPendingContext).getMessage());
        }
        assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
        try(var store=open(node,resources,e->{})){store.retainPendingContext();}
        Path active=node.resolve(MembershipPendingContextFiles.FILE);byte[] damaged=Files.readAllBytes(active);damaged[damaged.length-1]^=1;Files.write(active,damaged);
        before=V53ReplayFilesTest.files(node);assertThrows(IllegalArgumentException.class,()->open(node,resources,e->{}));
        assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
    }

    @Test void sourceInodeSubstitutionDuringContextWriteFailsWithoutAcknowledgement()throws Exception {
        Path node=copy("inode");var resources=resources();var events=new ArrayList<String>();
        try(var store=open(node,resources,e->{
            events.add(e);if(e.equals("CONTEXT_CANDIDATE_WRITTEN")) {
                var context=MembershipPendingContext.decode(Files.readAllBytes(node.resolve(MembershipPendingContextFiles.NEXT)));
                assertArrayEquals(expected,MembershipPendingContext.encode(context));
                var segments=V53PendingContextTest.parts(expected).segments();var basis=decode(segments.get(3),"records","BASIS");
                Path packet=node.resolve("sources").resolve((String)basis.value().get("basisId")).resolve("source.gscp");
                Path changed=temporary.resolve("same-bytes-new-inode");Files.write(changed,Files.readAllBytes(packet));Files.move(changed,packet,StandardCopyOption.REPLACE_EXISTING);
            }
        })) {
            events.clear();assertThrows(IllegalArgumentException.class,store::retainPendingContext);noAck(events);
            assertFalse(Files.exists(node.resolve(MembershipPendingContextFiles.FILE)));
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void redundantContextWithdrawalPreservesOriginalsAndRestoresExistingReacceptancePath()throws Exception {
        for(String cut:List.of("none","CONTEXT_REDUNDANT_DELETED","CONTEXT_REDUNDANT_PARENT_FORCED")) {
            Path node=copy("discard-"+cut);var resources=resources();var before=protectedFiles(node);var events=new ArrayList<String>();
            try(var store=open(node,resources,e->{events.add(e);if(e.equals(cut))throw new IOException("withdraw interruption");})) {
                store.retainPendingContext();
                if(cut.equals("none")){store.discardRedundantPendingContext();store.discardRedundantPendingContext();}
                else assertThrows(IOException.class,store::discardRedundantPendingContext);
                noAck(events);
            }
            assertEquals(before,protectedFiles(node));assertEquals(0,resources.usage().leases());
            assertFalse(Files.exists(node.resolve(MembershipPendingContextFiles.FILE)));
            try(var store=open(node,resources,e->{})) {
                store.discardRedundantPendingContext();store.acceptCurrent(seed.entry(),seed.payload());
                V53StagedApplicationTest.assertNewAcceptance(node,seed);
            }
            assertEquals(0,resources.usage().leases());
        }
    }
}
