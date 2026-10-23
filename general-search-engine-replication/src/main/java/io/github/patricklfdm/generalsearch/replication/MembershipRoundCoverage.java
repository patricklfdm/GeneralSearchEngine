package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded proof component for a stable original selection. Not admitted by the storage reader yet.
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
    private static byte[] encode(Decoded selected,First first,MembershipCapsule.Anchor parent,Decoded certificate) {
        return canonical(Map.of("schema","gse-v53-round-coverage/1.3","selection",selected.digest(),
                "first",Map.of("parent",anchor(first.parent()),"end",anchor(first.end()),"certificate",first.certificate().digest()),
                "parent",anchor(parent),"certificate",certificate.digest()),MAXIMUM);
    }
    static byte[] begin(MembershipCapsule capsule,byte[] originalCoverage,byte[] ancestry,Decoded promise,Decoded selected) {
        MembershipSelectionCoverage.verify(originalCoverage,capsule,promise,selected,ancestry);
        var value=object(parse(originalCoverage,MembershipSelectionCoverage.MAXIMUM));
        var parent=anchor(value.get("parent"));var certificate=capsule.context.record((String)value.get("certificate"),"CERTIFICATE");
        byte[] result=encode(selected,new First(parent,capsule.terminal(),certificate),parent,certificate);
        verify(result,capsule,promise,selected,ancestry);return result;
    }
    static First verify(byte[] bytes,MembershipCapsule capsule,Decoded promise,Decoded selected,byte[] ancestry) {
        var value=object(parse(bytes,MAXIMUM));
        require(value.keySet().equals(Set.of("schema","selection","first","parent","certificate"))
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
        return new First(firstParent,firstEnd,firstCertificate);
    }
    /** The new candidate must already possess exact fresh checkpoint/phased observations. */
    static Publication advance(MembershipCapsule before,byte[] previous,byte[] priorAncestry,MembershipCapsule candidate,byte[] ancestry,
            Decoded promise,Decoded selected,Decoded certificate,Map<String,byte[]> images) {
        var first=verify(previous,before,promise,selected,priorAncestry);
        require(before.context.view.equals(first.parent().cut().get("view")) && before.context.view.get("operation")==null,"round ended at membership boundary");
        var retained=candidate.retainingCertificate(before,first.certificate(),first.parent().cut(),images);
        byte[] result=encode(selected,first,before.terminal(),certificate);verify(result,retained,promise,selected,ancestry);
        return new Publication(retained,result);
    }
    private MembershipRoundCoverage() {}
}
