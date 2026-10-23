package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact original selected BASIS frames. Private generation metadata, not replacement votes/receipts. */
final class MembershipSelectedSources {
    static final String FILE="selected-sources.gsr";
    static final int MAXIMUM=6*16384;
    static byte[] encodeSources(MembershipSelection.Decision decision) {
        var out=new ByteArrayOutputStream();
        for(var source:decision.sources())out.writeBytes(source.basis.bytes());
        byte[] bytes=out.toByteArray();cuts(bytes,decision.selected());return bytes;
    }
    static List<Map<String,Object>> cuts(byte[] bytes,Decoded selected) {
        require(bytes.length>0 && bytes.length<=MAXIMUM && selected.kind().equals("SELECTED"),"selected source frame capacity/kind");
        var refs=list(selected.value().get("sources"));require(refs.size()>=2 && refs.size()<=6,"selected source count");
        var voters=refs.stream().map(MembershipFormat::object).map(v->(String)v.get("voter")).toList();
        orderedNodes(voters);quorum(object(object(selected.value().get("cut")).get("view")),voters);
        require(voters.contains(object(selected.value().get("ballot")).get("proposer")),"selected source proposer absent");
        var cuts=new ArrayList<Map<String,Object>>();int offset=0;boolean longest=false;
        for(Object item:refs) {
            require(bytes.length-offset>=HEADER,"missing selected original BASIS");
            int length=HEADER+header(Arrays.copyOfRange(bytes,offset,offset+HEADER),"records","BASIS");
            require(length<=16384 && length<=bytes.length-offset,"truncated selected original BASIS");
            var basis=decode(Arrays.copyOfRange(bytes,offset,offset+length),"records","BASIS");offset+=length;
            var value=basis.value();var ref=object(item);
            require(basis.digest().equals(ref.get("basisDigest")) && value.get("basisId").equals(ref.get("basisId"))
                    && value.get("voter").equals(ref.get("voter")),"selected original source reference");
            for(String field:List.of("root","view","ballot"))require(value.get(field).equals(selected.value().get(field)),"selected original source binding");
            var cut=object(value.get("cut"));
            require(viewDigest((String)value.get("root"),object(cut.get("view"))).equals(value.get("view"))
                    && number(cut.get("index"))<=number(object(selected.value().get("cut")).get("index")),"selected original source cut");
            if(cut.equals(selected.value().get("cut")))longest=true;cuts.add(cut);
        }
        require(offset==bytes.length && longest,"selected source inventory/longest cut");return List.copyOf(cuts);
    }
    static List<MembershipCapsule.Anchor> parents(byte[] bytes,Decoded selected,MembershipCapsule capsule,byte[] ancestry) {
        var lower=capsule.ancestryAnchors(ancestry);var result=new TreeMap<Long,MembershipCapsule.Anchor>();
        for(var cut:cuts(bytes,selected)) {
            var anchor=capsule.anchor(number(cut.get("index")));if(anchor==null)anchor=lower.get(cut);
            require(anchor!=null && anchor.cut().equals(cut),"selected source lost authenticated original endpoint");
            var previous=result.putIfAbsent(number(cut.get("index")),anchor);
            require(previous==null || previous.equals(anchor),"selected source conflicting original endpoint");
        }
        return List.copyOf(result.values());
    }
    private MembershipSelectedSources() {}
}
