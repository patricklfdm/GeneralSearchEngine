package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.io.IOException;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual local owners; original bootstrap alone is conditional. No public READY is asserted. */
class V53RoundStorageTest {
    @TempDir Path temp;
    static final List<Integer> NODES=List.of(1,2,3);
    record Publication(Map<Integer,MembershipGrantJournal.Applied> applied,List<Decoded> acks,Set<Owned> checkpoints,List<MembershipSelection.Bridge> bridges) {
        Decoded publish(MembershipGrantJournal store,int n)throws IOException {return store.publishCurrent(applied.get(n),acks,checkpoints,bridges);}
    }
    static final class Fixture {
        final V53PublicationLifetimeTest.Fixture f;
        final Map<Integer,byte[]> bases=new TreeMap<>(),selections=new TreeMap<>(),sources=new TreeMap<>();
        final Map<String,Object> ballot;
        Fixture(Path root)throws Exception {
            f=new V53PublicationLifetimeTest.Fixture(root,true);
            try(var store=f.open(1)){ballot=object(store.promised().orElseThrow().value().get("ballot"));}
            for(int n:NODES)try(var store=f.open(n)) {
                bases.put(n,store.originalBasis().orElseThrow().bytes());selections.put(n,store.originalSelection().orElseThrow().bytes());
                sources.put(n,store.originalSource().capsule.packet.bytes());
            }
        }
        Decoded entry(String kind,byte[] payload)throws Exception {
            try(var store=f.open(1)) {
                var c=store.floorCopyCurrent().capsule.context;
                return decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",number(c.cut.get("index"))+1,
                        "previous",c.cut.get("entry"),"origin",ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
            }
        }
        Publication apply(Decoded entry,byte[] payload)throws Exception {
            var accepts=new HashSet<Owned>();Decoded accept=null;
            for(int n:NODES)try(var store=f.open(n)) {
                accepts.add(store.acceptCurrent(entry,payload));accept=MembershipPendingAccept.decode(Files.readAllBytes(f.node(n).resolve("pending.accept"))).accept();
            }
            String root=f.initial.application.f.f.f.root().manifestDigest();
            var proofFields=new TreeMap<>(Objects.requireNonNull(accept).value());proofFields.put("accepts",V53PublicationLifetimeTest.witnesses(root,"ACCEPT",accept,accepts));
            var proof=decode(encode("records","PROOF",proofFields),"records","PROOF");var proofs=new HashSet<Owned>();
            for(int n:NODES)try(var store=f.open(n)){proofs.add(store.proveCurrent(proof,accepts));}
            var fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(root,"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var phased=new HashSet<>(accepts);phased.addAll(proofs);f.observations.addAll(phased);
            for(int n:NODES)try(var store=f.open(n)){store.certifyCurrent(certificate,phased);}
            var applied=new TreeMap<Integer,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
            var lower=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
            for(int n:NODES)try(var store=f.open(n)) {
                var result=store.applyCurrent(f.initial.application.app.configuration(),f.initial.application.app.storage(),phased);applied.put(n,result);
                acks.add(result.endorsement().acknowledgement());owned.add(result.endorsement().owned());
                var ends=new ArrayList<>(result.endorsement().ancestors());result.endorsement().parent().ifPresent(ends::add);
                for(var end:ends)lower.computeIfAbsent(number(object(end.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(end);
            }
            f.observations.addAll(owned);var bridges=new ArrayList<MembershipSelection.Bridge>();
            for(var group:lower.values()) {
                var observations=group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::owned).collect(java.util.stream.Collectors.toSet());
                f.observations.addAll(observations);bridges.add(new MembershipSelection.Bridge(group.getFirst().statement(),group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),observations));
            }
            for(int n:NODES) {
                Path original=f.root.resolve("originals/slot-"+entry.value().get("index")+"/node-"+n);
                Files.createDirectories(original.getParent());V53JournalApplicationTest.copy(f.node(n),original);
            }
            return new Publication(applied,acks,owned,bridges);
        }
        void finish(Publication publication)throws Exception {
            for(int n:NODES)try(var store=f.open(n)) {
                var result=publication.publish(store,n);assertArrayEquals(result.bytes(),publication.publish(store,n).bytes());
                assertTrue(store.currentCertificate().isEmpty());assertTrue(store.currentOwnedTail().isEmpty());
            }
            f.maintain(null);
            for(int n:NODES)try(var store=f.open(n)) {
                var before=V53ReplayFilesTest.files(f.node(n));publication.publish(store,n);
                assertArrayEquals(bases.get(n),store.prepareCurrent(ballot).bytes());assertArrayEquals(selections.get(n),store.originalSelection().orElseThrow().bytes());
                assertArrayEquals(sources.get(n),store.originalSource().capsule.packet.bytes());assertEquals(before,V53ReplayFilesTest.files(f.node(n)));
            }
        }
    }
    @Test void sameOriginalRoundPublishesRealWritesAndBarriersWithoutGrowingRetainedHistory()throws Exception {
        Path root=Path.of("target/v53-round-storage").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);var f=new Fixture(root);
        int maximumObjects=0;long sequence=42;
        for(int slot=2;slot<=13;slot++) {
            byte[] payload=new byte[0];String kind="BARRIER";
            if(slot%2==1)try(var encoder=f.f.initial.application.app.encoder()) {
                kind="DATA";payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(100+slot,"round-"+slot))));sequence++;
            }
            var publication=f.apply(f.entry(kind,payload),payload);f.finish(publication);
            for(int n:NODES)try(var store=f.f.open(n)) {
                var copy=store.floorCopyCurrent();assertEquals((long)slot,copy.capsule.context.cut.get("index"));assertEquals(sequence,copy.capsule.context.catalog.get("applicationSequence"));
                assertTrue(publication.bridges().size()<=3);maximumObjects=Math.max(maximumObjects,copy.capsule.packet.objectNames().size());
                assertTrue(copy.capsule.packet.objectNames().size()<=25);assertEquals(2,f.f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                Path snapshot=root.resolve("snapshots/slot-"+slot+"/node-"+n);Files.createDirectories(snapshot.getParent());V53JournalApplicationTest.copy(f.f.node(n),snapshot);
            }
            System.out.println("v53RoundStorageSlot="+slot+" PASS");
        }
        V53JournalApplicationTest.copy(f.f.node(1),root.resolve("before-fresh-prepare"));
        try(var store=f.f.open(1)) {
            var advanced=store.prepareCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(21));assertEquals(13L,object(advanced.value().get("cut")).get("index"));assertNull(advanced.value().get("accepted"));
        }
        assertEquals(0,f.f.resources.usage().leases());
        Files.write(root.resolve("receipt.json"),canonical(Map.of("status","PASS","slots",13L,"sameBallot",true,"applicationSequence",sequence,"maximumObjects",(long)maximumObjects,"freshProcesses",false,"publicReady",false),4096));
        System.out.println("v53RoundStorageEvidence="+root.toAbsolutePath());
    }
    @Test void originalPhasedProofAndExactNextSlotRemainMandatoryAndHigherBallotFences()throws Exception {
        var f=new Fixture(temp);f.finish(f.apply(f.entry("BARRIER",new byte[0]),new byte[0]));
        var entry=f.entry("BARRIER",new byte[0]);Path node=f.f.node(1);var before=V53ReplayFilesTest.files(node);
        try(var store=f.f.open(1)) {
            for(String field:List.of("index","previous","origin")) {
                var changed=new TreeMap<>(entry.value());changed.put(field,field.equals("index")?99L:field.equals("previous")?"f".repeat(64):f.f.initial.application.f.f.f.fixture.source.ballot(19));
                var wrong=decode(encode("records","ENTRY",changed),"records","ENTRY");assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(wrong,new byte[0]));
            }
            store.observeCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(21));assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(entry,new byte[0]));
        }
        assertEquals(before,V53ReplayFilesTest.files(node));
        var first=f.f.initial.application.cohort.owned();f.f.observations.removeAll(first);
        assertThrows(IllegalArgumentException.class,()->f.f.open(1));f.f.observations.addAll(first);assertEquals(before,V53ReplayFilesTest.files(node));
        try(var store=f.f.open(1)) {
            var owned=store.acceptCurrent(entry,new byte[0]);assertEquals(owned,store.acceptCurrent(entry,new byte[0]));
            byte[] payload;try(var encoder=f.f.initial.application.app.encoder()) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(99,"conflict"))));
            }
            var changed=new TreeMap<>(entry.value());changed.put("kind","DATA");changed.put("payload",hash(payload));
            var conflict=assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(decode(encode("records","ENTRY",changed),"records","ENTRY"),payload));
            assertEquals("pending ACCEPT conflict or obsolete ballot",conflict.getMessage());
            var fresh=store.prepareCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(21));assertEquals(2L,object(fresh.value().get("cut")).get("index"));assertEquals(owned.record(),fresh.value().get("accepted"));
        }
    }
    @Test void subsequentPublicationAndCoveredRetirementSurviveRepeatedInterruptedRecovery()throws Exception {
        for(String cut:List.of("INSTALL_MANIFEST_FORCED","PUBLICATION_SELECTOR_FORCED","COVERED_END_FILE_DELETED","COVERED_VOTE_PREFIX_WRITTEN")) {
            var f=new Fixture(temp.resolve(cut));f.finish(f.apply(f.entry("BARRIER",new byte[0]),new byte[0]));
            var publication=f.apply(f.entry("BARRIER",new byte[0]),new byte[0]);
            assertThrows(IOException.class,()->{try(var store=f.f.open(1,e->{if(e.equals(cut))throw new IOException("cut");})){publication.publish(store,1);}});
            String again=cut.equals("INSTALL_MANIFEST_FORCED")?"INSTALL_GENERATION_FORCED":"COVERED_VOTE_CANDIDATE_FORCED";
            assertThrows(IOException.class,()->{try(var store=f.f.open(1,e->{if(e.equals(again))throw new IOException("again");})){publication.publish(store,1);}});
            f.finish(publication);
            try(var store=f.f.open(1)){assertEquals(3L,store.floorCopyCurrent().capsule.context.cut.get("index"));}
        }
    }
}
