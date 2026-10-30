package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional history/projection checks cannot manufacture a native permit.
 * The separate native integration exercises actual owner/transport issuance. */
class V53PublishedLearnerSourceTest {
    @ParameterizedTest @CsvSource({"3,ADD","4,ADD","3,REPLACE","4,REPLACE","5,REPLACE"})
    void exactPublishedJoiningHistoryPreservesAllOriginalObligations(int size,String kind) {
        var history=new V53CapsuleFixture(size,kind,5);var learner=V53DeclarationsTest.node(6);var source=V53DeclarationsTest.node(1);
        var empty=MembershipLearnerRetentionPlan.genesis(V53CapsuleFixture.fromHistory(history.source,0).verify());
        var plan=empty.offer(history.verify(),new byte[0],learner);byte[] before=plan.bytes();
        for(int through:List.of(6,7,8)) {
            var current=V53CapsuleFixture.fromHistory(history.source,through).verify();
            MembershipLearnerProgressAccess.publishedSource(current,new byte[0],learner,source,plan);
            assertArrayEquals(before,plan.bytes(),"published read is not a learner offer or discharge");
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.publishedSource(current,new byte[0],learner,source,empty));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.publishedSource(current,new byte[0],learner,learner,plan));
            var other=new MembershipIdentity(learner.nodeId(),UUID.randomUUID(),learner.endpoint());
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.publishedSource(current,new byte[0],other,source,plan));
            var changed=object(V53ContextFixture.mutable(parse(before,16384)));object(changed.get("request")).put("number",2L);
            var foreign=MembershipLearnerRetentionPlan.decode(canonical(changed,16384));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.publishedSource(current,new byte[0],learner,source,foreign));
            changed=object(V53ContextFixture.mutable(parse(before,16384)));object(list(changed.get("possible")).getFirst()).put("application","ab".repeat(32));
            var conflicting=MembershipLearnerRetentionPlan.decode(canonical(changed,16384));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.publishedSource(current,new byte[0],learner,source,conflicting));
        }
        for(int through:List.of(0,1,2,3,4,5,9)) {
            var current=V53CapsuleFixture.fromHistory(history.source,through).verify();
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.publishedSource(current,new byte[0],learner,source,plan));
        }
    }
}
