package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private generation metadata: original selected parent and its certified first slot.
 * This is neither a replacement SELECTED record nor an ownership receipt. */
final class MembershipSelectionCoverage {
    static final String FILE="selected-coverage.json";
    static final int MAXIMUM=4096;
    static byte[] encodeCoverage(Decoded selected,MembershipCapsule.Anchor parent,Decoded certificate) {
        return encodeCoverage(selected,parent,certificate,List.of());
    }
    static byte[] encodeCoverage(Decoded selected,MembershipCapsule.Anchor parent,Decoded certificate,List<MembershipCapsule.Anchor> ancestors) {
        return canonical(value(selected,parent,certificate.digest(),ancestors),MAXIMUM);
    }
    /** Only byte sizing: the placeholder digest is never a certificate or retained authority. */
    static int publicationBytes(Decoded selected,MembershipCapsule.Anchor parent,List<MembershipCapsule.Anchor> ancestors) {
        return canonical(value(selected,parent,"0".repeat(64),ancestors),16*1024).length;
    }
    private static Map<String,Object> value(Decoded selected,MembershipCapsule.Anchor parent,String certificate,List<MembershipCapsule.Anchor> ancestors) {
        var value=new TreeMap<String,Object>(Map.of("schema","gse-v53-selected-coverage/1.3","selection",selected.digest(),
                "parent",Map.of("cut",parent.cut(),"catalog",parent.catalog(),"application",parent.application()),"certificate",certificate));
        require(ancestors.size()<=5,"publication local ancestor count");
        if(!ancestors.isEmpty())value.put("ancestors",ancestors.stream().map(a->Map.of("cut",a.cut(),"catalog",a.catalog(),"application",a.application())).toList());
        return value;
    }
    static List<MembershipCapsule.Anchor> additionalParents(byte[] bytes) {
        var value=object(parse(bytes,MAXIMUM));if(!value.containsKey("ancestors"))return List.of();
        var result=new ArrayList<MembershipCapsule.Anchor>();long prior=-1;
        var rows=list(value.get("ancestors"));require(!rows.isEmpty() && rows.size()<=5,"publication ancestor inventory");
        for(Object row:rows) {
            var item=object(row);require(item.keySet().equals(Set.of("cut","catalog","application")) && item.get("catalog") instanceof String
                    && item.get("application") instanceof String,"publication ancestor fields");
            var anchor=new MembershipCapsule.Anchor(object(item.get("cut")),(String)item.get("catalog"),(String)item.get("application"));
            long index=number(anchor.cut().get("index"));require(index>prior,"publication ordered distinct ancestors");prior=index;result.add(anchor);
        }
        return List.copyOf(result);
    }
    static void verify(byte[] bytes,MembershipCapsule capsule,Decoded promise,Decoded selected,byte[] ancestry) {
        require(promise.kind().equals("PROMISE") && selected.kind().equals("SELECTED"),"publication original record kinds");
        var value=object(parse(bytes,MAXIMUM));
        require((value.keySet().equals(Set.of("schema","selection","parent","certificate")) || value.keySet().equals(Set.of("schema","selection","parent","certificate","ancestors")))
                && "gse-v53-selected-coverage/1.3".equals(value.get("schema"))
                && selected.digest().equals(value.get("selection")) && Arrays.equals(bytes,canonical(value,MAXIMUM)),"publication coverage identity");
        var p=object(value.get("parent"));require(p.keySet().equals(Set.of("cut","catalog","application")),"publication parent fields");
        require(p.get("catalog") instanceof String && p.get("application") instanceof String
                && value.get("certificate") instanceof String,"publication parent/certificate digests");
        var parent=new MembershipCapsule.Anchor(object(p.get("cut")),(String)p.get("catalog"),(String)p.get("application"));
        var s=selected.value();var promised=promise.value();
        require(s.get("root").equals(capsule.context.root) && s.get("cut").equals(parent.cut())
                && s.get("view").equals(viewDigest(capsule.context.root,object(parent.cut().get("view")))),"publication original selected parent");
        for(String field:List.of("root","view","ballot"))require(s.get(field).equals(promised.get(field)),"publication original promise binding");
        var voters=list(s.get("sources")).stream().map(MembershipFormat::object).map(v->(String)v.get("voter")).toList();
        orderedNodes(voters);quorum(object(parent.cut().get("view")),voters);
        require(voters.contains(object(s.get("ballot")).get("proposer")),"publication selected proposer absent");
        long start=number(parent.cut().get("index"));
        require(start<MembershipValidation.MAX && number(capsule.context.cut.get("index"))==start+1,"publication first selected slot only");
        capsule.verifyAncestry(ancestry,List.of(parent));
        var additional=additionalParents(bytes);capsule.verifyAncestry(ancestry,additional);
        if(!additional.isEmpty()) {
            var last=object(list(capsule.packet.capsule().value().get("items")).getLast());
            var statement=capsule.context.record((String)last.get("statement"),"CHECKPOINT");
            for(var lower:additional)MembershipCheckpointPlan.ancestorStatement(statement,parent,lower);
        }
        var certificate=capsule.context.record((String)value.get("certificate"),"CERTIFICATE");
        var entry=capsule.publicationCertificate(certificate,parent.cut());
        require(certificate.value().get("ballot").equals(s.get("ballot"))
                && entry.digest().equals(capsule.context.cut.get("entry")),"publication exact certified selected slot");
        require(s.get("nextEntry")==null?entry.value().get("origin").equals(s.get("ballot"))
                :s.get("nextEntry").equals(entry.digest()),"publication changed selected carried entry/origin");
    }
    private MembershipSelectionCoverage() {}
}
