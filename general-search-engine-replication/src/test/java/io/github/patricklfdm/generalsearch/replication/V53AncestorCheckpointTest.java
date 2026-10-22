package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual renewal after real sources at different original cuts; earlier bootstrap/bridges are historical fixtures. */
class V53AncestorCheckpointTest {
    @TempDir Path temp;
    static final class Fixture {
        final Path root;
        final V53JournalApplicationTest application=new V53JournalApplicationTest();
        final Set<Owned> historical=new HashSet<>(),observations=new HashSet<>(),checkpoints=new HashSet<>();
        final List<Decoded> acknowledgements=new ArrayList<>();
        final List<MembershipSelection.Bridge> bridges=new ArrayList<>(),oldBridges=new ArrayList<>();
        final Map<Integer,MembershipGrantJournal.Applied> applied=new TreeMap<>();
        Fixture(Path root,boolean local)throws Exception {
            this.root=root;Files.createDirectories(root);var app=new V53ApplicationReplayTest();app.temp=root;
            application.configure(root,app.initial(41),3,4);var f=application.f.f.f.fixture;historical.addAll(f.owned);
            for(int from:List.of(1,2)) {
                var statement=decode(encode("records","CHECKPOINT",Map.of("root",f.source.rootHash,"scope","RANGE","start",f.state(from).get("cut"),"end",f.state(4).get("cut"),
                        "catalogBefore",f.catalog(from),"catalogAfter",f.catalog(4),"applicationBefore",f.state(from).get("application"),"applicationAfter",f.state(4).get("application"))),"records","CHECKPOINT");
                var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
                for(int n:List.of(1,2,3)) {
                    var id=V53DeclarationsTest.node(n);var ack=decode(encode("records","CHECKPOINT_ACK",Map.of("root",f.source.rootHash,"statement",statement.digest(),
                            "cut",f.state(4).get("cut"),"voter",id.nodeId().value(),"incarnation",id.storageId().toString())),"records","CHECKPOINT_ACK");
                    acks.add(ack);owned.add(new Owned(id.nodeId().value(),id.storageId(),ack.digest(),cutDigest(object(f.state(4).get("cut")))));
                }
                oldBridges.add(new MembershipSelection.Bridge(statement,acks,owned));historical.addAll(owned);
            }
            var sources=new ArrayList<MembershipSelection.Source>();
            for(int n:List.of(1,2,3)) {
                var initial=new V53CapsuleFixture(new V53ContextFixture(3,"REPLACE",application.base,V53ApplicationImageTest.HISTORY,41),"REPLACE",n==3?4:n);
                historical.addAll(initial.owned);observations.addAll(historical);
                V53PendingProofFixture.provisionNode(new V53CurrentGenerationFixture(3,initial),node(n),n);
                try(var store=open(n,e->{})){store.prepareCurrent(f.source.ballot(20));sources.add(store.originalSource());}
            }
            for(int n:List.of(1,2,3))try(var store=open(n,e->{})){store.selectCurrent(sources,oldBridges);store.installCurrent(sources,oldBridges,f.source.images);}
            var copies=new ArrayList<MembershipFloor.Copy>();for(int n:List.of(1,2,3))try(var store=open(n,e->{})){copies.add(store.floorCopyCurrent());}
            for(int n:List.of(1,2,3))try(var store=open(n,e->{})){store.establishFloor(copies);store.retireInactive();store.releaseFloor();}
            var accepts=new HashSet<Owned>();for(int n:List.of(1,2,3))try(var store=open(n,e->{})){accepts.add(store.acceptCurrent(application.f.f.entry(),application.f.f.payload()));}
            var proof=application.f.f.proof(accepts);var proofs=new HashSet<Owned>();for(int n:List.of(1,2,3))try(var store=open(n,e->{})){proofs.add(store.proveCurrent(proof,accepts));}
            application.cohort=new V53PendingCertificateFixture.Cohort(proof,application.f.certificate(proof,proofs),accepts,proofs);observations.addAll(application.cohort.owned());
            for(int n:List.of(1,2,3))try(var store=open(n,e->{})){store.certifyCurrent(application.cohort.certificate(),application.cohort.owned());}
            var grouped=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
            for(int n:local?List.of(1,2,3):List.of(2,3))try(var store=open(n,e->{})) {
                var result=application.apply(store);applied.put(n,result);acknowledgements.add(result.endorsement().acknowledgement());checkpoints.add(result.endorsement().owned());
                var ends=new ArrayList<>(result.endorsement().ancestors());ends.add(result.endorsement().parent().orElseThrow());
                for(var end:ends)grouped.computeIfAbsent(number(object(end.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(end);
            }
            observations.addAll(checkpoints);
            for(var ends:grouped.values()) {
                var owned=new HashSet<Owned>();ends.forEach(e->owned.add(e.owned()));observations.addAll(owned);
                bridges.add(new MembershipSelection.Bridge(ends.getFirst().statement(),ends.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),owned));
            }
        }
        Path node(int n){return application.f.f.node(root,n);}
        MembershipGrantJournal open(int n,MembershipBallotAllocator.Cut cut)throws Exception {
            return MembershipGrantJournal.openApplying(node(n),application.f.f.f.root(),V53DeclarationsTest.node(n),application.f.f.resources(),
                    (r,p,i)->MembershipCapsule.verify(r,p,i,observations),cut);
        }
        Decoded publish(MembershipGrantJournal store,int n)throws Exception {return store.publishCurrent(applied.get(n),acknowledgements,checkpoints,bridges);}
        void retain()throws Exception {
            Files.write(root.resolve("base.image"),application.base);
            var bridgeOwned=new HashSet<Owned>();bridges.forEach(b->bridgeOwned.addAll(b.owned));
            Files.write(root.resolve("observations.json"),canonical(Map.of("accepts",V53JournalApplicationTest.observations(application.cohort.accepts()),"proofs",V53JournalApplicationTest.observations(application.cohort.proofs()),
                    "checkpoints",V53JournalApplicationTest.observations(checkpoints),"bridges",observations(bridgeOwned),"historical",observations(historical)),65536));
            for(var ack:acknowledgements)Files.write(root.resolve("ack-"+ack.value().get("voter")+".gsr"),ack.bytes());
            for(var bridge:bridges) {
                String start="bridge-"+object(bridge.statement.value().get("start")).get("index");Files.write(root.resolve(start+"-statement.gsr"),bridge.statement.bytes());
                for(var ack:bridge.acknowledgements)Files.write(root.resolve(start+"-"+ack.value().get("voter")+".gsr"),ack.bytes());
            }
        }
    }
    static List<Map<String,Object>> observations(Set<Owned> rows) {
        return rows.stream().sorted(Comparator.comparing(Owned::record).thenComparing(Owned::voter)).map(v->Map.<String,Object>of("voter",v.voter(),"storage",v.storage().toString(),"record",v.record(),"parent",v.parent())).toList();
    }
    static final List<String> PROCESS_CUTS=List.of("APPLY_ANCESTOR_0_STATEMENT_PREFIX_WRITTEN","APPLY_ANCESTOR_1_ACK_PREFIX_WRITTEN","APPLY_ANCESTOR_1_ACK_FORCED",
            "PUBLICATION_SELECTOR_FORCED","COVERED_END_FILE_DELETED","COVERED_VOTE_PREFIX_WRITTEN");
    @Test void actualDifferentFrozenSourcesRenewToOneNewEndAndPublishAllOriginalAncestry()throws Exception {
        var f=new Fixture(temp,true);assertEquals(3,f.bridges.size());
        for(int n:List.of(1,2,3))try(var store=f.open(n,e->{})) {
            var applied=f.applied.get(n);assertEquals(List.of(1L,2L),applied.plan().additionalParents().stream().map(a->number(a.cut().get("index"))).toList());
            assertEquals(2,applied.endorsement().ancestors().size());assertEquals(4L,number(applied.plan().originalParent().cut().get("index")));
            byte[] original=Files.readAllBytes(f.node(n).resolve("generations/b/basis.gsr"));f.publish(store,n);assertTrue(store.currentCertificate().isEmpty());var copy=store.floorCopyCurrent();
            var originalBasis=decode(original,"records","BASIS");
            assertEquals((long)(n==3?4:n),object(originalBasis.value().get("cut")).get("index"));
            assertArrayEquals(original,Files.readAllBytes(f.node(n).resolve("generations/a/basis.gsr")));
            copy.capsule.verifyAncestry(MembershipGenerationPlan.ancestry(f.bridges),applied.plan().additionalParents());
            assertEquals(5L,copy.capsule.context.cut.get("index"));assertFalse(Files.exists(f.node(n).resolve("applied-end")));
        }
        for(int n:List.of(1,2,3))try(var store=f.open(n,e->{})){assertEquals(5L,object(store.prepareCurrent(f.application.f.f.f.fixture.source.ballot(21)).value().get("cut")).get("index"));}
    }
    @Test void missingStaleOrForeignRenewedEndorsementsCannotPublishOrReplaceTheLocalPlan()throws Exception {
        var f=new Fixture(temp,true);var before=V53ReplayFilesTest.files(f.node(1));
        try(var store=f.open(1,e->{})) {
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(1),f.acknowledgements,f.checkpoints,f.bridges.subList(1,3)));
            var stale=new ArrayList<>(f.oldBridges);stale.add(f.bridges.getLast());
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(f.applied.get(1),f.acknowledgements,f.checkpoints,stale));
            var e=f.applied.get(1).endorsement();var wrong=new MembershipAppliedEndFiles.Endorsement(e.acknowledgement(),e.owned(),e.parent(),f.applied.get(2).endorsement().ancestors());
            assertThrows(IllegalArgumentException.class,()->store.publishCurrent(new MembershipGrantJournal.Applied(f.applied.get(1).plan(),wrong),f.acknowledgements,f.checkpoints,f.bridges));
            f.observations.removeAll(f.bridges.getFirst().owned);assertThrows(IllegalArgumentException.class,()->f.publish(store,1));
            assertEquals(before,V53ReplayFilesTest.files(f.node(1)));
        }
    }
    @Test void everyAdditionalWriteIsResumableAndObservedHigherBallotFencesEveryReturn()throws Exception {
        for(int index:List.of(0,1))for(String part:List.of("STATEMENT","ACK"))for(String suffix:List.of("CREATED","PREFIX_WRITTEN","WRITTEN","FORCED")) {
            String point="APPLY_ANCESTOR_"+index+"_"+part+"_"+suffix;var f=new Fixture(temp.resolve(point),false);
            try(var store=f.open(1,e->{if(e.equals(point))throw new IOException(point);})){assertThrows(IOException.class,()->f.application.apply(store));}
            MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(1,e->{if(e.equals("APPLY_ANCESTOR_1_ACK_FORCED"))ref[0].observeCurrent(f.application.f.f.f.fixture.source.ballot(21));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->f.application.apply(store));
            }
            try(var store=f.open(1,e->{})){f.applied.put(1,f.application.apply(store));f.publish(store,1);}
        }
    }
    @Test void coveredCleanupAndPartialAckRejectMissingAlteredLinkedOrUnexpectedAncestorFiles()throws Exception {
        for(String damage:List.of("statement","ack","plan","missing-plan","extra","link")) {
            var f=new Fixture(temp.resolve(damage),true);Path end=f.node(1).resolve("applied-end");
            try(var store=f.open(1,e->{if(e.equals("PUBLICATION_SELECTOR_FORCED"))throw new IOException("stop");})){assertThrows(IOException.class,()->f.publish(store,1));}
            switch(damage) {
                case "statement","ack" -> {Path file=end.resolve("ancestor-1-"+(damage.equals("ack")?"ack":"statement")+".gsr");Files.write(file,Files.readAllBytes(end.resolve("parent-"+(damage.equals("ack")?"ack":"statement")+".gsr")));}
                case "plan" -> Files.write(end.resolve("plan.json"),new byte[0]);
                case "missing-plan" -> Files.delete(end.resolve("plan.json"));
                case "extra" -> Files.write(end.resolve("ancestor-5-ack.gsr"),new byte[0]);
                case "link" -> Files.createLink(f.root.resolve("linked"),end.resolve("ancestor-1-ack.gsr"));
            }
            var before=V53ReplayFilesTest.files(f.node(1));assertThrows(Exception.class,()->f.open(1,e->{}));assertEquals(before,V53ReplayFilesTest.files(f.node(1)));
        }
        var f=new Fixture(temp.resolve("partial"),false);Path end=f.node(1).resolve("applied-end");
        try(var store=f.open(1,e->{if(e.equals("APPLY_ANCESTOR_1_ACK_PREFIX_WRITTEN"))throw new IOException("stop");})){assertThrows(IOException.class,()->f.application.apply(store));}
        Files.delete(end.resolve("ancestor-0-ack.gsr"));var before=V53ReplayFilesTest.files(f.node(1));
        try(var store=f.open(1,e->{})){assertThrows(IllegalArgumentException.class,()->f.application.apply(store));}assertEquals(before,V53ReplayFilesTest.files(f.node(1)));
    }
    @Test void freshProcessesRecoverRenewedAncestryAndCoveredCleanupTwice()throws Exception {
        Path retained=Path.of("target/v53-ancestor-checkpoint-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:PROCESS_CUTS) {
                Path root=retained.resolve(mode+"-"+point);var f=new Fixture(root,false);f.retain();Path node=f.node(1);V53JournalApplicationTest.copy(node,root.resolve("original"));
                V53JournalPublicationTest.child(root,"fault",point,mode,V53AncestorCheckpointWorker.class);V53JournalApplicationTest.copy(node,root.resolve("crash"));
                boolean covered=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR").value().get("generation").equals("a");
                String again=covered?"COVERED_VOTE_CANDIDATE_FORCED":"APPLY_ANCESTOR_1_ACK_PREFIX_WRITTEN";
                V53JournalPublicationTest.child(root,"recovery-fault",again,"halt",V53AncestorCheckpointWorker.class);V53JournalApplicationTest.copy(node,root.resolve("recovery-crash"));
                V53JournalPublicationTest.child(root,"resume","none","none",V53AncestorCheckpointWorker.class);V53JournalApplicationTest.copy(node,root.resolve("final"));
                V53JournalPublicationTest.preserved(node,V53ReplayFilesTest.files(root.resolve("original")));
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");rows.add(Map.of("mode",mode,"cut",point,"recoveryCut",again,"status","PASS","manifest",selector.value().get("digest")));
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",rows,"expectedCases",12L,"freshJvms",(long)rows.size()*3,"execution","private-ancestor-renewal-publication",
                    "historicalAuthority","conditional-fixture","currentObservations","actual-local-votes-and-ends","selectorPublication",true,"powerLoss",false),65536));
            System.out.println("v53AncestorCheckpointEvidence="+retained.toAbsolutePath());
        }
        assertEquals(12,rows.size());
    }
}
