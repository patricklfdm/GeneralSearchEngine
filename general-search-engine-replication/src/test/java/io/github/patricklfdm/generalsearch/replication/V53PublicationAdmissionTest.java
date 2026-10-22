package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Real admission against conditional earlier checkpoint ancestry; no public bootstrap claim. */
class V53PublicationAdmissionTest {
    @TempDir Path temp;
    static final class Fixture {
        final Path root;final V53PendingProofFixture f;final V53ApplicationReplayTest application=new V53ApplicationReplayTest();final List<MembershipSelection.Bridge> bridges=new ArrayList<>();
        Fixture(Path root,int groups)throws Exception {
            this.root=root;Files.createDirectories(root);
            application.temp=root;var source=new V53ContextFixture(3,"ADD",application.initial(41),V53ApplicationImageTest.HISTORY,41);for(int i=0;i<8;i++)source.commit("BARRIER",null,()->{});
            var prefix=new V53CapsuleFixture(source,"ADD",8);
            f=new V53PendingProofFixture(new V53CurrentGenerationFixture(3,prefix),command("BARRIER",(Object)null),"BARRIER");
            f.provision(root);f.install(root);
            var copies=new ArrayList<MembershipFloor.Copy>();for(int n:f.nodes)try(var store=open(n,new ArrayList<>())){copies.add(store.floorCopyCurrent());}
            for(int n:f.nodes)try(var store=open(n,new ArrayList<>())){store.establishFloor(copies);store.retireInactive();store.releaseFloor();}
            for(int i=1;i<=groups;i++) {
                var statement=decode(encode("records","CHECKPOINT",Map.of("root",source.rootHash,"scope","RANGE",
                        "start",prefix.state(i).get("cut"),"end",prefix.state(8).get("cut"),"catalogBefore",prefix.catalog(i),"catalogAfter",prefix.catalog(8),
                        "applicationBefore",prefix.state(i).get("application"),"applicationAfter",prefix.state(8).get("application"))),"records","CHECKPOINT");
                var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
                for(int n:f.nodes) {
                    var id=V53DeclarationsTest.node(n);var ack=decode(encode("records","CHECKPOINT_ACK",Map.of("root",source.rootHash,"statement",statement.digest(),
                            "cut",f.f.admitted.context.cut,"voter",id.nodeId().value(),"incarnation",id.storageId().toString())),"records","CHECKPOINT_ACK");
                    acks.add(ack);owned.add(new Owned(id.nodeId().value(),id.storageId(),ack.digest(),cutDigest(f.f.admitted.context.cut)));
                }
                bridges.add(new MembershipSelection.Bridge(statement,acks,owned));prefix.owned.addAll(owned);
            }
            // Provision historical ancestry as a fixture, with exact manifest/selector hashes.
            // New grant, selection, admission and vote persistence above/below use actual owners.
            if(groups>0)for(int n:f.nodes) {
                Path path=f.node(root,n).resolve("generations/b");byte[] ancestry=MembershipGenerationPlan.ancestry(bridges);Files.write(path.resolve("ancestry.gsr"),ancestry);
                var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generation.gsr")),"records","GENERATION").value());
                var inventory=new ArrayList<Object>(list(manifest.get("files")));inventory.add(Map.of("path","ancestry.gsr","size",(long)ancestry.length,"sha256",hash(ancestry)));inventory.sort(Comparator.comparing(v->(String)object(v).get("path")));manifest.put("files",inventory);
                byte[] bytes=encode("records","GENERATION",manifest);Files.write(path.resolve("generation.gsr"),bytes);
                Files.write(f.node(root,n).resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",source.rootHash,"node","node-"+n,"generation","b","digest",hash(bytes))));
            }
        }
        Path node(){return f.node(root,1);}
        MembershipGrantJournal open(int n,List<String> events)throws Exception {
            return MembershipGrantJournal.openApplying(f.node(root,n),f.f.root(),V53DeclarationsTest.node(n),f.resources(),f.f::verify,events::add);
        }
    }
    @Test void seventhFutureGroupRefusesBeforeAnyVoteOrApplicationReservation()throws Exception {
        var f=new Fixture(temp,6);var before=V53ReplayFilesTest.files(f.node());var events=new ArrayList<String>();
        var resources=f.f.resources();
        try(var store=MembershipGrantJournal.openApplying(f.node(),f.f.f.root(),V53DeclarationsTest.node(1),resources,f.f.f::verify,events::add)) {
            var usage=resources.usage();events.clear();var failure=assertThrows(MembershipOperationException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));
            assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,failure.reason());
            assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,failure.outcome());
            assertTrue(events.isEmpty(),events.toString());assertTrue(store.currentOwnedTail().isEmpty());assertEquals(usage,resources.usage());
            assertEquals(before,V53ReplayFilesTest.files(f.node()));
            // Refusal does not poison the owner or discard its original frozen source.
            assertEquals(8L,object(store.originalSource().basis.value().get("cut")).get("index"));
        }
        assertEquals(before,V53ReplayFilesTest.files(f.node()));
        try(var store=f.open(1,events)){assertThrows(MembershipOperationException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));}
        assertEquals(before,V53ReplayFilesTest.files(f.node()));
    }
    @Test void sixthFutureGroupFitsAndAnExactDuplicateKeepsItsOriginalVote()throws Exception {
        var f=new Fixture(temp,5);var events=new ArrayList<String>();
        try(var store=f.open(1,events)) {
            var first=store.acceptCurrent(f.f.entry(),f.f.payload());byte[] vote=Files.readAllBytes(f.node().resolve(MembershipPendingAccept.FILE));
            events.clear();assertEquals(first,store.acceptCurrent(f.f.entry(),f.f.payload()));
            assertArrayEquals(vote,Files.readAllBytes(f.node().resolve(MembershipPendingAccept.FILE)));assertFalse(events.contains("ACCEPT_VALIDATED"));
        }
        try(var store=f.open(1,events)){assertTrue(store.currentOwnedTail().isPresent());}
    }
    @Test void sixGroupsProceedThroughActualCertificateApplicationPublicationAndReopen()throws Exception {
        var f=new Fixture(temp,5);var cohort=certify(f,false);var applied=new TreeMap<Integer,MembershipGrantJournal.Applied>();
        var acknowledgements=new ArrayList<Decoded>();var checkpoints=new HashSet<Owned>();
        var grouped=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
        for(int n:f.f.nodes)try(var store=f.open(n,new ArrayList<>())) {
            var result=store.applyCurrent(f.application.configuration(),f.application.storage(),cohort.owned());applied.put(n,result);
            assertEquals(5,result.endorsement().ancestors().size());assertEquals(41,result.plan().application.sequence());
            acknowledgements.add(result.endorsement().acknowledgement());checkpoints.add(result.endorsement().owned());
            var ends=new ArrayList<>(result.endorsement().ancestors());ends.add(result.endorsement().parent().orElseThrow());
            for(var end:ends)grouped.computeIfAbsent(number(object(end.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(end);
        }
        var bridges=new ArrayList<MembershipSelection.Bridge>();f.f.f.fixture.owned.addAll(cohort.owned());f.f.f.fixture.owned.addAll(checkpoints);
        for(var ends:grouped.values()) {
            var owned=new HashSet<Owned>();ends.forEach(e->owned.add(e.owned()));f.f.f.fixture.owned.addAll(owned);
            bridges.add(new MembershipSelection.Bridge(ends.getFirst().statement(),ends.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),owned));
        }
        assertEquals(6,bridges.size());
        for(int n:f.f.nodes)try(var store=f.open(n,new ArrayList<>())) {
            byte[] selected=Files.readAllBytes(f.f.node(temp,n).resolve("generations/b/selected.gsr"));
            store.publishCurrent(applied.get(n),acknowledgements,checkpoints,bridges);
            assertEquals(9L,store.floorCopyCurrent().capsule.context.cut.get("index"));assertTrue(store.currentCertificate().isEmpty());
            assertArrayEquals(selected,Files.readAllBytes(f.f.node(temp,n).resolve("generations/a/selected.gsr")));
        }
        for(int n:f.f.nodes)try(var store=f.open(n,new ArrayList<>())){assertEquals(9L,store.floorCopyCurrent().capsule.context.cut.get("index"));}
    }
    static V53PendingCertificateFixture.Cohort certify(Fixture f,boolean legacy)throws Exception {
        var accepts=new HashSet<Owned>();
        for(int n:f.f.nodes)try(var store=legacy?f.f.open(f.root,n,f.f.resources(),e->{}):f.open(n,new ArrayList<>())){accepts.add(store.acceptCurrent(f.f.entry(),f.f.payload()));}
        var proof=f.f.proof(accepts);var proofs=new HashSet<Owned>();
        for(int n:f.f.nodes)try(var store=f.open(n,new ArrayList<>())){proofs.add(store.proveCurrent(proof,accepts));}
        var certificate=new V53PendingCertificateFixture(f.f).certificate(proof,proofs);
        var cohort=new V53PendingCertificateFixture.Cohort(proof,certificate,accepts,proofs);
        for(int n:f.f.nodes)try(var store=f.open(n,new ArrayList<>())){store.certifyCurrent(certificate,cohort.owned());}
        return cohort;
    }
    @Test void oldAcknowledgedVotesRemainReadableAndDuplicateButOversizedReplayRefusesBeforeScratch()throws Exception {
        var f=new Fixture(temp,6);var cohort=certify(f,true);var before=V53ReplayFilesTest.files(f.node());var events=new ArrayList<String>();
        try(var store=f.open(1,events)) {
            assertNotNull(store.acceptCurrent(f.f.entry(),f.f.payload()));events.clear();
            var error=assertThrows(MembershipOperationException.class,()->store.applyCurrent(f.application.configuration(),f.application.storage(),cohort.owned()));
            assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE,error.outcome());assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());
            assertEquals(cohort.certificate().digest(),store.currentCertificate().orElseThrow().digest());assertTrue(events.isEmpty(),events.toString());
        }
        assertEquals(before,V53ReplayFilesTest.files(f.node()));assertFalse(Files.exists(f.application.storage().directory()));
    }
    @Test void admittedVoteCandidateResumesExactBytesAndHigherBallotStillFences()throws Exception {
        var f=new Fixture(temp,5);var r=f.f.resources();
        try(var store=MembershipGrantJournal.openApplying(f.node(),f.f.f.root(),V53DeclarationsTest.node(1),r,f.f.f::verify,e->{
            if(e.equals("ACCEPT_PREFIX_WRITTEN"))throw new java.io.IOException("interrupted accepted candidate");
        })){assertThrows(java.io.IOException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));}
        byte[] prefix=Files.readAllBytes(f.node().resolve(MembershipPendingAccept.NEXT));
        try(var store=f.open(1,new ArrayList<>())) {
            assertThrows(IllegalArgumentException.class,store::currentOwnedTail);assertNotNull(store.acceptCurrent(f.f.entry(),f.f.payload()));
            byte[] vote=Files.readAllBytes(f.node().resolve(MembershipPendingAccept.FILE));assertArrayEquals(prefix,Arrays.copyOf(vote,prefix.length));
            store.observeCurrent(f.f.f.fixture.source.ballot(21));assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));
            assertArrayEquals(vote,Files.readAllBytes(f.node().resolve(MembershipPendingAccept.FILE)));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void coverageByteSizingMatchesRealEncodingAndRejectsLongIdentityOverflow() {
        var fixture=new V53CapsuleFixture(5,"REPLACE",4);var parent=fixture.verify().terminal();
        var certificate=decode(fixture.source.inventory.get(fixture.source.steps.getFirst().get("certificate")),"records","CERTIFICATE");
        // Only the serialized footprint is tested here, not authority for these synthetic anchors.
        var names=new ArrayList<String>();for(int i=1;i<=5;i++)names.add("node-"+i+"x".repeat(58));
        var view=new TreeMap<>(object(parent.cut().get("view")));view.put("old",names);view.put("new",names);
        var cut=new TreeMap<>(parent.cut());cut.put("view",view);cut.put("index",99L);
        parent=new MembershipCapsule.Anchor(cut,parent.catalog(),parent.application());
        var lower=new ArrayList<MembershipCapsule.Anchor>();for(long i=1;i<=5;i++) {
            var c=new TreeMap<>(cut);c.put("index",i);lower.add(new MembershipCapsule.Anchor(c,parent.catalog(),parent.application()));
        }
        var exactParent=parent;
        assertTrue(MembershipSelectionCoverage.publicationBytes(certificate,parent,lower)>MembershipSelectionCoverage.MAXIMUM);
        assertEquals("JSON exceeds frame bound",assertThrows(ReplicationException.class,()->MembershipSelectionCoverage.encodeCoverage(certificate,exactParent,certificate,lower)).getMessage());
        var small=lower.subList(0,1);
        assertEquals(MembershipSelectionCoverage.encodeCoverage(certificate,parent,certificate,small).length,
                MembershipSelectionCoverage.publicationBytes(certificate,parent,small));
    }

}
