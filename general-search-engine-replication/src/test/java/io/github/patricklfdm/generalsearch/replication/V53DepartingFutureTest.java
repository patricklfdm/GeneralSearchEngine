package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Representation and real end-file binding, with explicitly conditional original voting authority. */
class V53DepartingFutureTest {
    @TempDir Path temp;
    record Fixture(String profile,MembershipIdentity owner,MembershipCheckpointPlan plan,Map<String,byte[]> records) {
        String root(){return (String)plan.catalog.value().get("root");}
        byte[] frame(Map<String,byte[]> values){return MembershipFutureRetentionFiles.encode(root(),owner,1,V53ContextFixture.H,
                plan.originalParent(),List.of(new MembershipFutureRetentionFiles.Peer(V53DeclarationsTest.node(1),plan.originalParent())),values);}
        MembershipFutureRetentionFiles.State decode(Map<String,byte[]> values){return MembershipFutureRetentionFiles.decodeOwned(frame(values),root(),owner);}
    }
    static Fixture fixture(String profile,int ownerNumber,int at) {
        String[] p=profile.split("-");var selection=new V53SelectionFixture(Integer.parseInt(p[0]),p[1],at);
        var before=selection.capsule.verify();var plan=V53CheckpointPlanTest.plan(before,selection.capsule.source,at);var owner=V53DeclarationsTest.node(ownerNumber);
        var sources=before.context.voters().stream().sorted().map(node->selection.source(node,1,null,0)).toList();
        var proposer=sources.stream().filter(s->s.owner.nodeId().value().equals("node-1")).findFirst().orElseThrow();
        var chosen=new MembershipSelection.Campaign(proposer).select(sources,List.of());
        var promise=encode("records","PROMISE",Map.of("root",before.context.root,"view",before.context.authority(),
                "ballot",plan.originalCertificate().value().get("ballot"),"basisId",new UUID(6,ownerNumber).toString()));
        var records=new TreeMap<String,byte[]>();
        records.put("selector.gsr",V53DepartingEndTest.selector(plan,owner).bytes());records.put("promise.gsr",promise);
        records.put("selected.gsr",chosen.selected().bytes());
        var step=selection.capsule.source.steps.get(at);
        for(String name:List.of("entry","accept","proof","certificate"))records.put(name+".gsr",selection.capsule.source.inventory.get(step.get(name)));
        records.put("catalog.gsr",plan.catalog.bytes());records.put("statement.gsr",plan.statement.bytes());
        if(MembershipContext.nodes(object(object(plan.catalog.value().get("cut")).get("view")),"new").contains(owner.nodeId().value()))
            records.put("ack.gsr",V53CheckpointPlanTest.endorsements(plan,List.of(owner.nodeId().value())).acks().getFirst().bytes());
        return new Fixture(profile,owner,plan,records);
    }
    @Test void fiveExactDeparturesSurviveEncodingOriginalProofInheritanceAndActualEndReopen()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-departing-future/run-"+UUID.randomUUID()));
        System.out.println("v53DepartingFutureEvidence="+raw.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();
        for(String profile:V53DepartingEndTest.PROFILES) {
            var f=fixture(profile,Integer.parseInt(profile.substring(0,1)),6);var state=f.decode(f.records());
            assertTrue(state.pending());assertFalse(state.endorsed());assertEquals(Set.copyOf(MembershipFutureRetentionFiles.DEPARTURE_RECORDS),state.originals().keySet());
            assertThrows(NullPointerException.class,()->state.record("ack.gsr"));
            var proof=new MembershipFutureRetentionSet.Proof(f.frame(f.records()),state);var inheritor=V53DeclarationsTest.node(1);
            byte[] inherited=MembershipFutureRetentionSet.encode(f.root(),inheritor,List.of(proof));
            var copied=MembershipFutureRetentionSet.decode(inherited,f.root(),inheritor,h->h.equals(state.digest)?proof.bytes():null).getFirst();
            assertEquals(f.owner(),copied.state().owner);assertFalse(copied.state().endorsed());assertArrayEquals(proof.bytes(),copied.bytes());
            var resources=V53DepartingEndTest.resources();Path end=temp.resolve(profile);var selector=decode(f.records().get("selector.gsr"),"records","SELECTOR");
            try(var lease=V53DepartingEndTest.journal(resources)) {
                try(var store=new MembershipAppliedEndFiles(end,resources,MembershipResources.Unit.JOURNAL.bytes)) {
                    store.forceCompletion(f.plan(),selector,f.owner(),()->{},e->{});store.retainedTarget(state);
                }
                try(var reopened=new MembershipAppliedEndFiles(end,resources,MembershipResources.Unit.JOURNAL.bytes)){reopened.retainedTarget(copied.state());}
                Path dir=Files.createDirectory(raw.resolve(profile));var originals=Files.createDirectory(dir.resolve("records"));
                for(var row:f.records().entrySet())Files.write(originals.resolve(row.getKey()),row.getValue());
                Files.write(dir.resolve("future.gsft"),proof.bytes());Files.write(dir.resolve("inherited.gsfs"),inherited);
                Files.write(dir.resolve("parent.json"),canonical(MembershipRetentionIntent.anchor(f.plan().originalParent()),4096));
                V53JournalApplicationTest.copy(end,dir.resolve("end"));
                rows.add(Map.of("profile",profile,"node",f.owner().nodeId().value(),"status","PASS","future",state.digest));
            }assertEquals(0,resources.usage().leases());
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-departing-future-v1","authority","conditional-fixture","cases",rows),16384));
    }
    @Test void eligibleOwnerStillNeedsAckAndDepartedOwnerCannotSupplyOne() {
        var survivor=fixture("5-REPLACE",1,6);assertTrue(survivor.decode(survivor.records()).endorsed());
        var missing=new TreeMap<>(survivor.records());missing.remove("ack.gsr");
        assertEquals("future retention owner eligibility/completion kind",assertThrows(IllegalArgumentException.class,()->survivor.decode(missing)).getMessage());
        var departed=fixture("5-REPLACE",5,6);var fake=new TreeMap<>(departed.records());
        fake.put("ack.gsr",V53CheckpointPlanTest.endorsements(departed.plan(),List.of("node-5")).acks().getFirst().bytes());
        assertEquals("future retention owner eligibility/completion kind",assertThrows(IllegalArgumentException.class,()->departed.decode(fake)).getMessage());
    }
    @Test void nonvotingShapeCannotAuthorizeLearnersLaterStableSlotsOrAnotherIdentity() {
        for(var f:List.of(fixture("3-ADD",6,2),fixture("5-REPLACE",5,7)))
            assertEquals("applied-end exact departing FINAL owner",assertThrows(IllegalArgumentException.class,()->f.decode(f.records())).getMessage());
        var f=fixture("5-REPLACE",5,6);var foreign=new MembershipIdentity(f.owner().nodeId(),new UUID(9,9),f.owner().endpoint());
        byte[] bytes=MembershipFutureRetentionFiles.encode(f.root(),foreign,1,V53ContextFixture.H,f.plan().originalParent(),
                List.of(new MembershipFutureRetentionFiles.Peer(V53DeclarationsTest.node(1),f.plan().originalParent())),f.records());
        assertEquals("applied-end permanent identity",assertThrows(IllegalArgumentException.class,()->MembershipFutureRetentionFiles.decodeOwned(bytes,f.root(),foreign)).getMessage());
    }
    @Test void omittedChangedOrRelabelledOriginalsDoNotBecomeValidDepartureProofs() {
        var f=fixture("4-REMOVE",4,6);
        for(String name:MembershipFutureRetentionFiles.DEPARTURE_RECORDS) {
            var missing=new TreeMap<>(f.records());missing.remove(name);assertThrows(IllegalArgumentException.class,()->f.decode(missing),name);
        }
        for(String field:List.of("catalogBefore","applicationBefore")) {
            var values=new TreeMap<>(f.records());var statement=new TreeMap<>(decode(values.get("statement.gsr"),"records","CHECKPOINT").value());
            statement.put(field,V53ContextFixture.H);values.put("statement.gsr",encode("records","CHECKPOINT",statement));
            assertEquals("applied-end departing exact statement",assertThrows(IllegalArgumentException.class,()->f.decode(values)).getMessage());
        }
        var bytes=f.frame(f.records());bytes[bytes.length-1]^=1;
        assertThrows(IllegalArgumentException.class,()->MembershipFutureRetentionFiles.decodeOwned(bytes,f.root(),f.owner()));
        assertThrows(IllegalArgumentException.class,()->MembershipFutureRetentionFiles.decodeOwned(f.frame(f.records()),f.root(),V53DeclarationsTest.node(1)));
    }
    @Test void originalEndRequiresSameKindExactFilesAndExactImage()throws Exception {
        var f=fixture("4-REMOVE",4,6);var resources=V53DepartingEndTest.resources();Path path=temp.resolve("end");
        try(var lease=V53DepartingEndTest.journal(resources)) {
            try(var end=new MembershipAppliedEndFiles(path,resources,MembershipResources.Unit.JOURNAL.bytes)) {
                end.forceCompletion(f.plan(),decode(f.records().get("selector.gsr"),"records","SELECTOR"),f.owner(),()->{},e->{});
                var survivor=fixture("4-REMOVE",1,6);
                assertThrows(IllegalArgumentException.class,()->end.retainedTarget(survivor.decode(survivor.records())));
            }
            Files.write(path.resolve("ack.gsr"),V53CheckpointPlanTest.endorsements(f.plan(),List.of("node-4")).acks().getFirst().bytes());
            try(var end=new MembershipAppliedEndFiles(path,resources,MembershipResources.Unit.JOURNAL.bytes)) {
                assertEquals("future retention completion kind changed",assertThrows(IllegalArgumentException.class,()->end.retainedTarget(f.decode(f.records()))).getMessage());
            }
            Files.delete(path.resolve("ack.gsr"));Files.write(path.resolve("application.image"),new byte[]{1});
            try(var end=new MembershipAppliedEndFiles(path,resources,MembershipResources.Unit.JOURNAL.bytes)) {
                assertThrows(IllegalArgumentException.class,()->end.retainedTarget(f.decode(f.records())));
            }
        }assertEquals(0,resources.usage().leases());
    }
}
