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
    private final boolean controlCloses,exportOwnership;
    private final Map<String,Owner> owners=new TreeMap<>();
    private final List<Map<String,Object>> boundaries=new ArrayList<>();
    private final List<String> closingOwners;
    private final Set<String> closing=new HashSet<>();
    private boolean saved;
    V53ResourceTransitionCapture(Path raw,String root)throws IOException {
        this(raw,root,List.of());
    }
    V53ResourceTransitionCapture(Path raw,String root,List<String> closingOwners)throws IOException {
        this(raw,root,closingOwners,false);
    }
    V53ResourceTransitionCapture(Path raw,String root,List<String> closingOwners,boolean controlCloses)throws IOException {
        this(raw,root,closingOwners,controlCloses,false);
    }
    V53ResourceTransitionCapture(Path raw,String root,List<String> closingOwners,boolean controlCloses,boolean exportOwnership)throws IOException {
        require(closingOwners.size()<=6 && closingOwners.equals(closingOwners.stream().distinct().sorted().toList()) &&
                closingOwners.stream().allMatch(n->n.matches("node-[1-6]")),"resource close original owners");
        this.closingOwners=List.copyOf(closingOwners);
        require(!exportOwnership || controlCloses,"export ownership requires close capture");
        this.controlCloses=controlCloses;this.exportOwnership=exportOwnership;
        MembershipValidation.digest(root);this.root=root;directory=Files.createDirectory(raw.resolve(DIRECTORY));
    }
    void closeOwner(MembershipGrantJournal journal,List<Map<String,Object>> events)throws IOException {
        String node=journal.activationIdentity().nodeId().value();
        if(closingOwners.isEmpty()){journal.close();return;}
        // Opt-in whole-owner fixtures call this only after endpoint/transport
        // shutdown. Never label a second close as the original owner lifetime.
        synchronized(events) {
            synchronized(this) {
                require(!saved && closingOwners.contains(node) && owners.containsKey(node) && closing.add(node),"resource close owner invocation");
            }
            journal.activationContext(); // A previously closed owner must fail before BEGIN.
            events.add(Map.of("node",node,"event","RESOURCE_OWNER_CLOSE_BEGIN"));
        }
        journal.close(); // An exception deliberately leaves no successful RETURNED marker.
        synchronized(events) {events.add(Map.of("node",node,"event","RESOURCE_OWNER_CLOSE_RETURNED"));}
    }
    synchronized MembershipResources create(MembershipIdentity identity,int eventIndex) {
        String node=identity.nodeId().value();
        require(!saved && node.matches("node-[1-9][0-9]*") && !owners.containsKey(node) && owners.size()<6 && eventIndex==boundaries.size(),
                "resource capture owner registration");
        var budget=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM,
                controlCloses?MembershipControlCloseObservations.MAXIMUM:0,exportOwnership);
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
        saveDigest(hash(events));
    }
    synchronized void save(V53EvidenceSpool events)throws IOException {
        saveDigest(events.sealedSha256(directory.getParent().resolve("events.json")));
    }
    private void saveDigest(String eventsSha256)throws IOException {
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
        var index=new TreeMap<String,Object>(Map.of("schema",closingOwners.isEmpty()?"gse-v53-resource-capture-index-v1":"gse-v53-resource-capture-index-v2","root",root,
                "eventsSha256",eventsSha256,"boundariesSha256",hash(data),"owners",refs));
        if(!closingOwners.isEmpty())index.put("closingOwners",closingOwners);
        Files.write(directory.resolve("index.json"),canonical(index,16384),StandardOpenOption.CREATE_NEW);
        if(Boolean.getBoolean("v53.resource.storage.transfers")) {
            Path transfers=Files.createDirectory(directory.getParent().resolve("storage-transfer-captures"));
            var transferRefs=new ArrayList<Map<String,Object>>();
            for(var ref:refs) {
                String name=(String)ref.get("path");var identity=object(ref.get("identity"));
                String digest=V53ResourceTraceFiles.writeTransfers(transfers.resolve(name),owners.get(identity.get("node")).budget.storageTransferObservations());
                transferRefs.add(Map.of("identity",identity,"path",name,"sha256",digest,"resourceSha256",ref.get("sha256")));
            }
            Files.write(transfers.resolve("index.json"),canonical(Map.of("schema","gse-v53-storage-transfer-capture-v1","root",root,
                    "eventsSha256",eventsSha256,"owners",transferRefs),16384),StandardOpenOption.CREATE_NEW);
        }
        if(controlCloses) {
            Path closeDirectory=Files.createDirectory(directory.getParent().resolve("control-close-captures"));
            var closeRefs=new ArrayList<Map<String,Object>>();
            for(var ref:refs) {
                String name=(String)ref.get("path");var identity=object(ref.get("identity"));
                String digest=V53ResourceTraceFiles.writeCloses(closeDirectory.resolve(name),owners.get(identity.get("node")).budget.controlCloseObservations());
                closeRefs.add(Map.of("identity",identity,"path",name,"sha256",digest,"resourceSha256",ref.get("sha256")));
            }
            Files.write(closeDirectory.resolve("index.json"),canonical(Map.of("schema","gse-v53-control-close-capture-v1","root",root,
                    "eventsSha256",eventsSha256,"owners",closeRefs),16384),StandardOpenOption.CREATE_NEW);
        }
    }
}
