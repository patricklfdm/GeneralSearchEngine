package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Pure binding of a retained pending end to the original custody inventory.
 * This reader creates no owner, force observation, vote or deletion authority.
 * It must work after covered retirement, without resampling deleted payloads. */
final class MembershipLearnerPendingLink {
    static final String ROOT="pendingIntent";
    private MembershipLearnerPendingLink() {}
    static Path shape(MembershipLearnerPlan summary,Map<String,Object> link) {
        require(link.keySet().equals(Set.of("directory","directoryKey","plan","planKey","sourceKey","receipt","marker","markerKey","ack","ackKey")),
                "pending custody original link shape");
        Path path=MembershipLearnerPendingIntent.directory(summary);
        require(path.toString().equals(link.get("directory")),"pending custody original directory");
        for(String name:List.of("plan","receipt","marker","ack"))MembershipValidation.digest((String)link.get(name));
        for(String name:List.of("directoryKey","planKey","sourceKey","markerKey","ackKey"))
            require(link.get(name) instanceof String key && !key.isBlank() && key.length()<=4096,"pending custody original inode bound");
        return path;
    }
    static void inventory(MembershipLearnerPlan summary,Map<String,Object> link,List<?> inventory,String receipt) {
        shape(summary,link);require(receipt.equals(link.get("receipt")),"pending custody typed receipt changed");
        var roots=inventory.stream().map(MembershipFormat::object).filter(v->ROOT.equals(v.get("name"))).toList();
        require(roots.size()==1 && Boolean.TRUE.equals(roots.getFirst().get("present")),"pending custody original root missing");
        var files=new TreeMap<String,Map<String,Object>>();
        for(Object raw:list(roots.getFirst().get("files"))) {
            var row=object(raw);require(files.putIfAbsent((String)row.get("name"),object(row.get("identity")))==null,"pending custody duplicate original member");
        }
        directory(files,".",link.get("directoryKey"));directory(files,"source",link.get("sourceKey"));
        member(files,"pending-intent.json",link.get("planKey"),link.get("plan"),MembershipLearnerDisposition.PENDING_MAXIMUM);
        member(files,MembershipLearnerDisposition.PENDING_ACK,link.get("ackKey"),link.get("ack"),2048);
        member(files,MembershipLearnerDisposition.PENDING_SOURCE,link.get("markerKey"),link.get("marker"),MembershipLearnerDisposition.PENDING_SOURCE_MAXIMUM);
        require(files.keySet().stream().filter(n->!n.contains("/")).collect(java.util.stream.Collectors.toSet())
                .equals(Set.of(".","source","pending-intent.json",MembershipLearnerDisposition.PENDING_ACK,MembershipLearnerDisposition.PENDING_SOURCE)),
                "pending custody incomplete/foreign terminal inventory");
    }
    private static void directory(Map<String,Map<String,Object>> files,String name,Object key) {
        var row=files.get(name);require(row!=null && row.equals(Map.of("directory",true,"key",key)),"pending custody directory identity changed");
    }
    private static void member(Map<String,Map<String,Object>> files,String name,Object key,Object digest,int maximum) {
        var row=files.get(name);require(row!=null && row.keySet().equals(Set.of("key","size","sha256"))
                && key.equals(row.get("key")) && digest.equals(row.get("sha256")) && number(row.get("size"))>0 && number(row.get("size"))<=maximum,
                "pending custody member identity changed: "+name);
    }
}
