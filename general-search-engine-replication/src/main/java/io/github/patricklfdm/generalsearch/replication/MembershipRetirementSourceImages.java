package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact old images from the original BASIS pinned by the local floor generation.
 * This does not create a copy or permit retiring its backing source. */
final class MembershipRetirementSourceImages {
    static final String SCHEMA="gse-v53-retirement-source-images-v1";
    static Decoded basis(Decoded record,MembershipFloorFiles.Retained floor) {
        var local=MembershipRetirementImages.local(record,floor);local.check();
        require(local.fileNames().contains("basis.gsr"),"retirement source backing requires original local BASIS");
        var basis=decode(local.fileBytes("basis.gsr"),"records","BASIS");
        require(basis.digest().equals(local.generation.value().get("basis")) && basis.value().get("voter").equals(record.value().get("node")),"retirement source backing local identity");
        return basis;
    }
    static Map<String,byte[]> images(Decoded record,MembershipFloorFiles.Retained floor,MembershipBasisSources sources)throws IOException {
        require(sources!=null,"retirement source backing owner absent");var original=sources.original(basis(record,floor));var images=new TreeMap<String,byte[]>();String previous=null;
        for(Object raw:list(record.value().get("files"))) {
            var file=object(raw);String path=(String)file.get("path");if(!path.endsWith(".image"))continue;
            require(path.matches("generations/[ab]/[0-9a-f]{64}\\.image") && (previous==null || previous.compareTo(path)<0),"retirement source image path/order");previous=path;
            String name=path.substring(path.lastIndexOf('/')+1),digest=(String)file.get("sha256");long size=number(file.get("size"));
            require(name.equals(digest+".image") && size>0 && size<=MembershipResources.Unit.APPLICATION.bytes,"retirement source image inventory");
            byte[] bytes=original.images().get(digest);require(bytes!=null && bytes.length==size && hash(bytes).equals(digest),"retirement exact image absent from pinned original source");images.put(name,bytes);
        }
        require(!images.isEmpty() && images.size()<=7,"retirement source image count");return Collections.unmodifiableMap(images);
    }
    static byte[] create(Decoded record,MembershipFloorFiles.Retained floor,MembershipBasisSources sources)throws IOException {
        var local=MembershipRetirementImages.local(record,floor);var basis=basis(record,floor);var bytes=images(record,floor,sources);var rows=new ArrayList<Map<String,Object>>();
        for(Object raw:list(record.value().get("files"))) {var file=object(raw);if(((String)file.get("path")).endsWith(".image"))rows.add(file);}
        require(rows.size()==bytes.size(),"retirement source image duplicate");
        return canonical(Map.of("schema",SCHEMA,"retirement",record.digest(),"floor",floor.floor().digest(),"root",record.value().get("root"),
                "node",record.value().get("node"),"storage",local.owner.storageId().toString(),"selector",record.value().get("selector"),
                "generation",local.generation.digest(),"basis",basis.digest(),"images",rows),MembershipRetirementImages.MAXIMUM);
    }
    static Map<String,byte[]> resolve(byte[] binding,Decoded record,MembershipFloorFiles.Retained floor,MembershipBasisSources sources)throws IOException {
        require(Arrays.equals(binding,create(record,floor,sources)),"retirement source image binding differs from pinned originals");return images(record,floor,sources);
    }
    private MembershipRetirementSourceImages() {}
}
