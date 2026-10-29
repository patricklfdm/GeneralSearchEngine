package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Pure projections over explicitly conditional history, not quorum evidence. */
class V53LearnerRetentionPlanTest {
    static MembershipCapsule capsule(int size,String kind,int cut){return new V53CapsuleFixture(size,kind,cut).verify();}
    static MembershipLearnerRetentionPlan offered(int size,String kind,int cut) {
        return MembershipLearnerRetentionPlan.genesis(capsule(size,kind,0)).offer(capsule(size,kind,cut),new byte[0],V53DeclarationsTest.node(6));
    }
    @Test void allFiveJoiningProfilesBindExactSourceAndCanonicalImmutableRequest() {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            var current=capsule(size,kind,3);var plan=offered(size,kind,3);
            assertEquals(List.of(current.terminal()),plan.required(current,new byte[0]));
            assertEquals(3L,plan.recorded().getFirst().cut().get("index"));
            assertArrayEquals(plan.bytes(),MembershipLearnerRetentionPlan.decode(plan.bytes()).bytes());
            assertArrayEquals(plan.bytes(),plan.offer(current,new byte[0],V53DeclarationsTest.node(6)).bytes());
            assertThrows(UnsupportedOperationException.class,()->plan.recorded().clear());
            assertThrows(UnsupportedOperationException.class,()->plan.recorded().getFirst().cut().put("index",99L));
        }
    }
    @Test void newerTipSameImageAndReceiptCannotReplaceOriginalAncestor() {
        var plan=offered(3,"ADD",3);var later=capsule(3,"ADD",5);
        assertEquals(plan.recorded().getFirst().application(),later.terminal().application());
        assertThrows(IllegalArgumentException.class,()->plan.required(later,new byte[0]));
        assertThrows(IllegalArgumentException.class,()->plan.offer(later,new byte[0],V53DeclarationsTest.node(6)));
        assertThrows(IllegalArgumentException.class,()->plan.required(capsule(4,"ADD",3),new byte[0]));
    }
    @Test void mergesKeepBothPossibilitiesWithoutTrustingEmptyOrNewerClaims() {
        var a=offered(3,"REPLACE",3);var b=offered(3,"REPLACE",4);
        var zero=MembershipLearnerRetentionPlan.genesis(capsule(3,"REPLACE",0));String root=capsule(3,"REPLACE",0).context.root;
        for(var order:List.of(List.of(zero,a,b),List.of(b,a,zero),List.of(a,b,a))) {
            var merged=MembershipLearnerRetentionPlan.mergeRecorded(root,order);
            assertEquals(List.of(3L,4L),merged.recorded().stream().map(p->number(p.cut().get("index"))).toList());
            assertArrayEquals(merged.bytes(),MembershipLearnerRetentionPlan.decode(merged.bytes()).bytes());
        }
        var c=offered(3,"REPLACE",5);
        assertTrue(assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(root,List.of(a,b,c)))
                .getMessage().contains("endpoint capacity"));
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(root,List.of()));
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(root,Collections.nCopies(8,a)));
    }
    @Test void foreignOperationAndSameIndexDifferentAuthorityCannotMerge() {
        var a=offered(3,"ADD",3);String root=capsule(3,"ADD",0).context.root;
        var requestChanged=object(V53ContextFixture.mutable(parse(a.bytes(),16384)));
        object(requestChanged.get("request")).put("number",2L);
        var other=MembershipLearnerRetentionPlan.decode(canonical(requestChanged,16384));
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(root,List.of(a,other)));
        var pointChanged=object(V53ContextFixture.mutable(parse(a.bytes(),16384)));
        object(list(pointChanged.get("possible")).getFirst()).put("catalog","cd".repeat(32));
        var conflict=MembershipLearnerRetentionPlan.decode(canonical(pointChanged,16384));
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(root,List.of(a,conflict)));
        assertThrows(IllegalArgumentException.class,()->conflict.required(capsule(3,"ADD",3),new byte[0]));
    }
    @Test void cannotEnrollCurrentVoterChangedStorageOrJointAndTerminalOperation() {
        var initial=MembershipLearnerRetentionPlan.genesis(capsule(3,"ADD",0));var at=capsule(3,"ADD",3);
        assertThrows(IllegalArgumentException.class,()->initial.offer(at,new byte[0],V53DeclarationsTest.node(1)));
        var id=V53DeclarationsTest.node(6);var changed=new MembershipIdentity(id.nodeId(),UUID.randomUUID(),id.endpoint());
        assertThrows(IllegalArgumentException.class,()->initial.offer(at,new byte[0],changed));
        for(int index:List.of(0,1,6,7,8,9))assertThrows(IllegalArgumentException.class,()->initial.offer(capsule(3,"ADD",index),new byte[0],id));
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.genesis(at));
    }
    @Test void retirementCannotEraseStillUnconfirmedOriginalOperation() {
        var plan=offered(3,"ADD",3);
        assertTrue(plan.preventsRetirement("RETIRE",canonical(Map.of("through",1L),8192)));
        assertThrows(IllegalArgumentException.class,()->plan.preventsRetirement("RETIRE",canonical(Map.of("through",0L),8192)));
        var later=object(V53ContextFixture.mutable(parse(plan.bytes(),16384)));object(later.get("request")).put("number",2L);
        assertFalse(MembershipLearnerRetentionPlan.decode(canonical(later,16384)).preventsRetirement("RETIRE",canonical(Map.of("through",1L),8192)));
        assertFalse(plan.preventsRetirement("CANCEL",canonical(Map.of("number",1L),8192)));
        assertFalse(MembershipLearnerRetentionPlan.genesis(capsule(3,"ADD",0)).preventsRetirement("RETIRE",canonical(Map.of("through",1L),8192)));
    }
    @Test void decodingRefusesNoncanonicalOrIncompleteBindings() {
        var a=offered(3,"ADD",3);var original=object(parse(a.bytes(),16384));
        for(String missing:List.of("root","request","learner","possible")) {
            var value=new TreeMap<>(original);value.remove(missing);
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.decode(canonical(value,16384)));
        }
        for(String nullable:List.of("request","learner")) {
            var value=new TreeMap<>(original);value.put(nullable,null);
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.decode(canonical(value,16384)));
        }
        var unknown=new TreeMap<>(original);unknown.put("quorum",true);
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.decode(canonical(unknown,16384)));
        var duplicates=new TreeMap<>(original);var points=list(original.get("possible"));duplicates.put("possible",List.of(points.getFirst(),points.getFirst()));
        assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.decode(canonical(duplicates,16384)));
    }
}
