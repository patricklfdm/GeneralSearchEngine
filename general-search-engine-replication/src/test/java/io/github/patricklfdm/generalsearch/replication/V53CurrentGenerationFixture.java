package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

/** Physical selected-generation fixture, not a bootstrap or installation implementation. */
final class V53CurrentGenerationFixture {
    final int size;final V53CapsuleFixture fixture;final MembershipCapsule admitted;final String accepted;
    V53CurrentGenerationFixture(int size,int through,boolean tail) {
        this.size=size;var selection=new V53SelectionFixture(size,"REPLACE",through);fixture=selection.capsule;
        if(tail){var source=selection.source("node-1",10,"owned-original-tail",3);admitted=source.capsule;accepted=source.accepted.digest();}
        else{admitted=fixture.verify();accepted=null;}
    }
    MembershipRoot root(){return V53BallotAllocatorWorker.root(fixture.source);}
    MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images) {
        return MembershipCapsule.verify(root,packet,images,fixture.owned);
    }
    void provision(Path path) throws Exception {
        V53BallotAllocatorWorker.provision(path,size);Files.createDirectory(path.resolve("sources"));
        var promise=decode(encode("records","PROMISE",map("root",root().manifestDigest(),"view",admitted.context.authority(),
                "ballot",fixture.source.ballot(10),"basisId",new UUID(0,100).toString())),"records","PROMISE");
        AdmissionPaths.write(path.resolve("grants.gsr"),promise.bytes());
        Path directory=path.resolve("generations");Files.createDirectory(directory);Path generation=directory.resolve("a");Files.createDirectory(generation);
        var files=new TreeMap<String,byte[]>();files.put("source.gscp",admitted.packet.bytes());files.put("promise.gsr",promise.bytes());
        fixture.source.images.forEach((hash,bytes)->files.put(hash+".image",bytes));
        if(accepted!=null)files.put("owned-tail.gsr",admitted.packet.objectBytes(accepted));
        var inventory=new ArrayList<Map<String,Object>>();
        for(var row:files.entrySet()) {
            AdmissionPaths.write(generation.resolve(row.getKey()),row.getValue());
            inventory.add(map("path",row.getKey(),"size",(long)row.getValue().length,"sha256",hash(row.getValue())));
        }
        var manifest=decode(encode("records","GENERATION",map("root",root().manifestDigest(),"node","node-1","generation","a",
                "cut",admitted.context.cut,"application",admitted.terminal().application(),"catalog",admitted.terminal().catalog(),
                "capsule",admitted.packet.capsule().digest(),"promise",promise.digest(),"basis",null,"selection",null,"ownedTail",accepted,"files",inventory)),"records","GENERATION");
        AdmissionPaths.write(generation.resolve("generation.gsr"),manifest.bytes());AdmissionPaths.forceDirectory(directory);
        AdmissionPaths.write(path.resolve("selector.gsr"),encode("records","SELECTOR",map("root",root().manifestDigest(),"node","node-1","generation","a","digest",manifest.digest())));
    }
}
