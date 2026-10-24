package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact inactive inventory; validation alone never authorizes deletion. */
final class MembershipRetirementPlan {
    final Decoded record;
    final MembershipFloor.Copy original;
    final String inactive;
    private MembershipRetirementPlan(Decoded record,MembershipFloor.Copy original,String inactive) {
        this.record=record;this.original=original;this.inactive=inactive;
    }
    static MembershipRetirementPlan create(MembershipRoot root,MembershipIdentity identity,MembershipCurrentGeneration current,
            MembershipFloorFiles.Retained retained,MembershipFloor.Copy old) throws java.io.IOException {
        return create(root,identity,current,retained,old,null);
    }
    static MembershipRetirementPlan create(MembershipRoot root,MembershipIdentity identity,MembershipCurrentGeneration current,
            MembershipFloorFiles.Retained retained,MembershipFloor.Copy old,MembershipPendingContext.Reconstructed context) throws java.io.IOException {
        current.check();old.check();require(old.owner.equals(identity),"retirement local owner");
        var selector=current.selector;var floor=retained.floor();var floorCopies=retained.copies();
        require(selector.kind().equals("SELECTOR") && selector.value().get("root").equals(root.manifestDigest())
                && selector.value().get("node").equals(identity.nodeId().value()) && selector.value().get("digest").equals(current.manifest.digest())
                && selector.value().get("generation").equals(current.manifest.value().get("generation")),"retirement current selector");
        String inactive=(String)old.generation.value().get("generation");
        require(!inactive.equals(selector.value().get("generation")),"retirement cannot list current generation");
        var floorLocal=floorCopies.stream().filter(c->c.owner.equals(identity)).findFirst().orElseThrow(()->new IllegalArgumentException("retirement floor local copy"));
        MembershipFloor.verify(floor,root,floorLocal,floorCopies);
        current.verifyParents(List.of(floorLocal.capsule.terminal()));
        floorLocal.capsule.verifyAncestry(floorLocal.fileNames().contains("ancestry.gsr")?floorLocal.fileBytes("ancestry.gsr"):new byte[0],List.of(old.capsule.terminal()));
        require(number(old.capsule.context.cut.get("index"))<=number(object(floor.value().get("cut")).get("index")),"retirement generation above floor");
        if(old.generation.value().get("ownedTail")!=null) {
            String digest=(String)old.generation.value().get("ownedTail");var accept=decode(old.fileBytes("owned-tail.gsr"),"records","ACCEPT");
            if(number(accept.value().get("index"))>number(object(floor.value().get("cut")).get("index"))) {
                var entry=decode(old.capsule.packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY");
                for(String original:List.of(digest,entry.digest(),(String)entry.value().get("payload")))
                    require(Arrays.equals(old.capsule.packet.objectBytes(original),current.capsule.packet.objectBytes(original)),"retirement loses original above-floor owned bytes");
                if(number(accept.value().get("index"))>number(current.capsule.context.cut.get("index")))
                    require(digest.equals(current.manifest.value().get("ownedTail")) || MembershipContextTail.retained(current,accept,context),"retirement loses unresolved tail ownership");
            }
        }
        var files=new ArrayList<Map<String,Object>>();
        for(String name:new TreeSet<>(old.fileNames())){byte[] bytes=old.fileBytes(name);files.add(Map.of("path","generations/"+inactive+"/"+name,"size",(long)bytes.length,"sha256",hash(bytes)));}
        var record=decode(encode("records","RETIREMENT",Map.of("root",root.manifestDigest(),"node",identity.nodeId().value(),
                "floor",floor.digest(),"selector",selector.digest(),"files",files)),"records","RETIREMENT");
        return new MembershipRetirementPlan(record,old,inactive);
    }
}
