package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded proof continuity for storage under an immutable original stable selection.
 * No grant, vote, activation, persistence or READY is performed by this class. */
final class MembershipRoundCoverage {
    static final int MAXIMUM=MembershipSelectionCoverage.MAXIMUM;
    private static final Set<String> STABLE=Set.of("DATA","BARRIER","RESERVE","PREPARE","READY","SEAL","CANCEL","RETIRE");
    record First(MembershipCapsule.Anchor parent,MembershipCapsule.Anchor end,Decoded certificate) {}
    record Publication(MembershipCapsule capsule,byte[] coverage) {
        Publication {coverage=coverage.clone();}
        @Override public byte[] coverage(){return coverage.clone();}
    }
    private static Map<String,Object> anchor(MembershipCapsule.Anchor a){return Map.of("cut",a.cut(),"catalog",a.catalog(),"application",a.application());}
    private static MembershipCapsule.Anchor anchor(Object value) {
        var a=object(value);require(a.keySet().equals(Set.of("cut","catalog","application")) && a.get("catalog") instanceof String && a.get("application") instanceof String,"round anchor fields");
        return new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application"));
    }
    private static Map<String,Object> value(Decoded selected,First first,MembershipCapsule.Anchor parent,String certificate,List<MembershipCapsule.Anchor> ancestors) {
        var result=new TreeMap<String,Object>(Map.of("schema","gse-v53-round-coverage/1.3","selection",selected.digest(),
                "first",Map.of("parent",anchor(first.parent()),"end",anchor(first.end()),"certificate",first.certificate().digest()),
                "parent",anchor(parent),"certificate",certificate));
        require(ancestors.size()<=5,"round ancestor count");
        if(!ancestors.isEmpty())result.put("ancestors",ancestors.stream().map(MembershipRoundCoverage::anchor).toList());
        return result;
    }
    private static byte[] encode(Decoded selected,First first,MembershipCapsule.Anchor parent,Decoded certificate,List<MembershipCapsule.Anchor> ancestors) {
        return canonical(value(selected,first,parent,certificate.digest(),ancestors),MAXIMUM);
    }
    static First first(MembershipCapsule capsule,byte[] coverage,byte[] ancestry,Decoded promise,Decoded selected) {
        require(coverage!=null,"round continuation requires original published coverage");
        var value=object(parse(coverage,MAXIMUM));
        if("gse-v53-round-coverage/1.3".equals(value.get("schema")))return verify(coverage,capsule,promise,selected,ancestry);
        MembershipSelectionCoverage.verify(coverage,capsule,promise,selected,ancestry);
        var first=new First(anchor(value.get("parent")),capsule.terminal(),capsule.context.record((String)value.get("certificate"),"CERTIFICATE"));
        require(first.parent().cut().get("view").equals(first.end().cut().get("view"))
                && object(first.parent().cut().get("view")).get("operation")==null,"round requires a stable first slot");
        return first;
    }
    static byte[] begin(MembershipCapsule capsule,byte[] originalCoverage,byte[] ancestry,Decoded promise,Decoded selected) {
        var first=first(capsule,originalCoverage,ancestry,promise,selected);
        var original=object(parse(originalCoverage,MAXIMUM));
        byte[] result=encode(selected,first,anchor(original.get("parent")),capsule.context.record((String)original.get("certificate"),"CERTIFICATE"),
                MembershipSelectionCoverage.additionalParents(originalCoverage));
        verify(result,capsule,promise,selected,ancestry);return result;
    }
    /** Sizing only; the placeholder is never retained as a certificate. */
    static int publicationBytes(MembershipCapsule before,byte[] coverage,byte[] ancestry,Decoded promise,Decoded selected,List<MembershipCapsule.Anchor> ancestors) {
        return canonical(value(selected,first(before,coverage,ancestry,promise,selected),before.terminal(),"0".repeat(64),ancestors),16*1024).length;
    }
    static First verify(byte[] bytes,MembershipCapsule capsule,Decoded promise,Decoded selected,byte[] ancestry) {
        var value=object(parse(bytes,MAXIMUM));
        require((value.keySet().equals(Set.of("schema","selection","first","parent","certificate"))
                || value.keySet().equals(Set.of("schema","selection","first","parent","certificate","ancestors")))
                && "gse-v53-round-coverage/1.3".equals(value.get("schema")) && selected.digest().equals(value.get("selection"))
                && value.get("certificate") instanceof String && Arrays.equals(bytes,canonical(value,MAXIMUM)),"round coverage identity");
        var original=object(value.get("first"));require(original.keySet().equals(Set.of("parent","end","certificate")) && original.get("certificate") instanceof String,"round original proof fields");
        var firstParent=anchor(original.get("parent"));var firstEnd=anchor(original.get("end"));var parent=anchor(value.get("parent"));
        var s=selected.value();var view=object(firstParent.cut().get("view"));
        require(promise.kind().equals("PROMISE") && selected.kind().equals("SELECTED") && s.get("root").equals(capsule.context.root)
                && s.get("cut").equals(firstParent.cut()) && s.get("view").equals(viewDigest(capsule.context.root,view)),"round original selected parent");
        for(String field:List.of("root","view","ballot"))require(s.get(field).equals(promise.value().get(field)),"round original promise");
        var voters=list(s.get("sources")).stream().map(MembershipFormat::object).map(r->(String)r.get("voter")).toList();orderedNodes(voters);quorum(view,voters);
        require(voters.contains(object(s.get("ballot")).get("proposer")),"round selected proposer");
        require(view.get("operation")==null && view.equals(firstEnd.cut().get("view")) && view.equals(parent.cut().get("view")),"round stable original authority");
        long start=number(firstParent.cut().get("index")),end=number(firstEnd.cut().get("index")),at=number(parent.cut().get("index"));
        require(start<MembershipValidation.MAX && end==start+1 && at>=start && at<MembershipValidation.MAX
                && number(capsule.context.cut.get("index"))==at+1,"round exact first/latest slots");
        capsule.verifyAncestry(ancestry,List.of(firstParent,firstEnd,parent));
        var firstCertificate=capsule.context.record((String)original.get("certificate"),"CERTIFICATE");
        var firstEntry=capsule.publicationCertificate(firstCertificate,firstParent.cut());
        require(firstCertificate.value().get("ballot").equals(s.get("ballot")) && firstEntry.digest().equals(firstEnd.cut().get("entry"))
                && STABLE.contains(firstEntry.value().get("kind")),"round original certified stable slot");
        require(s.get("nextEntry")==null?firstEntry.value().get("origin").equals(s.get("ballot")):s.get("nextEntry").equals(firstEntry.digest()),"round original carried choice");
        var certificate=capsule.context.record((String)value.get("certificate"),"CERTIFICATE");var entry=capsule.publicationCertificate(certificate,parent.cut());
        require(certificate.value().get("ballot").equals(s.get("ballot")) && entry.digest().equals(capsule.context.cut.get("entry")),"round current exact certified slot");
        if(at==start)require(parent.equals(firstParent) && capsule.terminal().equals(firstEnd) && certificate.digest().equals(firstCertificate.digest()),"round initial receipt changed");
        else require(at>=end && entry.value().get("origin").equals(s.get("ballot"))
                && (STABLE.contains(entry.value().get("kind")) || entry.value().get("kind").equals("INTENT")),"round subsequent origin/kind");
        var additional=MembershipSelectionCoverage.additionalParents(bytes);capsule.verifyAncestry(ancestry,additional);
        if(!additional.isEmpty()) {
            var last=object(list(capsule.packet.capsule().value().get("items")).getLast());
            var statement=capsule.context.record((String)last.get("statement"),"CHECKPOINT");
            for(var lower:additional)MembershipCheckpointPlan.ancestorStatement(statement,parent,lower);
        }
        return new First(firstParent,firstEnd,firstCertificate);
    }
    /** The new candidate must already possess exact fresh checkpoint/phased observations. */
    static Publication advance(MembershipCapsule before,byte[] previous,byte[] priorAncestry,MembershipCapsule candidate,byte[] ancestry,
            Decoded promise,Decoded selected,Decoded certificate,Map<String,byte[]> images) {
        var first=verify(previous,before,promise,selected,priorAncestry);
        require(before.context.view.equals(first.parent().cut().get("view")) && before.context.view.get("operation")==null,"round ended at membership boundary");
        var retained=candidate.retainingCertificate(before,first.certificate(),first.parent().cut(),images);
        byte[] result=encode(selected,first,before.terminal(),certificate,List.of());verify(result,retained,promise,selected,ancestry);
        return new Publication(retained,result);
    }
    /** Accept the exact predecessor, or the exact already-published receipt on an idempotent retry. */
    static Publication publish(MembershipCapsule original,byte[] coverage,byte[] originalAncestry,MembershipCapsule candidate,byte[] ancestry,
            Decoded promise,Decoded selected,MembershipCheckpointPlan plan) {
        var first=first(original,coverage,originalAncestry,promise,selected);
        if(original.terminal().equals(plan.originalParent()))
            require(original.context.view.equals(first.parent().cut().get("view")) && original.context.view.get("operation")==null,"round ended at membership boundary");
        else {
            var prior=object(parse(coverage,MAXIMUM));
            require(original.terminal().equals(candidate.terminal()) && anchor(prior.get("parent")).equals(plan.originalParent())
                    && plan.originalCertificate().digest().equals(prior.get("certificate")),"round duplicate publication changed original receipt");
        }
        var retained=candidate.retainingCertificate(original,first.certificate(),first.parent().cut(),Map.of(hash(plan.application.image()),plan.application.image()));
        byte[] result=encode(selected,first,plan.originalParent(),plan.originalCertificate(),plan.additionalParents());
        verify(result,retained,promise,selected,ancestry);return new Publication(retained,result);
    }
    private MembershipRoundCoverage() {}
}
