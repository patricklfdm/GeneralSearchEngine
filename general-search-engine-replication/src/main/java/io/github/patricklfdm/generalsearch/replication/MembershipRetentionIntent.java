package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded logical intent. Its digest excludes transport sequence/recipient so
 * distinct governing voters can acknowledge one identical transition. */
final class MembershipRetentionIntent {
    final Map<String,Object> payload;
    final String digest;
    final MembershipIdentity peer;
    final MembershipCapsule.Anchor lower,upper;
    MembershipRetentionIntent(Map<String,Object> payload) {
        require(payload.keySet().equals(Set.of("selection","peer","lower","upper")),"retention intent fields");
        this.payload=object(parse(canonical(payload,16384),16384));
        MembershipValidation.digest((String)payload.get("selection"));
        peer=MembershipContext.identity(object(this.payload.get("peer")));
        lower=anchor(object(this.payload.get("lower")));upper=anchor(object(this.payload.get("upper")));
        require(number(lower.cut().get("index"))<number(upper.cut().get("index")),"retention intent advancing cut");
        digest=hash(canonical(this.payload,16384));
    }
    private static MembershipCapsule.Anchor anchor(Map<String,Object> value) {
        require(value.keySet().equals(Set.of("cut","catalog","application")),"retention intent anchor fields");
        checkType(value,"retentionAnchor");return new MembershipCapsule.Anchor(object(value.get("cut")),(String)value.get("catalog"),(String)value.get("application"));
    }
    static Map<String,Object> anchor(MembershipCapsule.Anchor value) {
        return Map.of("cut",value.cut(),"catalog",value.catalog(),"application",value.application());
    }
}
