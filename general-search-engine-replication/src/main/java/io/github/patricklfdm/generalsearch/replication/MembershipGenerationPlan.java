package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Complete deterministic selected materialization. The journal must verify its original decision before use. */
final class MembershipGenerationPlan {
    static final String ADOPTION="adopted-certificate.gsr";
    final Decoded manifest,selector;
    final SortedMap<String,byte[]> files;
    final long metadata;
    private MembershipGenerationPlan(Decoded manifest,Decoded selector,SortedMap<String,byte[]> files,long metadata) {
        this.manifest=manifest;this.selector=selector;this.files=Collections.unmodifiableSortedMap(files);this.metadata=metadata;
    }
    void verify(Decoded root,MembershipIdentity local,MembershipCurrentGeneration.Verifier verifier,Collection<MembershipCapsule.Anchor> ancestors) {
        var packet=MembershipSourcePacket.decode(files.get("source.gscp"));var images=new TreeMap<String,byte[]>();
        for(String hash:packet.images().keySet())images.put(hash,files.get(hash+".image"));
        var capsule=Objects.requireNonNull(verifier.verify(root,packet,images));
        require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"generation verifier substituted source");
        require(local.equals(capsule.context.identities.get(local.nodeId().value())) && capsule.context.voters().contains(local.nodeId().value()),"installed local eligible identity");
        capsule.verifyAncestry(files.getOrDefault("ancestry.gsr",new byte[0]),ancestors);
        if(files.containsKey(MembershipSelectionCoverage.FILE)) {
            MembershipSelectionCoverage.verify(files.get(MembershipSelectionCoverage.FILE),capsule,
                    decode(files.get("promise.gsr"),"records","PROMISE"),decode(files.get("selected.gsr"),"records","SELECTED"),
                    files.getOrDefault("ancestry.gsr",new byte[0]));return;
        }
        var promise=decode(files.get("promise.gsr"),"records","PROMISE");var body=new TreeMap<>(promise.value());
        body.put("voter",local.nodeId().value());body.put("cut",capsule.context.cut);body.put("capsule",packet.capsule().digest());
        body.put("inventory",packet.inventoryDigest());body.put("accepted",manifest.value().get("ownedTail"));
        packet.bind(decode(encode("records","BASIS",body),"records","BASIS"));
    }
    static byte[] ancestry(List<MembershipSelection.Bridge> bridges) {
        require(bridges.size()<=6,"generation ancestry count");var bytes=new ByteArrayOutputStream();
        for(var bridge:bridges){bytes.writeBytes(bridge.statement.bytes());for(var ack:bridge.acknowledgements)bytes.writeBytes(ack.bytes());}
        require(bytes.size()<=96*1024,"generation ancestry bytes");return bytes.toByteArray();
    }
    /** Complete first-slot materialization. The caller must still own its original journal decision,
     * force the inactive generation/selector, and retire covered state in a separate durable transaction. */
    static MembershipGenerationPlan published(MembershipRoot root,MembershipIdentity local,String slot,Decoded promise,Decoded basis,
            Decoded selected,MembershipCheckpointPlan checkpoint,List<Decoded> acknowledgements,Set<MembershipContext.Owned> observations,
            List<MembershipSelection.Bridge> bridges) {
        require(Set.of("a","b").contains(slot),"publication generation slot");
        require(basis.kind().equals("BASIS") && basis.value().get("voter").equals(local.nodeId().value())
                && Objects.equals(basis.value().get("basisId"),promise.value().get("basisId")),"publication original local basis");
        for(String field:List.of("root","view","ballot"))require(basis.value().get(field).equals(promise.value().get(field)),"publication original basis binding");
        require(list(selected.value().get("sources")).stream().map(MembershipFormat::object).anyMatch(s->s.get("voter").equals(local.nodeId().value())
                && s.get("basisId").equals(basis.value().get("basisId")) && s.get("basisDigest").equals(basis.digest())),"publication missing original selected local source");
        var capsule=checkpoint.publication(acknowledgements,observations,bridges);
        require(capsule.context.root.equals(root.manifestDigest()) && local.equals(capsule.context.identities.get(local.nodeId().value()))
                && capsule.context.voters().contains(local.nodeId().value()),"publication local eligible identity");
        byte[] coverage=MembershipSelectionCoverage.encodeCoverage(selected,checkpoint.originalParent(),checkpoint.originalCertificate());
        byte[] ancestry=ancestry(bridges);MembershipSelectionCoverage.verify(coverage,capsule,promise,selected,ancestry);
        var files=new TreeMap<String,byte[]>();files.put("source.gscp",capsule.packet.bytes());files.put("promise.gsr",promise.bytes());
        files.put("basis.gsr",basis.bytes());files.put("selected.gsr",selected.bytes());files.put(MembershipSelectionCoverage.FILE,coverage);
        if(ancestry.length>0)files.put("ancestry.gsr",ancestry);
        byte[] image=checkpoint.application.image();files.put(hash(image)+".image",image);
        var inventory=new ArrayList<Map<String,Object>>();long metadata=0;
        for(var row:files.entrySet()) {
            inventory.add(Map.of("path",row.getKey(),"size",(long)row.getValue().length,"sha256",hash(row.getValue())));
            if(!row.getKey().endsWith(".image"))metadata=Math.addExact(metadata,row.getValue().length);
        }
        var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("node",local.nodeId().value());value.put("generation",slot);
        for(String field:List.of("cut","application","catalog"))value.put(field,capsule.packet.capsule().value().get(field));
        value.put("capsule",capsule.packet.capsule().digest());value.put("promise",promise.digest());value.put("basis",basis.digest());
        value.put("selection",selected.digest());value.put("ownedTail",null);value.put("files",inventory);
        var manifest=decode(encode("records","GENERATION",value),"records","GENERATION");metadata=Math.addExact(metadata,manifest.bytes().length);
        require(metadata<=MembershipResources.Unit.GENERATION.bytes,"complete generation metadata capacity");files.put(MembershipCurrentGeneration.MANIFEST,manifest.bytes());
        var selector=decode(encode("records","SELECTOR",Map.of("root",root.manifestDigest(),"node",local.nodeId().value(),"generation",slot,"digest",manifest.digest())),"records","SELECTOR");
        return new MembershipGenerationPlan(manifest,selector,files,metadata);
    }
    static MembershipGenerationPlan adopted(MembershipRoot root,MembershipIdentity local,String slot,Decoded promise,
            MembershipCapsule incoming,List<MembershipSelection.Bridge> bridges,Map<String,byte[]> images) {
        require(Set.of("a","b").contains(slot),"generation slot");incoming.packet.verifyImages(images);
        require(local.equals(incoming.context.identities.get(local.nodeId().value())),"adopted local historical identity");
        var certificate=incoming.membershipCertificateFence().orElseThrow(()->new IllegalArgumentException("no authenticated membership certificate fence"));
        require(MembershipContext.compareBallot(object(promise.value().get("ballot")),object(certificate.value().get("ballot")))>=0,"adopted promise below certificate");
        var files=new TreeMap<String,byte[]>();files.put("source.gscp",incoming.packet.bytes());files.put("promise.gsr",promise.bytes());
        files.put(ADOPTION,certificate.bytes());if(!bridges.isEmpty())files.put("ancestry.gsr",ancestry(bridges));
        images.forEach((h,bytes)->files.put(h+".image",bytes));
        var inventory=new ArrayList<Map<String,Object>>();long metadata=0;
        for(var row:files.entrySet()) {
            inventory.add(Map.of("path",row.getKey(),"size",(long)row.getValue().length,"sha256",hash(row.getValue())));
            if(!row.getKey().endsWith(".image"))metadata=Math.addExact(metadata,row.getValue().length);
        }
        var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("node",local.nodeId().value());value.put("generation",slot);
        for(String field:List.of("cut","application","catalog"))value.put(field,incoming.packet.capsule().value().get(field));
        value.put("capsule",incoming.packet.capsule().digest());value.put("promise",promise.digest());value.put("basis",null);
        value.put("selection",null);value.put("ownedTail",null);value.put("files",inventory);
        var manifest=decode(encode("records","GENERATION",value),"records","GENERATION");metadata=Math.addExact(metadata,manifest.bytes().length);
        require(metadata<=MembershipResources.Unit.GENERATION.bytes,"complete generation metadata capacity");files.put(MembershipCurrentGeneration.MANIFEST,manifest.bytes());
        var selector=decode(encode("records","SELECTOR",Map.of("root",root.manifestDigest(),"node",local.nodeId().value(),"generation",slot,"digest",manifest.digest())),"records","SELECTOR");
        return new MembershipGenerationPlan(manifest,selector,files,metadata);
    }
    static MembershipGenerationPlan selected(MembershipRoot root,MembershipIdentity local,String slot,Decoded promise,Decoded basis,
            MembershipSelection.Decision decision,List<MembershipSelection.Bridge> bridges,Map<String,byte[]> images) {
        require(Set.of("a","b").contains(slot) && bridges.size()<=6,"generation slot/ancestry limit");
        var original=decision.longest().capsule.packet;original.verifyImages(images);
        var objects=new TreeMap<String,byte[]>();for(String h:original.objectNames())objects.put(h,original.objectBytes(h));
        String tail=null;
        if(decision.carried()!=null) {
            var carried=decision.carried();tail=carried.accepted.digest();
            for(String h:List.of(tail,carried.entry.digest(),(String)carried.entry.value().get("payload")))objects.put(h,carried.capsule.packet.objectBytes(h));
        }
        var capsule=new TreeMap<>(original.capsule().value());capsule.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",capsule),"records","CAPSULE"),objects,original.images()));
        var files=new TreeMap<String,byte[]>();files.put("source.gscp",packet.bytes());files.put("promise.gsr",promise.bytes());
        files.put("basis.gsr",basis.bytes());files.put("selected.gsr",decision.selected().bytes());
        if(tail!=null)files.put("owned-tail.gsr",packet.objectBytes(tail));
        if(!bridges.isEmpty()) {
            var bytes=new ByteArrayOutputStream();
            for(var bridge:bridges){bytes.writeBytes(bridge.statement.bytes());for(var ack:bridge.acknowledgements)bytes.writeBytes(ack.bytes());}
            require(bytes.size()<=96*1024,"generation ancestry bytes");files.put("ancestry.gsr",bytes.toByteArray());
        }
        // Caller buffers remain bounded input; file hashes are rechecked after writing and before selector publication.
        images.forEach((h,bytes)->files.put(h+".image",bytes));
        var inventory=new ArrayList<Map<String,Object>>();long metadata=0;
        for(var row:files.entrySet()) {
            inventory.add(Map.of("path",row.getKey(),"size",(long)row.getValue().length,"sha256",hash(row.getValue())));
            if(!row.getKey().endsWith(".image"))metadata=Math.addExact(metadata,row.getValue().length);
        }
        var value=new TreeMap<String,Object>();value.put("root",root.manifestDigest());value.put("node",local.nodeId().value());value.put("generation",slot);
        for(String field:List.of("cut","application","catalog"))value.put(field,packet.capsule().value().get(field));
        value.put("capsule",packet.capsule().digest());value.put("promise",promise.digest());value.put("basis",basis.digest());
        value.put("selection",decision.selected().digest());value.put("ownedTail",tail);value.put("files",inventory);
        var manifest=decode(encode("records","GENERATION",value),"records","GENERATION");metadata=Math.addExact(metadata,manifest.bytes().length);
        require(metadata<=MembershipResources.Unit.GENERATION.bytes,"complete generation metadata capacity");
        files.put(MembershipCurrentGeneration.MANIFEST,manifest.bytes());
        var selector=decode(encode("records","SELECTOR",Map.of("root",root.manifestDigest(),"node",local.nodeId().value(),"generation",slot,"digest",manifest.digest())),"records","SELECTOR");
        return new MembershipGenerationPlan(manifest,selector,files,metadata);
    }
}
