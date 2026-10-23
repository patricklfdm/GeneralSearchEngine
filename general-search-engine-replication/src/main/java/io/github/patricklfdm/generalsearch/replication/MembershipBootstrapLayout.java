package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Derives initial metadata from exact original frames and the declared image size.
 * This does not verify actual image bytes, typed semantics, ownership or a commit. */
final class MembershipBootstrapLayout {
    final Decoded root,genesis,catalog;
    final MembershipSourcePacket packet;
    final MembershipRoot identity;
    final List<MembershipIdentity> identities;
    final String application;
    final long imageBytes;
    MembershipBootstrapLayout(Decoded suppliedRoot,Decoded suppliedGenesis,long imageBytes) {
        root=decode(suppliedRoot.bytes(),"records","ROOT");genesis=decode(suppliedGenesis.bytes(),"records","GENESIS");
        require(imageBytes>0 && imageBytes<=MembershipApplicationImage.MAXIMUM,"bootstrap layout declared image size");this.imageBytes=imageBytes;
        require(root.value().get("genesis").equals(genesis.digest()),"bootstrap layout original genesis");
        for(String field:List.of("groupId","historyId","baseSequence","schema","indexes"))require(root.value().get(field).equals(genesis.value().get(field)),"bootstrap layout root/genesis binding");
        require(genesis.value().get("source").equals("EMPTY")== (genesis.value().get("sourceDigest")==null),"bootstrap layout source binding");
        require(root.value().get("limits").equals(hash(canonical(CATALOG.get("resources"),16384))),"bootstrap layout resource contract");
        identity=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        MembershipValidation.position(number(genesis.value().get("baseSequence")));
        require(!genesis.value().get("source").equals("EMPTY") || number(genesis.value().get("baseSequence"))==0,"bootstrap layout nonempty EMPTY source");
        identities=MembershipValidation.identities(list(root.value().get("initial")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList(),3,5);
        application=(String)genesis.value().get("application");MembershipValidation.digest(application);
        catalog=frame("CATALOG",MembershipCapsule.initialCatalog(root,genesis.value()));
        var objects=new TreeMap<String,byte[]>();for(var value:List.of(root,genesis,catalog))objects.put(value.digest(),value.bytes());
        var images=Map.of(application,imageBytes);
        var capsule=frame("CAPSULE",Map.of("root",root.rootDigest(),"application",application,"catalog",catalog.digest(),
                "cut",catalog.value().get("cut"),"initial",genesis.digest(),"inventory",hash(MembershipSourcePacket.index(objects,images)),"items",List.of()));
        packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(capsule,objects,images));
    }
    static Decoded frame(String kind,Map<String,Object> value){return decode(encode("records",kind,value),"records",kind);}
    String imagePath(){return "generations/a/"+application+".image";}
    Map<String,byte[]> metadata(MembershipIdentity local) {
        require(identities.contains(local),"bootstrap layout foreign identity");String node=local.nodeId().value(),rootHash=root.rootDigest();var cut=object(catalog.value().get("cut"));
        var p=new TreeMap<String,Object>();p.put("root",rootHash);p.put("view",MembershipContext.viewDigest(rootHash,object(cut.get("view"))));p.put("basisId",null);
        p.put("ballot",Map.of("counter",1L,"proposer",node,"incarnation",local.storageId().toString()));var promise=frame("PROMISE",p);
        var generation=new TreeMap<String,byte[]>();generation.put("source.gscp",packet.bytes());generation.put("promise.gsr",promise.bytes());
        var inventory=new TreeMap<String,Map<String,Object>>();generation.forEach((name,raw)->inventory.put(name,Map.of("path",name,"size",(long)raw.length,"sha256",hash(raw))));
        inventory.put(application+".image",Map.of("path",application+".image","size",imageBytes,"sha256",application));
        var m=new TreeMap<String,Object>();m.put("root",rootHash);m.put("node",node);m.put("generation","a");m.put("cut",cut);
        m.put("application",application);m.put("catalog",catalog.digest());m.put("capsule",packet.capsule().digest());m.put("promise",promise.digest());
        m.put("basis",null);m.put("selection",null);m.put("ownedTail",null);m.put("files",new ArrayList<>(inventory.values()));
        var manifest=frame("GENERATION",m);generation.put("generation.gsr",manifest.bytes());var files=new TreeMap<String,byte[]>();
        generation.forEach((name,raw)->files.put("generations/a/"+name,raw));
        files.put("replica.lock",new byte[0]);files.put("root.gsr",root.bytes());files.put("genesis.gsr",genesis.bytes());
        files.put("node.gsr",encode("records","NODE",Map.of("identity",MembershipBootstrapSeed.identity(local),"root",rootHash)));
        files.put(MembershipBallotAllocator.CURRENT,encode("records","ALLOCATOR",Map.of("counter",1L,"node",node,"root",rootHash)));
        files.put("grants.gsr",promise.bytes());files.put(MembershipPendingAccept.FILE,MembershipPendingAccept.empty());
        files.put("selector.gsr",encode("records","SELECTOR",Map.of("root",rootHash,"node",node,"generation","a","digest",manifest.digest())));
        return Collections.unmodifiableMap(files);
    }
    List<Map<String,Object>> inventory(MembershipIdentity local) {
        var result=new TreeMap<String,Map<String,Object>>();metadata(local).forEach((name,raw)->result.put(name,Map.of("path",name,"bytes",(long)raw.length,"sha256",hash(raw))));
        result.put(imagePath(),Map.of("path",imagePath(),"bytes",imageBytes,"sha256",application));return List.copyOf(result.values());
    }
}
