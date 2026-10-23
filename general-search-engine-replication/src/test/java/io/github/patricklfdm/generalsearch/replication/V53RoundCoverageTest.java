package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Conditional proof construction; no fixture observation here is a storage force or READY. */
class V53RoundCoverageTest {
    static final class Round {
        final V53ContextFixture source;
        final Decoded promise,selected;
        MembershipCapsule capsule;
        byte[] coverage,ancestry=new byte[0];
        MembershipRoundCoverage.First first;
        final Set<Owned> observations=new HashSet<>();
        List<MembershipSelection.Bridge> bridges=List.of();
        Round() {
            source=new V53ContextFixture(3,"ADD");capsule=V53CheckpointPlanTest.initial(source);
            var frozen=new ArrayList<MembershipSelection.Source>();
            for(int n:List.of(1,2,3)) {
                var id=V53DeclarationsTest.node(n);var basis=source.record("BASIS",V53ContextFixture.map("root",source.rootHash,"voter","node-"+n,"basisId",new UUID(0,n).toString(),
                        "ballot",source.ballot(1),"cut",capsule.context.cut,"view",capsule.context.authority(),"capsule",capsule.packet.capsule().digest(),
                        "inventory",capsule.packet.inventoryDigest(),"accepted",null));
                frozen.add(MembershipSelection.Source.verify(capsule,basis,V53SelectionFixture.reference(basis),id,
                        Set.of(new Owned("node-"+n,id.storageId(),basis.digest(),cutDigest(capsule.context.cut)))));
            }
            selected=new MembershipSelection.Campaign(frozen.getFirst()).select(frozen,List.of()).selected();
            var value=new TreeMap<>(frozen.getFirst().basis.value());value.keySet().retainAll(Set.of("root","view","ballot","basisId"));
            promise=decode(encode("records","PROMISE",value),"records","PROMISE");
        }
        Round(V53PublishedGenerationTest.Fixture fixture) {
            source=fixture.f.capsule.source;capsule=fixture.f.capsule.verify();promise=fixture.promise;selected=fixture.selected;
        }
        void next(int at) {
            var required=first==null?List.of(capsule.terminal()):List.of(first.parent(),first.end(),capsule.terminal());
            var plan=V53CheckpointPlanTest.plan(capsule,source,at).renewAncestors(required,ancestry);var ends=V53CheckpointPlanTest.endorsements(plan);
            var complete=plan.complete(ends.acks(),ends.owned());var next=new ArrayList<MembershipSelection.Bridge>();
            var hidden=new TreeMap<Long,MembershipCapsule.Anchor>();for(var lower:required)if(complete.anchor(number(lower.cut().get("index")))==null)hidden.put(number(lower.cut().get("index")),lower);
            for(var lower:hidden.values()) {
                if(complete.context.view.equals(lower.cut().get("view"))) {
                    var statement=source.record("CHECKPOINT",Map.of("root",source.rootHash,"scope","RANGE","start",lower.cut(),"end",complete.context.cut,
                            "catalogBefore",lower.catalog(),"catalogAfter",complete.packet.capsule().value().get("catalog"),"applicationBefore",lower.application(),"applicationAfter",complete.context.catalog.get("application")));
                    var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
                    for(String voter:complete.context.voters().stream().sorted().toList()) {
                        var id=complete.context.identities.get(voter);var ack=source.record("CHECKPOINT_ACK",Map.of("root",source.rootHash,"cut",complete.context.cut,
                                "statement",statement.digest(),"voter",voter,"incarnation",id.storageId().toString()));
                        acks.add(ack);owned.add(new Owned(voter,id.storageId(),ack.digest(),cutDigest(complete.context.cut)));
                    }
                    next.add(new MembershipSelection.Bridge(statement,acks,owned));
                }else next.add(bridges.stream().filter(b->b.statement.value().get("start").equals(lower.cut())).findFirst().orElseThrow());
            }
            var candidate=plan.publication(ends.acks(),ends.owned(),next);byte[] nextAncestry=MembershipGenerationPlan.ancestry(next);
            if(coverage==null) {
                byte[] initial=MembershipSelectionCoverage.encodeCoverage(selected,plan.originalParent(),plan.originalCertificate(),plan.additionalParents());
                coverage=MembershipRoundCoverage.begin(candidate,initial,nextAncestry,promise,selected);capsule=candidate;
            }else {
                var result=MembershipRoundCoverage.advance(capsule,coverage,ancestry,candidate,nextAncestry,promise,selected,plan.originalCertificate(),source.images);
                capsule=result.capsule();coverage=result.coverage();
            }
            ancestry=nextAncestry;bridges=next;first=MembershipRoundCoverage.verify(coverage,capsule,promise,selected,ancestry);
            observations.addAll(V53CheckpointPlanTest.votes(source,source.steps.get(at)));observations.addAll(ends.owned());
            next.forEach(b->observations.addAll(b.owned));observations.removeIf(o->!capsule.packet.objectNames().contains(o.record()));
        }
    }
    @Test void oneHundredSameBallotSlotsRetainOnlyFirstAndCurrentProofs() {
        var r=new Round();int steadyObjects=0;long largestPacket=0,largestCoverage=0;
        for(int i=0;i<100;i++) {
            r.source.commit("BARRIER",null,()->{});r.next(i);
            assertEquals((long)i+1,r.capsule.context.cut.get("index"));assertEquals(0L,object(r.selected.value().get("cut")).get("index"));
            assertTrue(r.capsule.packet.objectNames().contains(r.source.steps.getFirst().get("certificate")));
            assertTrue(r.capsule.packet.objectNames().contains(r.source.steps.get(i).get("certificate")));
            if(i>1)assertFalse(r.capsule.packet.objectNames().contains(r.source.steps.get(i-1).get("certificate")));
            if(i==3)steadyObjects=r.capsule.packet.objectNames().size();if(i>3)assertEquals(steadyObjects,r.capsule.packet.objectNames().size());
            assertTrue(r.bridges.size()<=2);assertEquals(1,list(r.capsule.packet.capsule().value().get("items")).size());
            largestPacket=Math.max(largestPacket,r.capsule.packet.bytes().length);largestCoverage=Math.max(largestCoverage,r.coverage.length);
        }
        assertTrue(largestPacket<32*1024);assertTrue(largestCoverage<=MembershipRoundCoverage.MAXIMUM);
        System.out.println("v53RoundCoverage=PASS slots=100 maximumPacket="+largestPacket+" maximumCoverage="+largestCoverage+" conditional=true");
    }
    @Test void allProfilesRetainOriginalControlHistoryUntilIntentEndsTheRound() {
        for(Object[] p:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}}) {
            var r=new Round(new V53PublishedGenerationTest.Fixture((int)p[0],(String)p[1],0));
            for(int i=0;i<=5;i++)r.next(i);
            assertNotNull(r.capsule.context.view.get("operation"));
            assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.advance(r.capsule,r.coverage,r.ancestry,r.capsule,r.ancestry,
                    r.promise,r.selected,r.first.certificate(),r.source.images));
        }
        var joint=new V53PublishedGenerationTest.Fixture(3,"ADD",5);var plan=joint.plan();
        assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.begin(joint.capsule(),plan.files.get(MembershipSelectionCoverage.FILE),
                MembershipGenerationPlan.ancestry(joint.bridges),joint.promise,joint.selected));
    }
    @Test void alteredOriginalAndCurrentProofBindingsAndNoncanonicalBytesReject() {
        var r=new Round();for(int i=0;i<4;i++){r.source.commit("BARRIER",null,()->{});r.next(i);}
        for(String field:List.of("selection","certificate","schema","first-parent","first-end","first-certificate","parent","extra")) {
            var value=new TreeMap<>(object(parse(r.coverage,4096)));
            if(field.startsWith("first-")) {
                var first=new TreeMap<>(object(value.get("first")));String name=field.substring(6);
                first.put(name,name.equals("certificate")?value.get("certificate"):value.get("parent"));value.put("first",first);
            }else if(field.equals("parent"))value.put(field,object(value.get("first")).get("parent"));else value.put(field,"f".repeat(64));
            byte[] invalid=canonical(value,4096);
            assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(invalid,r.capsule,r.promise,r.selected,r.ancestry),field);
        }
        assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(r.coverage,r.capsule,r.promise,r.selected,new byte[0]));
        byte[] spaced=Arrays.copyOf(r.coverage,r.coverage.length+1);spaced[spaced.length-1]=' ';
        assertThrows(ReplicationException.class,()->MembershipRoundCoverage.verify(spaced,r.capsule,r.promise,r.selected,r.ancestry));
        assertThrows(IllegalArgumentException.class,()->MembershipSelectionCoverage.verify(r.coverage,r.capsule,r.promise,r.selected,r.ancestry),"current storage reader remains first-slot only");
    }
    @Test void checkpointEndorsementsCannotReplaceEitherOriginalPhasedProof() {
        var r=new Round();for(int i=0;i<4;i++){r.source.commit("BARRIER",null,()->{});r.next(i);}
        for(int slot:List.of(0,3))for(String phase:List.of("accept","proof")) {
            var observations=new HashSet<>(r.observations);observations.removeIf(o->o.record().equals(r.source.steps.get(slot).get(phase)));
            var prefix=MembershipCapsule.verify(r.source.root,r.capsule.packet,r.source.images,observations);
            assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(r.coverage,prefix,r.promise,r.selected,r.ancestry));
        }
        for(String phase:List.of("entry","accept","proof","certificate")) {
            var packet=r.capsule.packet;var objects=new TreeMap<String,byte[]>();for(String h:packet.objectNames())objects.put(h,packet.objectBytes(h));
            objects.remove(r.source.steps.getFirst().get(phase));var value=new TreeMap<>(packet.capsule().value());
            value.put("inventory",hash(MembershipSourcePacket.index(objects,packet.images())));
            var modified=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",value),"records","CAPSULE"),objects,packet.images()));
            var prefix=MembershipCapsule.verify(r.source.root,modified,r.source.images,r.observations);
            assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(r.coverage,prefix,r.promise,r.selected,r.ancestry));
        }
    }
    @Test void selectedCarriedChoiceHigherBallotAndDifferentRootCannotBeSubstituted() {
        var r=new Round();for(int i=0;i<3;i++){r.source.commit("BARRIER",null,()->{});r.next(i);}
        var wrongSelection=new TreeMap<>(r.selected.value());wrongSelection.put("nextEntry",r.source.steps.getLast().get("entry"));
        var selected=decode(encode("records","SELECTED",wrongSelection),"records","SELECTED");
        var bytes=new TreeMap<>(object(parse(r.coverage,4096)));bytes.put("selection",selected.digest());
        assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(canonical(bytes,4096),r.capsule,r.promise,selected,r.ancestry));
        wrongSelection=new TreeMap<>(r.selected.value());wrongSelection.put("ballot",r.source.ballot(2));
        var higher=decode(encode("records","SELECTED",wrongSelection),"records","SELECTED");
        var p=new TreeMap<>(r.promise.value());p.put("ballot",r.source.ballot(2));var promise=decode(encode("records","PROMISE",p),"records","PROMISE");
        bytes.put("selection",higher.digest());
        assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(canonical(bytes,4096),r.capsule,promise,higher,r.ancestry));
        var foreign=new V53ContextFixture(4,"ADD");var candidate=V53CheckpointPlanTest.initial(foreign);
        assertThrows(IllegalArgumentException.class,()->candidate.retainingCertificate(r.capsule,r.first.certificate(),r.first.parent().cut(),foreign.images));
    }
    @Test void coverageBoundsAndMalformedFieldsRejectWithoutPublishingAStorageFormat() {
        var r=new Round();r.source.commit("BARRIER",null,()->{});r.next(0);
        for(String field:List.of("schema","selection","first","parent","certificate")) {
            var v=new TreeMap<>(object(parse(r.coverage,4096)));v.put(field,null);
            assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(canonical(v,4096),r.capsule,r.promise,r.selected,r.ancestry),field);
        }
        byte[] oversized=new byte[MembershipRoundCoverage.MAXIMUM+1];Arrays.fill(oversized,(byte)' ');
        assertThrows(IllegalArgumentException.class,()->MembershipRoundCoverage.verify(oversized,r.capsule,r.promise,r.selected,r.ancestry));
        var result=new MembershipRoundCoverage.Publication(r.capsule,r.coverage);byte[] copy=result.coverage();copy[0]=0;
        assertArrayEquals(r.coverage,result.coverage());
    }
}
