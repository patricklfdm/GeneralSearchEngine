package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Logical unpublished target, never a remote application capability. Each
 * acknowledging owner must bind it to its own actual native applied result. */
final class MembershipFutureRetentionIntent {
    final Map<String,Object> payload;
    final String digest,selection,certificate;
    final MembershipIdentity peer;
    final MembershipCapsule.Anchor lower,parent,upper;
    MembershipFutureRetentionIntent(Map<String,Object> value) {
        require(value.keySet().equals(Set.of("selection","certificate","peer","lower","parent","upper")),"future intent fields");
        payload=object(parse(canonical(value,16384),16384));
        selection=(String)payload.get("selection");certificate=(String)payload.get("certificate");
        MembershipValidation.digest(selection);MembershipValidation.digest(certificate);
        checkType(payload.get("peer"),"identity");peer=MembershipContext.identity(object(payload.get("peer")));
        lower=anchor(payload.get("lower"));parent=anchor(payload.get("parent"));upper=anchor(payload.get("upper"));
        require(number(lower.cut().get("index"))<=number(parent.cut().get("index"))
                && number(parent.cut().get("index"))<MembershipBallotAllocator.MAX
                && number(upper.cut().get("index"))==number(parent.cut().get("index"))+1,"future intent immediate advancing target");
        digest=hash(canonical(payload,16384));
    }
    private static MembershipCapsule.Anchor anchor(Object value) {
        checkType(value,"retentionAnchor");var a=object(value);MembershipContext.checkView(object(object(a.get("cut")).get("view")));
        return new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application"));
    }
}
