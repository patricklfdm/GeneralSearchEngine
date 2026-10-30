package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Routing only. Conditional catalog fixtures issue no source or voting authority. */
class V53JoiningIntentReferenceTest {
    @ParameterizedTest @CsvSource({"3,ADD","4,ADD","3,REPLACE","4,REPLACE","5,REPLACE"})
    void aliasBindsFullRequestCutAndPermanentIdentityOnlyWhileSealed(int size,String kind) {
        var f=new V53ContextFixture(size,kind);f.transition(kind);
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)f.root.value().get("groupId"))),
                UUID.fromString((String)f.root.value().get("historyId")),f.rootHash);
        var joining=MembershipContext.identity(V53ContextFixture.member(6));var sealed=context(f,4);
        var change=new MembershipChangeRequest(new MembershipOperationId(root,1),sealed.authority(),MembershipChangeKind.valueOf(kind),
                f.target.stream().map(MembershipContext::identity).toList());
        var request=new MembershipLearnerRequest(root,joining,change,Path.of("/tmp/unused-joining-replica"),Path.of("/tmp/unused-joining-operation"));
        var alias=MembershipJoiningIntentExport.reference(request,sealed.cut);
        assertTrue(MembershipJoiningIntentExport.reference(sealed,joining,alias));
        for(int step:List.of(0,1,2,3,5,6,7,8))assertFalse(MembershipJoiningIntentExport.reference(context(f,step),joining,alias));
        assertFalse(MembershipJoiningIntentExport.reference(sealed,MembershipContext.identity(V53ContextFixture.member(1)),alias));
        var copied=new MembershipIdentity(joining.nodeId(),UUID.randomUUID(),joining.endpoint());
        assertFalse(MembershipJoiningIntentExport.reference(sealed,copied,alias));
        var later=new MembershipChangeRequest(new MembershipOperationId(root,2),sealed.authority(),change.kind(),change.target());
        var different=new MembershipLearnerRequest(root,joining,later,request.replicaDirectory(),request.operationDirectory());
        assertFalse(MembershipJoiningIntentExport.reference(sealed,joining,MembershipJoiningIntentExport.reference(different,sealed.cut)));
        assertFalse(MembershipJoiningIntentExport.reference(sealed,joining,MembershipJoiningIntentExport.reference(request,context(f,3).cut)));
    }
    private static MembershipContext context(V53ContextFixture f,int step) {
        var catalog=decode(f.inventory.get(f.steps.get(step).get("catalogAfter")),"records","CATALOG");
        return new MembershipContext(f.root,catalog,object(catalog.value().get("cut")),f.inventory,f.images);
    }
}
