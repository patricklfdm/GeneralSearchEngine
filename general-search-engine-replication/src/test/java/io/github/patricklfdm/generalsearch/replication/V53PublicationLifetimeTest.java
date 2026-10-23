package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.io.IOException;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Repeated real votes/publications with explicit, authorized source/floor maintenance. */
class V53PublicationLifetimeTest {
    @TempDir Path temp;
    static final List<Integer> NODES=List.of(1,2,3);
    record Installation(Map<String,Object> ballot,List<MembershipSelection.Source> sources,Map<Integer,String> obsolete,Map<String,byte[]> images,MembershipCapsule parent) {}
    static final class Fixture {
        final Path root;
        final V53JournalPublicationTest.Fixture initial;
        final MembershipResources resources=new MembershipResources(512*MembershipResources.MIB);
        final Set<Owned> observations=new HashSet<>();
        final List<Map<String,Object>> rows=new ArrayList<>();
        List<MembershipSelection.Bridge> bridges=List.of();
        long maximumImages,maximumMetadata,maximumStaging;
        Fixture(Path root)throws Exception {this(root,false);}
        Fixture(Path root,boolean retainFirst)throws Exception {
            this.root=root;initial=new V53JournalPublicationTest.Fixture(root,0);observations.addAll(initial.observations);
            if(retainFirst)for(int n:NODES) {
                Path original=root.resolve("originals/slot-1/node-"+n);Files.createDirectories(original.getParent());V53JournalApplicationTest.copy(node(n),original);
            }
            for(int n:NODES)try(var store=open(n)){initial.publish(store,n);}
            maintain(null);sample(0);
        }
        Path node(int n){return initial.node(n);}
        MembershipGrantJournal open(int n)throws Exception {return open(n,e->{});}
        MembershipGrantJournal open(int n,MembershipBallotAllocator.Cut cut)throws Exception {
            assertEquals(0,resources.usage().leases());
            return MembershipGrantJournal.openApplying(node(n),initial.application.f.f.f.root(),V53DeclarationsTest.node(n),resources,
                    (r,p,i)->MembershipCapsule.verify(r,p,i,observations),e->{
                        var used=resources.usage();maximumImages=Math.max(maximumImages,used.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
                        maximumMetadata=Math.max(maximumMetadata,used.metadata());maximumStaging=Math.max(maximumStaging,used.staging());
                        cut.at(e);
                    });
        }
        void maintain(Map<Integer,String> obsolete)throws Exception {
            var copies=new ArrayList<MembershipFloor.Copy>();for(int n:NODES)try(var store=open(n)){copies.add(store.floorCopyCurrent());}
            for(int n:NODES)try(var store=open(n)) {
                // Keep exact local and one other live copy; no duplicate physical-image aliasing.
                var pair=copies.stream().filter(c->c.owner.nodeId().value().equals("node-"+n) || c.owner.nodeId().value().equals("node-"+(n==1?2:1))).toList();
                store.establishFloor(pair);store.retireInactive();
                if(obsolete!=null)store.retireSource(obsolete.get(n));
                store.releaseFloor();store.rotateJournal();
            }
        }
        Installation prepare(int cycle)throws Exception {
            var ballot=initial.application.f.f.f.fixture.source.ballot(20+cycle);var sources=new ArrayList<MembershipSelection.Source>();
            var obsolete=new TreeMap<Integer,String>();Map<String,byte[]> images=new TreeMap<>();MembershipCapsule parent=null;
            for(int n:NODES)try(var store=open(n)) {
                obsolete.put(n,(String)store.originalBasis().orElseThrow().value().get("basisId"));store.prepareCurrent(ballot);sources.add(store.originalSource());
                var copy=store.floorCopyCurrent();parent=copy.capsule;
                for(String h:copy.capsule.packet.images().keySet())images.put(h,copy.fileBytes(h+".image"));
            }
            for(int n:NODES)try(var store=open(n)){store.selectCurrent(sources,List.of());}
            return new Installation(ballot,sources,obsolete,images,Objects.requireNonNull(parent));
        }
        void cycle(int cycle)throws Exception {
            var setup=prepare(cycle);var ballot=setup.ballot();
            for(int n:NODES)try(var store=open(n)){store.installCurrent(setup.sources(),List.of(),bridges,setup.images());}
            maintain(setup.obsolete());
            var context=setup.parent().context;
            var entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),"index",number(context.cut.get("index"))+1,
                    "previous",context.cut.get("entry"),"origin",ballot,"kind","BARRIER","payload",hash(new byte[0]))),"records","ENTRY");
            var accepts=new HashSet<Owned>();Decoded accept=null;
            for(int n:NODES)try(var store=open(n)) {
                accepts.add(store.acceptCurrent(entry,new byte[0]));accept=MembershipPendingAccept.decode(Files.readAllBytes(node(n).resolve("pending.accept"))).accept();
            }
            var proofFields=new TreeMap<>(Objects.requireNonNull(accept).value());proofFields.put("accepts",witnesses(context.root,"ACCEPT",accept,accepts));
            var proof=decode(encode("records","PROOF",proofFields),"records","PROOF");var proofs=new HashSet<Owned>();
            for(int n:NODES)try(var store=open(n)){proofs.add(store.proveCurrent(proof,accepts));}
            var certificateFields=new TreeMap<>(proof.value());certificateFields.put("proofs",witnesses(context.root,"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",certificateFields),"records","CERTIFICATE");
            var phased=new HashSet<>(accepts);phased.addAll(proofs);observations.addAll(phased);
            for(int n:NODES)try(var store=open(n)){store.certifyCurrent(certificate,phased);}
            var applied=new TreeMap<Integer,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var checkpoints=new HashSet<Owned>();
            var parentAcks=new ArrayList<Decoded>();var parentOwned=new HashSet<Owned>();Decoded statement=null;
            for(int n:NODES)try(var store=open(n)) {
                var result=store.applyCurrent(initial.application.app.configuration(),initial.application.app.storage(),phased);applied.put(n,result);
                assertTrue(result.plan().additionalParents().isEmpty(),"retired sources must not accumulate renewal obligations");
                acks.add(result.endorsement().acknowledgement());checkpoints.add(result.endorsement().owned());
                var lower=result.endorsement().parent().orElseThrow();statement=lower.statement();parentAcks.add(lower.acknowledgement());parentOwned.add(lower.owned());
            }
            observations.addAll(checkpoints);observations.addAll(parentOwned);
            bridges=List.of(new MembershipSelection.Bridge(Objects.requireNonNull(statement),parentAcks,parentOwned));
            for(int n:NODES)try(var store=open(n)) {
                store.publishCurrent(applied.get(n),acks,checkpoints,bridges);
                assertTrue(store.currentCertificate().isEmpty());assertTrue(store.currentOwnedTail().isEmpty());
            }
            maintain(null);sample(cycle);
        }
        void sample(int cycle)throws Exception {
            for(int n:NODES)try(var store=open(n)) {
                var copy=store.floorCopyCurrent();var usage=resources.usage();
                assertEquals((long)cycle+1,copy.capsule.context.cut.get("index"));assertEquals(42L,copy.capsule.context.catalog.get("applicationSequence"));
                assertEquals(1,usage.counts().get(MembershipResources.Unit.GENERATION));
                assertEquals(1,usage.counts().get(MembershipResources.Unit.SOURCE));assertEquals(2,usage.counts().get(MembershipResources.Unit.APPLICATION));
                try(var files=Files.walk(node(n))){assertEquals(2,files.filter(p->p.toString().endsWith(".image")).count());}
                try(var files=Files.list(node(n).resolve("sources"))){assertEquals(1,files.count());}
                assertTrue(store.governingFloor().isEmpty());assertFalse(Files.exists(node(n).resolve("applied-end")));
                if(cycle>0)assertArrayEquals(MembershipGenerationPlan.ancestry(bridges),copy.fileBytes("ancestry.gsr"));
                byte[] selectedBytes=copy.fileBytes("selected-sources.gsr");var selected=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
                assertEquals(List.of((long)cycle,(long)cycle,(long)cycle),MembershipSelectedSources.cuts(selectedBytes,selected).stream().map(v->number(v.get("index"))).toList());
                var inventory=V53ReplayFilesTest.files(node(n));
                Path snapshot=root.resolve("snapshots/round-"+cycle+"/node-"+n);Files.createDirectories(snapshot.getParent());V53JournalApplicationTest.copy(node(n),snapshot);
                rows.add(Map.of("cycle",(long)cycle,"node","node-"+n,"cut",copy.capsule.context.cut.get("index"),"manifest",copy.generation.digest(),
                        "metadata",usage.metadata(),"staging",usage.staging(),"files",(long)inventory.size(),"journalBytes",Files.size(node(n).resolve("grants.gsr")),
                        "inventorySha256",hash(canonical(inventory.entrySet().stream().map(e->Map.of("path",e.getKey(),"sha256",e.getValue())).toList(),65536))));
            }
            assertEquals(0,resources.usage().leases());System.out.println("v53PublicationLifetimeRound="+cycle+" PASS");
        }
    }
    @Test void supplementalAncestryIsBoundedAuthenticatedAndCannotChangeTheSelectedDecision()throws Exception {
        var f=new Fixture(temp);f.cycle(1);var setup=f.prepare(2);var bridge=f.bridges.getFirst();Path node=f.node(1);
        var before=V53ReplayFilesTest.files(node);var events=new ArrayList<String>();
        try(var store=f.open(1,events::add)) {
            events.clear();assertThrows(IllegalArgumentException.class,()->store.selectCurrent(setup.sources(),f.bridges));
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),setup.images()));
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),List.of(bridge,bridge),setup.images()));
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),Collections.nCopies(7,bridge),setup.images()));
            var unowned=new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements,Set.of());
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),List.of(unowned),setup.images()));
            var wrong=new TreeMap<>(bridge.statement.value());wrong.put("catalogBefore","f".repeat(64));
            var foreign=new MembershipSelection.Bridge(decode(encode("records","CHECKPOINT",wrong),"records","CHECKPOINT"),bridge.acknowledgements,bridge.owned);
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),List.of(foreign),setup.images()));
            f.observations.removeAll(bridge.owned);
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()),"caller observations cannot replace the retained verifier");
            f.observations.addAll(bridge.owned);
            assertTrue(events.isEmpty(),events.toString());assertEquals(before,V53ReplayFilesTest.files(node));
            store.observeCurrent(f.initial.application.f.f.f.fixture.source.ballot(23));
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()));
            assertEquals(before,V53ReplayFilesTest.files(node));
        }
        // A local volatile observation is not a durable grant. The exact original install resumes after reopen.
        try(var store=f.open(1)){store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images());}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void supplementalAncestrySurvivesInterruptedInstallButDifferentRepresentationCannotReplaceIt()throws Exception {
        var f=new Fixture(temp);f.cycle(1);var setup=f.prepare(2);Path node=f.node(1);
        try(var store=f.open(1,e->{if(e.equals("INSTALL_MANIFEST_FORCED"))throw new IOException("cut");})) {
            assertThrows(IOException.class,()->store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()));
        }
        var before=V53ReplayFilesTest.files(node);var bridge=f.bridges.getFirst();var shortened=new MembershipSelection.Bridge(bridge.statement,bridge.acknowledgements.subList(0,2),bridge.owned);
        try(var store=f.open(1)) {
            assertThrows(IllegalArgumentException.class,()->store.installCurrent(setup.sources(),List.of(),List.of(shortened),setup.images()));
        }
        assertEquals(before,V53ReplayFilesTest.files(node));
        try(var store=f.open(1,e->{if(e.equals("INSTALL_GENERATION_FORCED"))throw new IOException("again");})) {
            assertThrows(IOException.class,()->store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()));
        }
        try(var store=f.open(1)) {
            var manifest=store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images());
            assertArrayEquals(manifest.bytes(),store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()).bytes());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void completedInstallationRemainsExactAfterItsOldSourceIsSafelyRetired()throws Exception {
        var f=new Fixture(temp);f.cycle(1);var setup=f.prepare(2);var expected=new TreeMap<Integer,Decoded>();
        for(int n:NODES)try(var store=f.open(n)){expected.put(n,store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()));}
        f.maintain(setup.obsolete());
        for(int n:NODES) {
            var before=V53ReplayFilesTest.files(f.node(n));var events=new ArrayList<String>();
            try(var store=f.open(n,events::add)) {
                events.clear();assertArrayEquals(expected.get(n).bytes(),store.installCurrent(setup.sources(),List.of(),f.bridges,setup.images()).bytes());
                assertTrue(events.isEmpty(),"exact completed receipt must not rewrite a generation");
            }
            assertEquals(before,V53ReplayFilesTest.files(f.node(n)));
        }
    }
    static List<Map<String,Object>> witnesses(String root,String phase,Decoded record,Set<Owned> observations) {
        return observations.stream().sorted(Comparator.comparing(Owned::voter)).map(o->{
            String receipt=hash(canonical(Map.of("root",root,"voter",o.voter(),"incarnation",o.storage().toString(),"phase",phase,"record",record.digest()),2048));
            assertEquals(record.digest(),o.record());return Map.<String,Object>of("voter",o.voter(),"incarnation",o.storage().toString(),"receipt",receipt);
        }).toList();
    }
    @Test void twelveFreshBallotsPublishAndReclaimWithoutAccumulatingSourceImagesOrAncestry()throws Exception {
        Path root=Path.of("target/v53-publication-lifetime").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);Fixture f=null;
        try {
            f=new Fixture(root);for(int cycle=1;cycle<=12;cycle++)f.cycle(cycle);
            assertTrue(f.maximumImages<=7);assertTrue(f.maximumMetadata<=MembershipResources.METADATA_LIMIT);assertTrue(f.maximumStaging<=512*MembershipResources.MIB);
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("execution","private-repeated-publication-maintenance","expectedRounds",13L,"rows",f==null?List.of():f.rows,
                    "peakImages",f==null?0L:f.maximumImages,"peakMetadata",f==null?0L:f.maximumMetadata,"peakStaging",f==null?0L:f.maximumStaging,
                    "sameBallotContinuation",false,"historicalBootstrap","conditional-fixture","freshProcesses",false),65536));
            System.out.println("v53PublicationLifetimeEvidence="+root.toAbsolutePath());
        }
    }
}
