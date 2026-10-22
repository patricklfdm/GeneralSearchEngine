package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact obsolete original-source decision. A plan is not a forced deletion authority. */
final class MembershipSourceRetirementPlan {
    final String basisId;
    final Decoded record,promise,basis;
    private MembershipSourceRetirementPlan(String basisId,Decoded record,Decoded promise,Decoded basis) {
        this.basisId=basisId;this.record=record;this.promise=promise;this.basis=basis;
    }
    static MembershipSourceRetirementPlan create(MembershipRoot root,MembershipIdentity identity,
            MembershipCurrentGeneration current,MembershipFloorFiles.Retained retained,Decoded highest,
            Decoded promise,Decoded basis,MembershipCapsule original,Map<String,byte[]> images) throws IOException {
        current.check();require(promise.kind().equals("PROMISE") && basis.kind().equals("BASIS") && highest.kind().equals("PROMISE"),"source retirement grant records");
        String id=(String)promise.value().get("basisId");require(id!=null && id.equals(basis.value().get("basisId")),"source retirement original identity");
        for(String field:List.of("root","view","ballot"))require(promise.value().get(field).equals(basis.value().get(field)),"source retirement grant context");
        require(basis.value().get("root").equals(root.manifestDigest()) && highest.value().get("root").equals(root.manifestDigest())
                && basis.value().get("voter").equals(identity.nodeId().value())
                && identity.equals(original.context.identities.get(identity.nodeId().value())),"source retirement root/owner");
        original.packet.bind(basis);original.packet.verifyImages(images);
        require(compareBallot(object(highest.value().get("ballot")),object(promise.value().get("ballot")))>0,"source retirement needs a newer durable promise");
        require(!promise.digest().equals(current.manifest.value().get("promise")) && !basis.digest().equals(current.manifest.value().get("basis")),"source retirement current generation reference");
        var local=retained.copies().stream().filter(c->c.owner.equals(identity)).findFirst().orElseThrow(()->new IllegalArgumentException("source retirement floor local copy"));
        MembershipFloor.verify(retained.floor(),root,local,retained.copies());
        require(!promise.digest().equals(local.generation.value().get("promise")) && !basis.digest().equals(local.generation.value().get("basis")),"source retirement governing floor reference");
        current.verifyParents(List.of(local.capsule.terminal(),original.terminal()));
        local.capsule.verifyAncestry(local.fileNames().contains("ancestry.gsr")?local.fileBytes("ancestry.gsr"):new byte[0],List.of(original.terminal()));
        long floor=number(object(retained.floor().value().get("cut")).get("index"));
        require(number(original.context.cut.get("index"))<=floor,"source retirement cut above floor");
        if(basis.value().get("accepted")!=null) {
            var accept=decode(original.packet.objectBytes((String)basis.value().get("accepted")),"records","ACCEPT");
            if(number(accept.value().get("index"))>floor) {
                var entry=decode(original.packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY");
                for(String digest:List.of(accept.digest(),entry.digest(),(String)entry.value().get("payload")))
                    require(Arrays.equals(original.packet.objectBytes(digest),current.capsule.packet.objectBytes(digest)),"source retirement loses above-floor original bytes");
                if(number(accept.value().get("index"))>number(current.capsule.context.cut.get("index")))
                    require(accept.digest().equals(current.accepted),"source retirement loses unresolved ownership");
            }
        }
        var files=new TreeMap<String,byte[]>();files.put(MembershipBasisSources.PACKET,original.packet.bytes());images.forEach((digest,bytes)->files.put(digest+".image",bytes));
        var inventory=new ArrayList<Map<String,Object>>();for(var file:files.entrySet())inventory.add(Map.of("path","sources/"+id+"/"+file.getKey(),"size",(long)file.getValue().length,"sha256",hash(file.getValue())));
        var record=decode(encode("records","RETIREMENT",Map.of("root",root.manifestDigest(),"node",identity.nodeId().value(),
                "floor",retained.floor().digest(),"selector",current.selector.digest(),"files",inventory)),"records","RETIREMENT");
        current.check();return new MembershipSourceRetirementPlan(id,record,promise,basis);
    }
}
