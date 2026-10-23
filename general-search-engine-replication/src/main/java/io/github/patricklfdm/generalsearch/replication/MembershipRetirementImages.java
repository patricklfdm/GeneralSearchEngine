package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private exact reference to images already owned by the pinned local governing-floor copy.
 * No alias file, copied image, new voter observation, or deletion authority is created here. */
final class MembershipRetirementImages {
    static final String FILE="images.json", SCHEMA="gse-v53-retirement-floor-images-v1";
    static final int MAXIMUM=65536;
    private static MembershipFloor.Copy local(Decoded record,MembershipFloorFiles.Retained floor) {
        require(record.value().get("floor").equals(floor.floor().digest()),"retirement borrowed floor changed");
        return floor.copies().stream().filter(c->c.owner.nodeId().value().equals(record.value().get("node")))
                .findFirst().orElseThrow(()->new IllegalArgumentException("retirement borrowed local copy absent"));
    }
    private static List<Map<String,Object>> images(Decoded record,MembershipFloor.Copy local) {
        var result=new ArrayList<Map<String,Object>>();String previous=null;
        for(Object raw:list(record.value().get("files"))) {
            var file=object(raw);String path=(String)file.get("path");
            if(!path.endsWith(".image"))continue;
            require(path.matches("generations/[ab]/[0-9a-f]{64}\\.image") && (previous==null || previous.compareTo(path)<0),"retirement borrowed image path/order");previous=path;
            String name=path.substring(path.lastIndexOf('/')+1);long size=number(file.get("size"));
            require(size>0 && size<=MembershipResources.Unit.APPLICATION.bytes && name.equals(file.get("sha256")+".image"),"retirement borrowed image inventory");
            require(local.fileNames().contains(name),"retirement original image absent from local floor");byte[] bytes=local.fileBytes(name);
            require(bytes.length==size && hash(bytes).equals(file.get("sha256")),"retirement borrowed image differs from original");
            result.add(Map.of("path",path,"generation",local.generation.digest(),"size",size,"sha256",file.get("sha256")));
        }
        require(!result.isEmpty() && result.size()<=7,"retirement borrowed image count");return List.copyOf(result);
    }
    static byte[] create(Decoded record,MembershipFloorFiles.Retained floor) {
        var local=local(record,floor);local.check();
        return canonical(Map.of("schema",SCHEMA,"retirement",record.digest(),"floor",floor.floor().digest(),
                "root",record.value().get("root"),"node",record.value().get("node"),"storage",local.owner.storageId().toString(),
                "selector",record.value().get("selector"),"images",images(record,local)),MAXIMUM);
    }
    static Map<String,byte[]> resolve(byte[] binding,Decoded record,MembershipFloorFiles.Retained floor) {
        // Equality with a completely derived canonical binding checks every field, type and path;
        // no caller path is resolved on disk and no semantically equivalent image is accepted.
        require(binding.length>0 && binding.length<=MAXIMUM,"retirement borrowed binding capacity");
        require(Arrays.equals(binding,create(record,floor)),"retirement borrowed binding differs from original floor/inventory");
        var local=local(record,floor);var result=new TreeMap<String,byte[]>();
        for(var row:images(record,local)) {String path=(String)row.get("path");String name=path.substring(path.lastIndexOf('/')+1);result.put(name,local.fileBytes(name));}
        return Collections.unmodifiableMap(result);
    }
    private MembershipRetirementImages() {}
}
