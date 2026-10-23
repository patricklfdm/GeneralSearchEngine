package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual local old/new ballots and applications; only the earlier bootstrap is conditional. */
class V53CarriedPublicationTest {
    @TempDir Path temp;
    static final List<Integer> NODES=List.of(1,2,3);
    static void snapshot(V53RoundStorageTest.Fixture f,String name)throws Exception {
        for(int n:NODES) {
            Path path=f.f.root.resolve("carried-snapshots/"+name+"/node-"+n);Files.createDirectories(path.getParent());V53JournalApplicationTest.copy(f.f.node(n),path);
        }
    }
    static void finish(V53RoundStorageTest.Fixture f,V53RoundStorageTest.Publication publication)throws Exception {
        for(int n:NODES)try(var store=f.f.open(n)) {
            var first=publication.publish(store,n);assertArrayEquals(first.bytes(),publication.publish(store,n).bytes());
            assertTrue(store.currentCertificate().isEmpty());assertTrue(store.currentOwnedTail().isEmpty());
        }
        f.f.maintain(null);
    }
    @Test void actualMinorityAndMajorityAcceptedTailsCarryIntoPublicationAndSameRoundContinuation()throws Exception {
        Path root=Path.of("target/v53-carried-publication").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);var rows=new ArrayList<Map<String,Object>>();
        try {
            for(int holders:List.of(1,2,3)) {
                Path work=root.resolve("holders-"+holders);var f=new V53RoundStorageTest.Fixture(work);
                byte[] payload;try(var encoder=f.f.initial.application.app.encoder()) {
                    payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(203,"carried-original"))));
                }
                var entry=f.entry("DATA",payload);Files.write(work.resolve("entry.gsr"),entry.bytes());Files.write(work.resolve("payload.bin"),payload);
                var oldAccepts=new HashSet<Owned>();
                for(int n:NODES)if(n>3-holders)try(var store=f.f.open(n)){oldAccepts.add(store.acceptCurrent(entry,payload));}
                f.f.observations.addAll(oldAccepts);snapshot(f,"old-accepted");
                var setup=f.f.prepare(1);snapshot(f,"prepared");
                for(int n:NODES)try(var store=f.f.open(n)) {
                    var selected=store.originalSelection().orElseThrow();assertEquals(entry.digest(),selected.value().get("nextEntry"));
                    assertEquals(21L,object(selected.value().get("ballot")).get("counter"));
                    store.installCurrent(setup.sources(),List.of(),setup.images());
                }
                snapshot(f,"installed");
                for(int n:NODES)try(var store=f.f.open(n)) {
                    var before=V53ReplayFilesTest.files(f.f.node(n));var changed=new TreeMap<>(entry.value());changed.put("origin",setup.ballot());
                    var rejected=assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(decode(encode("records","ENTRY",changed),"records","ENTRY"),payload));
                    assertEquals("pending entry differs from selected choice/origin",rejected.getMessage());assertEquals(before,V53ReplayFilesTest.files(f.f.node(n)));
                    var accepted=store.acceptCurrent(entry,payload);assertEquals(accepted,store.acceptCurrent(entry,payload));
                    var vote=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(n).resolve("pending.accept")));
                    assertArrayEquals(entry.bytes(),vote.entry().bytes());assertArrayEquals(payload,vote.payload());
                    assertEquals(20L,object(vote.entry().value().get("origin")).get("counter"));assertEquals(21L,object(vote.accept().value().get("ballot")).get("counter"));
                }
                snapshot(f,"reaccepted");f.f.maintain(setup.obsolete());snapshot(f,"reclaimed");
                var publication=f.apply(entry,payload);finish(f,publication);snapshot(f,"published");
                var barrier=new TreeMap<>(f.entry("BARRIER",new byte[0]).value());barrier.put("origin",setup.ballot());
                var next=f.apply(decode(encode("records","ENTRY",barrier),"records","ENTRY"),new byte[0]);finish(f,next);snapshot(f,"continued");
                for(int n:NODES)try(var store=f.f.open(n)) {
                    var copy=store.floorCopyCurrent();assertEquals(3L,copy.capsule.context.cut.get("index"));assertEquals(43L,copy.capsule.context.catalog.get("applicationSequence"));
                    var state=f.f.initial.application.app.read(copy.fileBytes(copy.capsule.terminal().application()+".image"),"carried-read-"+n);
                    assertEquals(1,state.documents().stream().filter(d->d.equals(new Doc(203,"carried-original"))).count());
                    assertEquals(2,f.f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    assertEquals(entry.digest(),store.originalSelection().orElseThrow().value().get("nextEntry"));
                    assertArrayEquals(setup.sources().get(n-1).basis.bytes(),store.prepareCurrent(setup.ballot()).bytes());
                    var fresh=store.prepareCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(22));assertNull(fresh.value().get("accepted"));
                    assertEquals(3L,object(fresh.value().get("cut")).get("index"));
                }
                snapshot(f,"fresh");assertEquals(0,f.f.resources.usage().leases());
                rows.add(Map.of("holders",(long)holders,"entry",entry.digest(),"origin",20L,"acceptBallot",21L,"selectedCut",1L,"publishedCut",3L,"applicationSequence",43L,"status","PASS"));
                System.out.println("v53CarriedPublicationHolders="+holders+" PASS");
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("execution","private-carried-publication","cases",rows,"expectedCases",3L,
                    "historicalBootstrap","conditional-fixture","freshProcesses",false,"runtimeEnabled",false),8192));
            System.out.println("v53CarriedPublicationEvidence="+root.toAbsolutePath());
        }
        assertEquals(3,rows.size());
    }
    record Candidate(V53RoundStorageTest.Fixture fixture,Decoded entry,V53PublicationLifetimeTest.Installation setup) {}
    static Candidate prepared(Path root)throws Exception {
        var f=new V53RoundStorageTest.Fixture(root);var entry=f.entry("BARRIER",new byte[0]);
        for(int n:NODES)try(var store=f.f.open(n)){f.f.observations.add(store.acceptCurrent(entry,new byte[0]));}
        return new Candidate(f,entry,f.f.prepare(1));
    }
    static MembershipGrantJournal openClone(Path node,Candidate c,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=c.fixture();return MembershipGrantJournal.openApplying(node,f.f.initial.application.f.f.f.root(),V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.f.observations),cut);
    }
    @Test void originalRoundPinsItsGenerationThroughInstallationAndRepeatedRecoveryFailures()throws Exception {
        var c=prepared(temp.resolve("seed"));var f=c.fixture();
        for(String point:List.of("INSTALL_RESERVED","INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_BEFORE_RETURN")) {
            Path node=temp.resolve(point);V53JournalApplicationTest.copy(f.f.node(1),node);var resources=new MembershipResources(512*MembershipResources.MIB);
            assertThrows(java.io.IOException.class,()->{try(var store=openClone(node,c,resources,e->{if(e.equals(point))throw new java.io.IOException("first");})) {
                store.installCurrent(c.setup().sources(),List.of(),c.setup().images());
            }});assertEquals(0,resources.usage().leases());
            assertThrows(java.io.IOException.class,()->openClone(node,c,resources,e->{if(e.equals("ACCEPT_ACTIVE_FORCED"))throw new java.io.IOException("again");}));
            assertEquals(0,resources.usage().leases());
            try(var store=openClone(node,c,resources,e->{})) {store.installCurrent(c.setup().sources(),List.of(),c.setup().images());}
            try(var store=openClone(node,c,resources,e->{})) {
                var before=V53ReplayFilesTest.files(node);assertEquals("original pending vote pins inactive generation until reacceptance",
                        assertThrows(IllegalArgumentException.class,store::retireInactive).getMessage());assertEquals(before,V53ReplayFilesTest.files(node));
                store.acceptCurrent(c.entry(),new byte[0]);assertEquals(7,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
            try(var store=openClone(node,c,resources,e->{})){assertEquals(21L,object(MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept"))).accept().value().get("ballot")).get("counter"));}
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void carriedVoteRequiresTheExactRetainedOriginalRound()throws Exception {
        var c=prepared(temp.resolve("seed"));var f=c.fixture();
        try(var store=f.f.open(1)){store.installCurrent(c.setup().sources(),List.of(),c.setup().images());}
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(1).resolve("pending.accept")));
        String old=(String)vote.selector().value().get("generation");
        for(String damage:List.of("missing","changed")) {
            Path node=temp.resolve(damage);V53JournalApplicationTest.copy(f.f.node(1),node);
            Path coverage=node.resolve("generations").resolve(old).resolve(MembershipSelectionCoverage.FILE);
            if(damage.equals("missing"))Files.delete(coverage);else Files.writeString(coverage,"{}");
            var before=V53ReplayFilesTest.files(node);var resources=new MembershipResources(512*MembershipResources.MIB);
            for(int repeat=0;repeat<2;repeat++) {
                assertThrows(IllegalArgumentException.class,()->{try(var ignored=openClone(node,c,resources,e->{})) {fail("damaged original round accepted");}});
                assertEquals(0,resources.usage().leases());assertEquals(before,V53ReplayFilesTest.files(node));
            }
        }
    }
    @Test void emptyCompletionBuffersYieldToBoundedMaintenanceAndRecoverAfterInterruption()throws Exception {
        var c=prepared(temp.resolve("seed"));var f=c.fixture();
        for(int n:NODES)try(var store=f.f.open(n)){store.installCurrent(c.setup().sources(),List.of(),c.setup().images());store.acceptCurrent(c.entry(),new byte[0]);}
        var copies=new ArrayList<MembershipFloor.Copy>();for(int n:List.of(1,2))try(var store=f.f.open(n)){copies.add(store.floorCopyCurrent());}
        for(String point:List.of("FLOOR_PROPOSAL_FORCED","FLOOR_AUTHORITY_FORCED","RETIREMENT_IMAGE_FORCED","RETIREMENT_FILE_DELETED","FLOOR_RELEASE_COPY_DELETED")) {
            Path node=temp.resolve(point);V53JournalApplicationTest.copy(f.f.node(1),node);var resources=new MembershipResources(512*MembershipResources.MIB);
            assertThrows(java.io.IOException.class,()->{try(var store=openClone(node,c,resources,e->{if(e.equals(point))throw new java.io.IOException("cut");})) {
                store.establishFloor(copies);store.retireInactive();store.retireSource(c.setup().obsolete().get(1));store.releaseFloor();
            }});assertEquals(0,resources.usage().leases());
            try(var store=openClone(node,c,resources,e->{})) {
                if(store.governingFloor().isEmpty())store.establishFloor(copies);
                if(point.equals("FLOOR_PROPOSAL_FORCED") || point.equals("FLOOR_AUTHORITY_FORCED")) {
                    var before=V53ReplayFilesTest.files(node);var usage=resources.usage();
                    assertEquals("resource ownership/count",assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(c.entry(),new byte[0])).getMessage());
                    assertEquals(usage,resources.usage(),"failed admission must restore maintenance capacity");assertEquals(before,V53ReplayFilesTest.files(node));
                }
                store.retireInactive();
                if(Files.exists(node.resolve("sources").resolve(c.setup().obsolete().get(1))))store.retireSource(c.setup().obsolete().get(1));
                store.releaseFloor();assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                store.acceptCurrent(c.entry(),new byte[0]);
            }
            assertEquals(0,resources.usage().leases());
            try(var store=openClone(node,c,resources,e->{})){assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));assertTrue(store.governingFloor().isEmpty());}
            assertEquals(0,resources.usage().leases());
        }
    }
}
