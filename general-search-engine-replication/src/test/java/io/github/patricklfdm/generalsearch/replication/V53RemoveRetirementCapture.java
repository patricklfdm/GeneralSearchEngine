package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Writer-held observations only. The sidecar cannot authorize a runtime action
 * and never changes the original callback trace or owned replica files. */
final class V53RemoveRetirementCapture {
    static final int MAXIMUM_CAPTURES=2048;
    static final String SCHEMA="gse-v53-remove-retirement-capture-v1";
    static final String CARRIED_SCHEMA="gse-v53-carried-retirement-capture-v1";
    static final String PROCESS_SCHEMA="gse-v53-carried-process-retirement-capture-v1";
    final Path raw,root;
    private final Path objects;
    private final Map<String,String> active=new HashMap<>();
    private final Map<String,Integer> previous=new HashMap<>();
    private long bytes;
    private int count;
    private boolean finished;
    V53RemoveRetirementCapture(Path raw)throws IOException {
        this(raw,raw.resolveSibling("retirement-captures-"+raw.getFileName()));
    }
    V53RemoveRetirementCapture(Path raw,Path directory)throws IOException {
        this.raw=raw;root=Files.createDirectory(directory);
        objects=Files.createDirectory(root.resolve("objects"));
    }
    synchronized void at(String node,Path replica,String point,int eventIndex)throws IOException {
        boolean generation=point.startsWith("RETIREMENT_"),source=point.startsWith("SOURCE_RETIREMENT_");
        if(!generation && !source && !(point.startsWith("JOURNAL_ROTATION_") && "source".equals(active.get(node))))return;
        require(!finished && eventIndex>=0 && eventIndex>previous.getOrDefault(node,-1),"REMOVE capture event lifetime");
        String kind=generation?"generation":"source";
        if(point.equals("RETIREMENT_OLD_FILES_FORCED") || point.equals("SOURCE_RETIREMENT_CREATED")) {
            require(!active.containsKey(node),"REMOVE capture overlapping transaction");active.put(node,kind);
        }
        require(kind.equals(active.get(node)),"REMOVE capture original transaction start");
        require(count<MAXIMUM_CAPTURES,"REMOVE capture count capacity");
        var before=V53GrantCapture.inventory(replica);
        for(var item:before.entrySet()) {
            var identity=object(item.getValue());if(identity.containsKey("directory"))continue;
            byte[] value=AdmissionPaths.read(replica.resolve(item.getKey()),V53GrantCapture.MAXIMUM_FILE);
            require(value.length==number(identity.get("size")) && hash(value).equals(identity.get("sha256")),"REMOVE capture original changed");
            Path target=objects.resolve((String)identity.get("sha256"));
            if(Files.exists(target,LinkOption.NOFOLLOW_LINKS))AdmissionPaths.exact(target,value);
            else {charge(value.length);Files.write(target,value,StandardOpenOption.CREATE_NEW);}
        }
        require(before.equals(V53GrantCapture.inventory(replica)),"REMOVE capture original changed");
        var metadata=new TreeMap<String,Object>();metadata.put("schema",SCHEMA);metadata.put("node",node);
        metadata.put("point",point);metadata.put("eventIndex",eventIndex);metadata.put("kind",kind);
        metadata.put("files",before.entrySet().stream().map(e->Map.of("name",e.getKey(),"identity",e.getValue())).toList());
        byte[] encoded=canonical(metadata,1024*1024);charge(encoded.length);
        Files.write(root.resolve(String.format(Locale.ROOT,"capture-%04d.json",++count)),encoded,StandardOpenOption.CREATE_NEW);
        previous.put(node,eventIndex);
        if(point.equals("RETIREMENT_BEFORE_RETURN") || point.equals("SOURCE_RETIREMENT_BEFORE_RETURN"))active.remove(node);
    }
    private void charge(long extent) {
        require(extent>=0 && extent<=V53GrantCapture.MAXIMUM_BYTES-bytes,"REMOVE capture aggregate byte capacity");bytes+=extent;
    }
    synchronized void finish(String profile)throws IOException {
        require(Set.of("4-REMOVE","5-REMOVE").contains(profile),"REMOVE capture profile");
        finish(SCHEMA,profile,"transition-round-result.json");
    }
    synchronized void finishCarried(String kind)throws IOException {
        require(Set.of("INTENT","FINAL").contains(kind),"carried capture kind");
        finish(CARRIED_SCHEMA,kind,"carried-transition-result.json");
    }
    synchronized void finishProcess(String history,int life,String terminal,byte[] events)throws IOException {
        MembershipValidation.digest(history);
        require(!finished && active.isEmpty() && (life==1 && terminal.equals("CUT_PREFIX") || life==2 && terminal.equals("CLOSED")),
                "process retirement original terminal");
        // INTENT/ACCEPT can die before the first retirement. Empty coverage is
        // explicit and must match the original callback inventory in replay.
        Files.write(root.resolve("collection.json"),canonical(Map.of("schema",PROCESS_SCHEMA,"root",history,
                "life",life,"pid",ProcessHandle.current().pid(),"terminal",terminal,"eventsSha256",hash(events),
                "captures",count,"storedBytes",bytes),4096),StandardOpenOption.CREATE_NEW);
        finished=true;
    }
    private void finish(String schema,String profile,String resultName)throws IOException {
        require(!finished && active.isEmpty() && count>0,"REMOVE capture incomplete collection");
        byte[] events=AdmissionPaths.read(raw.resolve("events.json"),32*1024*1024);
        byte[] result=AdmissionPaths.read(raw.resolve(resultName),4096);
        byte[] collection=canonical(Map.of("schema",schema,"profile",profile,"eventsSha256",hash(events),
                "resultSha256",hash(result),"captures",count,"storedBytes",bytes),4096);
        Files.write(root.resolve("collection.json"),collection,StandardOpenOption.CREATE_NEW);finished=true;
    }
}
