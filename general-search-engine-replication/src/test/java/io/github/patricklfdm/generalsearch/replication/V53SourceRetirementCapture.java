package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test-only writer-held prefixes; retained copies never authorize deletion.
 * Content addressing avoids copying every unchanged application at every cut. */
final class V53SourceRetirementCapture {
    static final String DIRECTORY="source-retirement-captures",EVENT="SOURCE_RETIREMENT_CAPTURED";
    static final int MAXIMUM_CAPTURES=512;
    private final Path root,objects;
    private final List<Map<String,Object>> events;
    private final Map<String,String> active=new HashMap<>();
    private long bytes;
    private int count;
    V53SourceRetirementCapture(Path raw,List<Map<String,Object>> events)throws IOException {
        root=Files.createDirectory(raw.resolve(DIRECTORY));objects=Files.createDirectory(root.resolve("objects"));this.events=Objects.requireNonNull(events);
    }
    synchronized void at(String node,String scope,Path replica,String point)throws IOException {
        boolean source=point.startsWith("SOURCE_RETIREMENT_");
        if(!source && !(point.startsWith("JOURNAL_ROTATION_") && active.containsKey(node)))return;
        if(point.equals("SOURCE_RETIREMENT_CREATED")) {
            require(!active.containsKey(node),"retirement capture overlapping transaction");active.put(node,scope);
        }
        require(scope.equals(active.get(node)),"retirement capture original start/scope");
        require(count<MAXIMUM_CAPTURES,"retirement capture count capacity");
        var before=V53GrantCapture.inventory(replica);
        for(var item:before.entrySet()) {
            var identity=object(item.getValue());if(identity.containsKey("directory"))continue;
            byte[] raw=AdmissionPaths.read(replica.resolve(item.getKey()),V53GrantCapture.MAXIMUM_FILE);
            require(raw.length==number(identity.get("size")) && hash(raw).equals(identity.get("sha256")),"retirement capture original changed");
            Path target=objects.resolve((String)identity.get("sha256"));
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))AdmissionPaths.exact(target,raw);
            else {
                require(raw.length<=V53GrantCapture.MAXIMUM_BYTES-bytes,"retirement capture aggregate byte capacity");
                Files.write(target,raw,StandardOpenOption.CREATE_NEW);bytes+=raw.length;
            }
        }
        require(before.equals(V53GrantCapture.inventory(replica)),"retirement capture original changed");
        var metadata=new TreeMap<String,Object>();metadata.put("schema","gse-v53-source-retirement-capture-v1");
        metadata.put("node",node);metadata.put("scope",scope);metadata.put("point",point);
        metadata.put("files",before.entrySet().stream().map(e->Map.of("name",e.getKey(),"identity",e.getValue())).toList());
        byte[] encoded=canonical(metadata,1024*1024);String name=String.format(Locale.ROOT,"capture-%04d.json",++count);
        Files.write(root.resolve(name),encoded,StandardOpenOption.CREATE_NEW);
        events.add(Map.of("node",node,"scope",scope,"event",EVENT,"point",point,"capture",DIRECTORY+"/"+name,"sha256",hash(encoded)));
        if(point.equals("SOURCE_RETIREMENT_BEFORE_RETURN"))active.remove(node);
    }
}
