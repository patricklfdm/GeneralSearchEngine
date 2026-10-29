package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact nonvoting source obligation; decoding is neither durability nor a
 * learner head confirmation. Each voter must check its own original history. */
final class MembershipLearnerRetentionIntent {
    final Map<String,Object> payload,request;
    final String digest,selection;
    final MembershipIdentity learner;
    final MembershipCapsule.Anchor endpoint;
    MembershipLearnerRetentionIntent(Map<String,Object> value) {
        require(value.keySet().equals(Set.of("selection","request","learner","endpoint")),"learner intent fields");
        payload=object(parse(canonical(value,16384),16384));selection=(String)payload.get("selection");
        MembershipValidation.digest(selection);checkType(payload.get("request"),"request");request=object(payload.get("request"));
        checkType(payload.get("learner"),"identity");learner=MembershipContext.identity(object(payload.get("learner")));
        require(!request.get("kind").equals("REMOVE") && list(request.get("target")).stream().map(MembershipFormat::object)
                .map(MembershipContext::identity).anyMatch(learner::equals),"learner intent original joining identity");
        checkType(payload.get("endpoint"),"retentionAnchor");var anchor=object(payload.get("endpoint"));
        endpoint=new MembershipCapsule.Anchor(object(anchor.get("cut")),(String)anchor.get("catalog"),(String)anchor.get("application"));
        MembershipContext.checkView(object(endpoint.cut().get("view")));digest=hash(canonical(payload,16384));
    }
}
