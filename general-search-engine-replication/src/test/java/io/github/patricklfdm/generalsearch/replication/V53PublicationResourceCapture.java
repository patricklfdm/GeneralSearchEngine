package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test-only original writer observations. Captured bytes confer no authority.
 * No receiving lifetime, resource limit or runtime deadline is changed. */
final class V53PublicationResourceCapture {
    static final String DIRECTORY="publication-resource-captures";
    static final List<String> POINTS=List.of("PUBLICATION_VALIDATED","INSTALL_RESERVED","INSTALL_PARENT_FORCED",
        "CURRENT_VALIDATED","CURRENT_FILES_FORCED","CURRENT_GENERATION_FORCED","CURRENT_SELECTOR_FORCED",
        "CURRENT_DIRECTORY_FORCED","PUBLICATION_SELECTOR_FORCED","PUBLICATION_RETIRED","PUBLICATION_BEFORE_RETURN");
    static final int MAXIMUM_CAPTURES=1024;
    private final Path root,objects;
    private final List<Map<String,Object>> rows=new ArrayList<>();
    private final Set<String> active=new HashSet<>();
    private final V53CaptureFiles.ObjectStore streamed;
    private long bytes;
    V53PublicationResourceCapture(Path raw)throws IOException {
        this(raw,MembershipBootstrapSource.EMPTY,V53WireArchive.Layout.JSON);
    }
    V53PublicationResourceCapture(Path raw,MembershipBootstrapSource source,V53WireArchive.Layout layout)throws IOException {
        boolean segmented=V53CaptureFiles.segmented(source,layout);
        root=Files.createDirectory(raw.resolve(DIRECTORY));objects=Files.createDirectory(root.resolve("objects"));
        streamed=segmented?new V53CaptureFiles.ObjectStore(objects):null;
    }
    static Map<String,Object> storage(MembershipResources.Usage use) {
        var counts=new TreeMap<String,Object>();
        use.counts().forEach((unit,count)->{if(unit!=MembershipResources.Unit.CONTROL && unit!=MembershipResources.Unit.WAITER)counts.put(unit.name(),count);});
        return Map.of("metadata",use.metadata(),"staging",use.staging(),"counts",counts,
            "leases",counts.values().stream().mapToInt(v->(Integer)v).sum());
    }
    synchronized void at(String node,String scope,Path replica,MembershipResources resources,String point,int eventIndex)throws IOException {
        String owner=node+":"+scope;
        if(point.equals("PUBLICATION_VALIDATED"))require(active.add(owner),"publication capture overlapping operation");
        if(!active.contains(owner) || !POINTS.contains(point))return;
        require(eventIndex>=0 && rows.size()<MAXIMUM_CAPTURES,"publication capture event/count capacity");
        var before=resources.usage();var snapshot=streamed==null?null:new V53CaptureFiles(replica);
        var files=snapshot==null?V53GrantCapture.inventory(replica):snapshot.inventory();
        if(streamed!=null)streamed.retain(snapshot);
        else for(var item:files.entrySet()) {
            var identity=object(item.getValue());if(identity.containsKey("directory"))continue;
            byte[] raw=AdmissionPaths.read(replica.resolve(item.getKey()),V53GrantCapture.MAXIMUM_FILE);
            require(raw.length==number(identity.get("size")) && hash(raw).equals(identity.get("sha256")),"publication capture original changed");
            Path target=objects.resolve((String)identity.get("sha256"));
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))AdmissionPaths.exact(target,raw);
            else {
                require(raw.length<=V53GrantCapture.MAXIMUM_BYTES-bytes,"publication capture aggregate capacity");
                Files.write(target,raw,StandardOpenOption.CREATE_NEW);bytes+=raw.length;
            }
        }
        if(streamed==null)require(files.equals(V53GrantCapture.inventory(replica)),"publication capture original changed");
        var after=resources.usage();require(storage(before).equals(storage(after)),"publication capture storage changed during observation");
        var value=new TreeMap<String,Object>();value.put("schema","gse-v53-publication-resource-capture-v1");
        value.put("node",node);value.put("scope",scope);value.put("point",point);value.put("eventIndex",eventIndex);
        value.put("usageBefore",V53PublicationReservationTest.usage(before));value.put("usageAfter",V53PublicationReservationTest.usage(after));
        value.put("files",files.entrySet().stream().map(e->Map.of("name",e.getKey(),"identity",e.getValue())).toList());
        byte[] encoded=canonical(value,1024*1024);String name=String.format(Locale.ROOT,"capture-%04d.json",rows.size());
        Files.write(root.resolve(name),encoded,StandardOpenOption.CREATE_NEW);rows.add(Map.of("path",name,"sha256",hash(encoded)));
        if(point.equals("PUBLICATION_BEFORE_RETURN"))active.remove(owner);
    }
    synchronized void save()throws IOException {
        Files.write(root.resolve("index.json"),canonical(Map.of("schema","gse-v53-publication-resource-index-v1",
            "complete",active.isEmpty(),"captures",rows),1024*1024),StandardOpenOption.CREATE_NEW);
    }
}
