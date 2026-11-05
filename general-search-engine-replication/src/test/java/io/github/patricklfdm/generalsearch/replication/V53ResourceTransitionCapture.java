package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One actual budget per original disk owner, from native open through final close.
 * Invoked by the fixture event append, never from the resource monitor itself. */
final class V53ResourceTransitionCapture {
    static final String DIRECTORY="resource-transition-captures";
    private record Owner(MembershipIdentity identity,MembershipResources budget,int registeredAt) {}
    private final String root;
    private final Path directory;
    private final Map<String,Owner> owners=new TreeMap<>();
    private final List<Map<String,Object>> boundaries=new ArrayList<>();
    private boolean saved;
    V53ResourceTransitionCapture(Path raw,String root)throws IOException {
        MembershipValidation.digest(root);this.root=root;directory=Files.createDirectory(raw.resolve(DIRECTORY));
    }
    synchronized MembershipResources create(MembershipIdentity identity,int eventIndex) {
        String node=identity.nodeId().value();
        require(!saved && node.matches("node-[1-9][0-9]*") && !owners.containsKey(node) && owners.size()<6 && eventIndex==boundaries.size(),
                "resource capture owner registration");
        var budget=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
        owners.put(node,new Owner(identity,budget,eventIndex));return budget;
    }
    synchronized void event(int index,Map<String,Object> event) {
        require(!saved && index==boundaries.size() && index<V53EvidenceArray.HISTORY_ROWS,"resource capture event capacity/order");
        var node=event.get("node");var owner=owners.get(node);
        require(owner!=null && event.get("event") instanceof String,"resource capture unknown event owner");
        var value=owner.budget.observationCheckpoint();
        require(value.complete(),"resource capture incomplete observation");
        boundaries.add(Map.of("eventIndex",index,"node",node,"sequence",value.sequence(),"usage",V53ResourceTraceFiles.usage(value.usage())));
    }
    synchronized void save(byte[] events)throws IOException {
        require(!saved && !owners.isEmpty(),"resource capture already saved/empty");saved=true;
        var refs=new ArrayList<Map<String,Object>>();
        for(var entry:owners.entrySet()) {
            var owner=entry.getValue();var value=owner.budget.observations();String name=entry.getKey()+".json";
            // Write the original even if it cannot qualify; never relabel a partial close.
            String digest=V53ResourceTraceFiles.write(directory.resolve(name),value);
            refs.add(Map.of("identity",MembershipBootstrapSeed.identity(owner.identity),"path",name,"sha256",digest,"registeredAt",owner.registeredAt));
        }
        byte[] data=V53EvidenceArray.encode(boundaries,32*1024*1024);
        Files.write(directory.resolve("boundaries.json"),data,StandardOpenOption.CREATE_NEW);
        Files.write(directory.resolve("index.json"),canonical(Map.of("schema","gse-v53-resource-capture-index-v1","root",root,
                "eventsSha256",hash(events),"boundariesSha256",hash(data),"owners",refs),16384),StandardOpenOption.CREATE_NEW);
    }
}
