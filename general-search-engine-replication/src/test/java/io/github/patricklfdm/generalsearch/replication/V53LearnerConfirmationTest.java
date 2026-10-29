package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional byte/projection checks. These manufactured wire fixtures never
 * enter a native journal; the TCP native test establishes actual receipt. */
class V53LearnerConfirmationTest {
    static MembershipLearnerConfirmation fixture(MembershipLearnerRetentionPlan plan,MembershipCapsule.Anchor endpoint) {
        var value=object(parse(plan.bytes(),16384));var request=object(value.get("request"));var learner=MembershipContext.identity(object(value.get("learner")));
        var q=decode(encode("wire","LEARNER_HEAD_QUERY",Map.of("root",request.get("root"),"view",request.get("expected"),
                "sender",MembershipPeerRetentionPlan.identity(V53DeclarationsTest.node(1)),"recipient",value.get("learner"),
                "ballot",MembershipLearnerDiscovery.correlation(learner),"trace",UUID.randomUUID().toString(),"sequence",1L,
                "payload",Map.of("request",request))),"wire","LEARNER_HEAD_QUERY");
        var a=new TreeMap<>(q.value());a.put("sender",q.value().get("recipient"));a.put("recipient",q.value().get("sender"));
        a.put("payload",Map.of("request",hash(canonical(request,8192)),"endpoint",MembershipRetentionIntent.anchor(endpoint)));
        return MembershipLearnerConfirmation.received(q,decode(encode("wire","LEARNER_HEAD_ACK",a),"wire","LEARNER_HEAD_ACK"));
    }
    @Test void confirmedPointIsExplicitAndConservativeDecodedMergeStillRefusesThreePoints() {
        var history=new V53CapsuleFixture(3,"ADD",4);var at3=V53CapsuleFixture.fromHistory(history.source,3).verify();
        var plan=V53LearnerRetentionPlanTest.offered(3,"ADD",3);var proof=fixture(plan,at3.terminal());
        var confirmed=plan.confirm(at3,new byte[0],proof);
        assertFalse(Arrays.equals(plan.bytes(),confirmed.bytes()));assertTrue(object(parse(confirmed.bytes(),16384)).containsKey("confirmation"));
        assertArrayEquals(confirmed.bytes(),MembershipLearnerRetentionPlan.decode(confirmed.bytes()).bytes());
        assertArrayEquals(confirmed.bytes(),confirmed.confirm(at3,new byte[0],fixture(plan,at3.terminal())).bytes(),"new trace at same head is idempotent");
        var bridge=V53LearnerProgressNetworkTest.bridge(history,3,4);var at4=history.verify().retainingVerifiedAncestry(List.of(bridge));
        byte[] ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));var next=confirmed.offer(at4,ancestry,V53DeclarationsTest.node(6));
        assertEquals(List.of(3L,4L),next.recorded().stream().map(a->number(a.cut().get("index"))).toList());
        assertArrayEquals(next.bytes(),next.confirm(at4,ancestry,proof).bytes(),"confirmation of 3 keeps uncertain 4");
        var stale=V53LearnerRetentionPlanTest.offered(3,"ADD",2);
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(at4.context.root,List.of(stale,next)),
                "arbitrary decoded proof cannot discharge a selected source");
        var advance=next.confirm(at4,ancestry,fixture(next,at4.terminal()));
        assertEquals(List.of(at4.terminal()),advance.recorded());
        assertArrayEquals(advance.bytes(),advance.confirm(at4,ancestry,proof).bytes(),"old confirmed reply cannot regress progress");
    }
    @Test void recomputedWireChecksumsCannotHideCrossBindingOrUnretainedHead() {
        var current=V53LearnerRetentionPlanTest.capsule(3,"ADD",3);var plan=V53LearnerRetentionPlanTest.offered(3,"ADD",3);
        var value=object(parse(plan.confirm(current,new byte[0],fixture(plan,current.terminal())).bytes(),16384));
        for(String change:List.of("request","trace","view","recipient","endpoint","base64","field")) {
            var changed=object(V53ContextFixture.mutable(value));var proof=object(changed.get("confirmation"));
            var ack=decode(Base64.getDecoder().decode((String)proof.get("ack")),"wire","LEARNER_HEAD_ACK");
            var a=object(V53ContextFixture.mutable(ack.value()));
            switch(change) {
                case "request"->object(a.get("payload")).put("request","ab".repeat(32));
                case "trace"->a.put("trace",UUID.randomUUID().toString());
                case "view"->a.put("view","ab".repeat(32));
                case "recipient"->object(a.get("recipient")).put("storage",UUID.randomUUID().toString());
                case "endpoint"->object(object(a.get("payload")).get("endpoint")).put("catalog","ab".repeat(32));
                case "field"->proof.put("trusted",true);
                default->{}
            }
            proof.put("ack",Base64.getEncoder().encodeToString(encode("wire","LEARNER_HEAD_ACK",a))+(change.equals("base64")?"\n":""));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.decode(canonical(changed,16384)),change);
        }
    }
    @Test void localDischargeKeepsBoundedPhysicalRenewalsUntilSelectedReconciliation() {
        var history=new V53CapsuleFixture(3,"ADD",4);
        var at3=V53CapsuleFixture.fromHistory(history.source,3).verify();
        var bridge=V53LearnerProgressNetworkTest.bridge(history,2,3);
        at3=at3.retainingVerifiedAncestry(List.of(bridge));byte[] ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));
        var plan=V53LearnerRetentionPlanTest.offered(3,"ADD",2).offer(at3,ancestry,V53DeclarationsTest.node(6));
        var confirmed=plan.confirm(at3,ancestry,fixture(plan,at3.terminal()));
        assertEquals(List.of(3L),confirmed.recorded().stream().map(a->number(a.cut().get("index"))).toList());
        assertEquals(List.of(2L,3L),confirmed.required(at3,ancestry).stream().map(a->number(a.cut().get("index"))).toList());
        assertArrayEquals(confirmed.bytes(),MembershipLearnerRetentionPlan.decode(confirmed.bytes()).bytes());
        assertEquals(List.of(2L,3L),MembershipLearnerRetentionPlan.mergeRecorded(at3.context.root,List.of(confirmed))
                .recorded().stream().map(a->number(a.cut().get("index"))).toList(),"plain decode cannot discharge physical debt");
        var value=object(V53ContextFixture.mutable(parse(confirmed.bytes(),16384)));
        var lower=V53CapsuleFixture.fromHistory(history.source,1).verify().terminal();
        value.put("renewals",List.of(MembershipRetentionIntent.anchor(lower),list(value.get("renewals")).getFirst()));
        var full=MembershipLearnerRetentionPlan.decode(canonical(value,16384));
        var bridges=List.of(V53LearnerProgressNetworkTest.bridge(history,1,4),V53LearnerProgressNetworkTest.bridge(history,2,4),
                V53LearnerProgressNetworkTest.bridge(history,3,4));
        var at4=history.verify().retainingVerifiedAncestry(bridges);byte[] all=MembershipGenerationPlan.ancestry(bridges);
        var proof=fixture(full,at4.terminal());
        assertTrue(assertThrows(IllegalArgumentException.class,()->full.confirm(at4,all,proof)).getMessage().contains("pending renewal capacity"));
        assertArrayEquals(canonical(value,16384),full.bytes(),"capacity refusal leaves the original obligations intact");
    }
}
