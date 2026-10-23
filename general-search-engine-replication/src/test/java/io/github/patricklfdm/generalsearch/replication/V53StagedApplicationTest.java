package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Real phased owners and typed replay. Historical bootstrap alone remains conditional. */
class V53StagedApplicationTest {
    @TempDir Path temp;
    static final List<Integer> NODES=List.of(1,2,3);
    record Phased(Decoded certificate,Set<Owned> accepts,Set<Owned> proofs) {
        Set<Owned> owned(){var result=new HashSet<>(accepts);result.addAll(proofs);return result;}
    }
    record Seed(V53RoundStorageTest.Fixture fixture,Decoded entry,byte[] payload,Phased phased) {}

    static Seed seed(Path root)throws Exception {
        return seed(root,Set.copyOf(NODES));
    }
    static Seed seed(Path root,Set<Integer> certificateNodes)throws Exception {
        var f=new V53RoundStorageTest.Fixture(root);byte[] payload;
        try(var encoder=f.f.initial.application.app.encoder()) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(303,"staged-original"))));
        }
        var entry=f.entry("DATA",payload);
        return new Seed(f,entry,payload,certify(f,entry,payload,certificateNodes));
    }
    static Phased certify(V53RoundStorageTest.Fixture f,Decoded entry,byte[] payload,Set<Integer> certificateNodes)throws Exception {
        var accepts=new HashSet<Owned>();Decoded acceptance=null;
        for(int n:NODES)try(var store=f.f.open(n)) {
            accepts.add(store.acceptCurrent(entry,payload));
            var actual=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(n).resolve(MembershipPendingAccept.FILE))).accept();
            if(acceptance!=null)assertArrayEquals(acceptance.bytes(),actual.bytes());acceptance=actual;
        }
        String root=f.f.initial.application.f.f.f.root().manifestDigest();
        var fields=new TreeMap<>(Objects.requireNonNull(acceptance).value());
        fields.put("accepts",V53PublicationLifetimeTest.witnesses(root,"ACCEPT",acceptance,accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<Owned>();
        for(int n:NODES)try(var store=f.f.open(n)){proofs.add(store.proveCurrent(proof,accepts));}
        fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(root,"PROOF",proof,proofs));
        var result=new Phased(decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE"),Set.copyOf(accepts),Set.copyOf(proofs));
        f.f.observations.addAll(result.owned());
        for(int n:NODES)if(certificateNodes.contains(n))try(var store=f.f.open(n)){store.certifyCurrent(result.certificate(),result.owned());}
        return result;
    }
    static MembershipGrantJournal.Applied apply(MembershipGrantJournal store,Seed seed)throws IOException {
        var app=seed.fixture().f.initial.application.app;
        return store.applyCurrent(app.configuration(),app.storage(),seed.phased().owned());
    }
    static void retire(MembershipGrantJournal store,Seed seed)throws IOException {
        var app=seed.fixture().f.initial.application.app;
        store.retireSupersededApplication(app.configuration(),app.storage(),seed.phased().owned());
    }
    static MembershipGrantJournal open(Path node,int n,Seed seed,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=seed.fixture();assertEquals(0,resources.usage().leases());
        return MembershipGrantJournal.openApplying(node,f.f.initial.application.f.f.f.root(),V53DeclarationsTest.node(n),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.f.observations),e->{
                    var used=resources.usage();assertTrue(used.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=7);
                    assertTrue(used.metadata()<=384*MembershipResources.MIB);assertTrue(used.staging()<=512*MembershipResources.MIB);cut.at(e);
                });
    }
    static Map<String,Object> nextBallot(Seed seed){return seed.fixture().f.initial.application.f.f.f.fixture.source.ballot(21);}
    static Map<String,byte[]> images(Seed seed)throws Exception {
        var result=new TreeMap<String,byte[]>();try(var store=seed.fixture().f.open(1)) {
            var copy=store.floorCopyCurrent();for(String h:copy.capsule.packet.images().keySet())result.put(h,copy.fileBytes(h+".image"));
        }return result;
    }
    static List<MembershipSelection.Source> otherSources(Seed seed)throws Exception {
        var result=new ArrayList<MembershipSelection.Source>();
        for(int n:List.of(2,3))try(var store=seed.fixture().f.open(n)){store.prepareCurrent(nextBallot(seed));result.add(store.originalSource());}
        return result;
    }
    static void install(MembershipGrantJournal store,Seed seed,List<MembershipSelection.Source> others,Map<String,byte[]> images)throws IOException {
        store.prepareCurrent(nextBallot(seed));var sources=new ArrayList<MembershipSelection.Source>();sources.add(store.originalSource());sources.addAll(others);
        var selected=store.selectCurrent(sources,List.of());assertEquals(seed.entry().digest(),selected.value().get("nextEntry"));
        assertEquals(1L,object(selected.value().get("cut")).get("index"));store.installCurrent(sources,List.of(),images);
    }
    static void noStaging(Path node) {
        assertFalse(Files.exists(node.resolve(MembershipReplayFiles.DIRECTORY)));
        assertFalse(Files.exists(node.resolve(MembershipAppliedEndFiles.DIRECTORY)));
    }
    static void assertNewAcceptance(Path node,Seed seed)throws IOException {
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
        assertArrayEquals(seed.entry().bytes(),vote.entry().bytes());assertArrayEquals(seed.payload(),vote.payload());
        assertEquals(20L,object(vote.entry().value().get("origin")).get("counter"));
        assertEquals(21L,object(vote.accept().value().get("ballot")).get("counter"));
    }
    static void assertPrepareBlocked(MembershipGrantJournal store,Path node,Seed seed)throws IOException {
        var before=V53ReplayFilesTest.files(node);
        assertArrayEquals(store.originalBasis().orElseThrow().bytes(),store.prepareCurrent(object(store.promised().orElseThrow().value().get("ballot"))).bytes(),
                "the exact forced grant remains replayable without opening another campaign");
        String reason=assertThrows(IllegalArgumentException.class,
                ()->store.prepareCurrent(seed.fixture().f.initial.application.f.f.f.fixture.source.ballot(22))).getMessage();
        assertTrue(Set.of("carried application staging must retire before another authority change",
                "staged retirement must finish before authority changes","carried vote must transfer before another authority change").contains(reason),reason);
        assertEquals(before,V53ReplayFilesTest.files(node),"a later campaign cannot strand the original staged retirement");
    }

    @Test void threeStagedCertifiedOwnersRecoverPublishOnceAndContinueTheNewRound()throws Exception {
        Path root=Path.of("target/v53-staged-handoff").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);
        var receipt=new TreeMap<String,Object>();receipt.put("schema","gse-v53-staged-handoff-v1");receipt.put("status","FAIL");
        receipt.put("execution","private-staged-application-handoff");receipt.put("historicalBootstrap","conditional-fixture");
        receipt.put("freshProcesses",false);receipt.put("runtimeEnabled",false);receipt.put("powerLoss",false);
        try {
            var seed=seed(root);var f=seed.fixture();var old=new TreeMap<Integer,MembershipGrantJournal.Applied>();
            Files.write(root.resolve("entry.gsr"),seed.entry().bytes());Files.write(root.resolve("payload.bin"),seed.payload());
            receipt.put("entry",seed.entry().digest());receipt.put("origin",20L);receipt.put("acceptBallot",21L);receipt.put("selectedCut",1L);
            V53CarriedPublicationTest.snapshot(f,"old-certified");
            for(int n:NODES)try(var store=f.f.open(n)){old.put(n,apply(store,seed));}
            V53CarriedPublicationTest.snapshot(f,"staged");var setup=f.f.prepare(1);V53CarriedPublicationTest.snapshot(f,"prepared");
            for(int n:NODES)try(var store=f.f.open(n)) {
                var installed=store.installCurrent(setup.sources(),List.of(),setup.images());var before=V53ReplayFilesTest.files(f.f.node(n));
                assertArrayEquals(installed.bytes(),store.installCurrent(setup.sources(),List.of(),setup.images()).bytes());
                assertEquals(before,V53ReplayFilesTest.files(f.f.node(n)),"a lost installation response may be replayed without changing authority");
            }
            V53CarriedPublicationTest.snapshot(f,"installed");
            for(int n:NODES) {
                Path node=f.f.node(n);byte[] vote=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE));
                byte[] selector=Files.readAllBytes(node.resolve(MembershipCurrentGeneration.SELECTOR));
                var events=new ArrayList<String>();
                try(var store=f.f.open(n,events::add)) {
                    var before=V53ReplayFilesTest.files(node);
                    assertThrows(IllegalArgumentException.class,()->apply(store,seed));
                    assertEquals("carried application staging must retire before another authority change",
                            assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(seed.entry(),seed.payload())).getMessage());
                    assertThrows(IllegalArgumentException.class,()->store.publishCurrent(old.get(n),List.of(),Set.of(),List.of()));
                    assertPrepareBlocked(store,node,seed);assertEquals(before,V53ReplayFilesTest.files(node));events.clear();retire(store,seed);
                    assertFalse(events.stream().anyMatch(e->e.startsWith("APPLY_ACK_") || e.equals("APPLY_BEFORE_RETURN")),"retirement must not issue an old ACK");
                    assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
                    assertArrayEquals(selector,Files.readAllBytes(node.resolve(MembershipCurrentGeneration.SELECTOR)));
                    noStaging(node);retire(store,seed);assertPrepareBlocked(store,node,seed);assertEquals(seed.phased().certificate().digest(),store.currentCertificate().orElseThrow().digest());
                }
            }
            V53CarriedPublicationTest.snapshot(f,"retired");
            for(int n:NODES)try(var store=f.f.open(n)){store.acceptCurrent(seed.entry(),seed.payload());assertNewAcceptance(f.f.node(n),seed);}
            V53CarriedPublicationTest.snapshot(f,"reaccepted");f.f.maintain(setup.obsolete());V53CarriedPublicationTest.snapshot(f,"reclaimed");
            var publication=f.apply(seed.entry(),seed.payload());
            for(int n:NODES)try(var store=f.f.open(n)) {
                assertNotEquals(old.get(n).plan().originalCertificate().digest(),publication.applied().get(n).plan().originalCertificate().digest());
                assertThrows(IllegalArgumentException.class,()->store.publishCurrent(old.get(n),publication.acks(),publication.checkpoints(),publication.bridges()),
                        "an old Applied object must not acquire the new certificate's authority");
            }
            V53CarriedPublicationTest.finish(f,publication);V53CarriedPublicationTest.snapshot(f,"published");
            var barrier=new TreeMap<>(f.entry("BARRIER",new byte[0]).value());barrier.put("origin",setup.ballot());
            V53CarriedPublicationTest.finish(f,f.apply(decode(encode("records","ENTRY",barrier),"records","ENTRY"),new byte[0]));V53CarriedPublicationTest.snapshot(f,"continued");
            for(int n:NODES)try(var store=f.f.open(n)) {
                var copy=store.floorCopyCurrent();assertEquals(3L,copy.capsule.context.cut.get("index"));assertEquals(43L,copy.capsule.context.catalog.get("applicationSequence"));
                var state=f.f.initial.application.app.read(copy.fileBytes(copy.capsule.terminal().application()+".image"),"staged-final-"+n);
                assertEquals(1,state.documents().stream().filter(d->d.equals(new Doc(303,"staged-original"))).count());
                noStaging(f.f.node(n));assertTrue(store.currentCertificate().isEmpty());assertTrue(store.currentOwnedTail().isEmpty());
                var fresh=store.prepareCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(22));assertNull(fresh.value().get("accepted"));
                assertEquals(3L,object(fresh.value().get("cut")).get("index"));
            }
            V53CarriedPublicationTest.snapshot(f,"fresh");assertEquals(0,f.f.resources.usage().leases());assertTrue(f.f.maximumImages<=7);
            receipt.put("publishedCut",3L);receipt.put("applicationSequence",43L);receipt.put("maximumImages",f.f.maximumImages);
            receipt.put("maximumMetadata",f.f.maximumMetadata);receipt.put("maximumStaging",f.f.maximumStaging);receipt.put("status","PASS");
        }catch(Exception|Error error){receipt.put("failure",error.getClass().getSimpleName()+": "+error.getMessage());throw error;}
        finally {
            Files.write(root.resolve("receipt.json"),canonical(receipt,16384));System.out.println("v53StagedHandoffEvidence="+root.toAbsolutePath());
        }
    }

    @Test void cleanupUsesTheOriginalLocalCertifiedSourceWhenTheNewGenerationHasOnlyAProof()throws Exception {
        var seed=seed(temp.resolve("local-certificate"),Set.of(1));var f=seed.fixture();
        for(int n:NODES)try(var store=f.f.open(n)) {
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(n).resolve(MembershipPendingAccept.FILE)));
            assertNotNull(vote.proof());assertEquals(n==1,vote.certificate()!=null);
            if(n==1)apply(store,seed);
        }
        var ballot=new TreeMap<>(nextBallot(seed));ballot.put("proposer","node-3");
        ballot.put("incarnation",V53DeclarationsTest.node(3).storageId().toString());
        var images=images(seed);var sources=new ArrayList<MembershipSelection.Source>();
        for(int n:NODES)try(var store=f.f.open(n)){store.prepareCurrent(ballot);sources.add(store.originalSource());}
        var decision=new MembershipSelection.Campaign(sources.get(2)).select(sources,List.of());
        assertEquals("node-3",decision.longest().owner.nodeId().value());
        assertFalse(decision.longest().capsule.packet.objectNames().contains(seed.phased().certificate().digest()));
        assertTrue(sources.getFirst().capsule.packet.objectNames().contains(seed.phased().certificate().digest()));
        for(int n:NODES)try(var store=f.f.open(n)) {
            store.selectCurrent(sources,List.of());store.installCurrent(sources,List.of(),images);
            var selector=decode(Files.readAllBytes(f.f.node(n).resolve("selector.gsr")),"records","SELECTOR");
            var installed=MembershipSourcePacket.decode(Files.readAllBytes(f.f.node(n).resolve("generations").resolve((String)selector.value().get("generation")).resolve("source.gscp")));
            assertFalse(installed.objectNames().contains(seed.phased().certificate().digest()),
                    "the chosen node 3 capsule has never received the old certificate");
        }
        Path node=f.f.node(1);byte[] vote=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE));
        try(var store=f.f.open(1)) {
            assertPrepareBlocked(store,node,seed);retire(store,seed);noStaging(node);
            assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
            store.acceptCurrent(seed.entry(),seed.payload());assertNewAcceptance(node,seed);
        }
        assertEquals(0,f.f.resources.usage().leases());
    }

    @Test void originalReplayPlanImageAndAckPrefixesCanYieldToTheExactHigherSelection()throws Exception {
        var seed=seed(temp.resolve("seed"));var images=images(seed);var others=otherSources(seed);
        for(String point:List.of("REPLAY_DIRECTORY_CREATED","REPLAY_CLAIM_PREFIX_WRITTEN","REPLAY_CLAIM_FORCED","REPLAY_APPLICATION_FINISHED",
                "APPLY_PLAN_PREFIX_WRITTEN","APPLY_IMAGE_PREFIX_WRITTEN","APPLY_END_FORCED","APPLY_ACK_PREFIX_WRITTEN","APPLY_BEFORE_RETURN")) {
            Path node=temp.resolve(point);V53JournalApplicationTest.copy(seed.fixture().f.node(1),node);var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var store=open(node,1,seed,resources,e->{if(e.equals(point))throw new IOException("initial staged cut");})) {
                assertThrows(IOException.class,()->apply(store,seed),point);
            }assertEquals(0,resources.usage().leases());
            byte[] vote=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE));
            try(var store=open(node,1,seed,resources,e->{})){install(store,seed,others,images);}
            try(var store=open(node,1,seed,resources,e->{})) {
                assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(seed.entry(),seed.payload()));
                assertPrepareBlocked(store,node,seed);
                retire(store,seed);noStaging(node);assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
                store.acceptCurrent(seed.entry(),seed.payload());assertNewAcceptance(node,seed);
            }assertEquals(0,resources.usage().leases());
            try(var ignored=open(node,1,seed,resources,e->{})){assertNewAcceptance(node,seed);}assertEquals(0,resources.usage().leases());
        }
    }

    @Test void installedHigherAuthorityAndActualOldPhasedEvidenceAreMandatory()throws Exception {
        var seed=seed(temp.resolve("authority"));var f=seed.fixture();Path node=f.f.node(1);
        try(var store=f.f.open(1)) {
            apply(store,seed);var before=V53ReplayFilesTest.files(node);
            assertThrows(IllegalArgumentException.class,()->retire(store,seed));assertEquals(before,V53ReplayFilesTest.files(node));
            store.prepareCurrent(nextBallot(seed));before=V53ReplayFilesTest.files(node);
            assertThrows(IllegalArgumentException.class,()->retire(store,seed));assertEquals(before,V53ReplayFilesTest.files(node));
        }
        var others=otherSources(seed);var images=images(seed);
        try(var store=f.f.open(1)) {
            install(store,seed,others,images);var before=V53ReplayFilesTest.files(node);var usage=f.f.resources.usage();var app=f.f.initial.application.app;
            assertThrows(IllegalArgumentException.class,()->store.retireSupersededApplication(app.configuration(),app.storage(),Set.of()));
            assertThrows(IllegalArgumentException.class,()->store.retireSupersededApplication(app.configuration(),app.storage(),seed.phased().accepts()));
            assertPrepareBlocked(store,node,seed);
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(usage,f.f.resources.usage());
            store.observeCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(22));
            assertThrows(IllegalArgumentException.class,()->retire(store,seed));assertEquals(before,V53ReplayFilesTest.files(node));
        }
        assertEquals(0,f.f.resources.usage().leases());
        try(var store=f.f.open(1)){retire(store,seed);noStaging(node);store.acceptCurrent(seed.entry(),seed.payload());}
        assertEquals(0,f.f.resources.usage().leases());
    }

    @Test void laterVolatileObservationInterruptsCleanupWithoutRevivingAnOldAcknowledgement()throws Exception {
        var seed=seed(temp.resolve("observed-seed"));var f=seed.fixture();
        try(var store=f.f.open(1)){apply(store,seed);}var others=otherSources(seed);var images=images(seed);
        try(var store=f.f.open(1)){install(store,seed,others,images);}
        for(String point:List.of("STAGED_RETIREMENT_AUTHORITY_VALIDATED","SUPERSEDED_END_AUTHORITY_FORCED",
                "SUPERSEDED_END_FILE_DELETED","SUPERSEDED_END_RETIREMENT_DELETED")) {
            Path node=temp.resolve(point);V53JournalApplicationTest.copy(f.f.node(1),node);var resources=new MembershipResources(512*MembershipResources.MIB);
            byte[] vote=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)),journal=Files.readAllBytes(node.resolve("grants.gsr"));
            MembershipGrantJournal[] owner={null};boolean[] hit={false};
            try(var store=open(node,1,seed,resources,e->{if(e.equals(point)) {
                hit[0]=true;owner[0].observeCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(22));
            }})) {
                owner[0]=store;assertThrows(IllegalArgumentException.class,()->retire(store,seed));assertTrue(hit[0]);
            }
            assertEquals(0,resources.usage().leases());assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
            assertArrayEquals(journal,Files.readAllBytes(node.resolve("grants.gsr")),"observation is not a durable promise");
            try(var store=open(node,1,seed,resources,e->{})) {
                retire(store,seed);noStaging(node);assertPrepareBlocked(store,node,seed);
                store.acceptCurrent(seed.entry(),seed.payload());assertNewAcceptance(node,seed);
            }
            assertEquals(0,resources.usage().leases());
        }
    }

    @Test void retirementManifestAndPartialDeletionResumeWithoutDiscardingTheOldVote()throws Exception {
        var seed=seed(temp.resolve("retirement-seed"));var f=seed.fixture();
        try(var store=f.f.open(1)){apply(store,seed);}var others=otherSources(seed);var images=images(seed);
        try(var store=f.f.open(1)){install(store,seed,others,images);}
        for(String point:List.of("SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN","SUPERSEDED_END_AUTHORITY_FORCED","SUPERSEDED_END_FILE_DELETED","SUPERSEDED_END_RETIREMENT_DELETED")) {
            Path node=temp.resolve(point);V53JournalApplicationTest.copy(f.f.node(1),node);var resources=new MembershipResources(512*MembershipResources.MIB);
            byte[] vote=Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE));
            try(var store=open(node,1,seed,resources,e->{if(e.equals(point))throw new IOException("first cleanup cut");})) {
                assertThrows(IOException.class,()->retire(store,seed));
            }assertEquals(0,resources.usage().leases());assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
            try(var store=open(node,1,seed,resources,e->{if(e.equals("SUPERSEDED_END_AUTHORITY_FORCED"))throw new IOException("recovery cleanup cut");})) {
                assertPrepareBlocked(store,node,seed);
                assertThrows(IOException.class,()->retire(store,seed));
            }assertEquals(0,resources.usage().leases());assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
            try(var store=open(node,1,seed,resources,e->{})) {
                retire(store,seed);noStaging(node);assertArrayEquals(vote,Files.readAllBytes(node.resolve(MembershipPendingAccept.FILE)));
                store.acceptCurrent(seed.entry(),seed.payload());assertNewAcceptance(node,seed);
            }assertEquals(0,resources.usage().leases());
        }
    }
}
