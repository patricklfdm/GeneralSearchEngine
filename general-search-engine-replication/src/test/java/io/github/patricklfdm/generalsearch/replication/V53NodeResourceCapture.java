package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Actual node budgets, not a second accounting pool. A forced process death
 * retains a bounded prefix; only a real successful close can claim CLOSED. */
final class V53NodeResourceCapture implements V53NodeProcessWorker.Sink {
    private record Owner(MembershipIdentity identity,MembershipNodeOwner<?,?> node,int registeredAt,Path replica) {}
    private final Path directory;
    private final String root;
    private final int life;
    private final V53NodeProcessWorker.Sink sink;
    private final V53RemoveRetirementCapture retirement,floor,campaign;
    private final Map<String,Owner> owners=new TreeMap<>();
    private final List<Map<String,Object>> events=new ArrayList<>(),boundaries=new ArrayList<>(),closes=new ArrayList<>();
    private final Set<String> closing=new HashSet<>(),closed=new HashSet<>();
    private boolean saved;
    V53NodeResourceCapture(Path directory,String root,int life,V53NodeProcessWorker.Sink sink)throws IOException {
        this(directory,root,life,sink,null);
    }
    V53NodeResourceCapture(Path directory,String root,int life,V53NodeProcessWorker.Sink sink,Path retirementDirectory)throws IOException {
        this(directory,root,life,sink,retirementDirectory,null);
    }
    V53NodeResourceCapture(Path directory,String root,int life,V53NodeProcessWorker.Sink sink,Path retirementDirectory,Path floorDirectory)throws IOException {
        this(directory,root,life,sink,retirementDirectory,floorDirectory,null);
    }
    V53NodeResourceCapture(Path directory,String root,int life,V53NodeProcessWorker.Sink sink,Path retirementDirectory,Path floorDirectory,Path campaignDirectory)throws IOException {
        MembershipValidation.digest(root);require(life==1 || life==2,"node resource original life");
        this.directory=Files.createDirectory(directory);this.root=root;this.life=life;this.sink=Objects.requireNonNull(sink);
        retirement=retirementDirectory==null?null:new V53RemoveRetirementCapture(directory,retirementDirectory);
        floor=floorDirectory==null?null:new V53RemoveRetirementCapture(directory,floorDirectory,true);
        campaign=campaignDirectory==null?null:new V53RemoveRetirementCapture(directory,campaignDirectory,V53RemoveRetirementCapture.Mode.CAMPAIGN);
    }
    synchronized void register(MembershipIdentity identity,MembershipNodeOwner<?,?> node) {
        register(identity,node,null);
    }
    synchronized void register(MembershipIdentity identity,MembershipNodeOwner<?,?> node,Path replica) {
        String name=identity.nodeId().value();var point=node.resourceCheckpoint();
        require(!saved && owners.size()<4 && !owners.containsKey(name) && node.state()==MembershipNodeOwner.State.NEW &&
                point.complete() && point.sequence()==0 && point.usage().leases()==0 && (retirement==null && floor==null && campaign==null || replica!=null),"node resource original registration");
        owners.put(name,new Owner(identity,node,events.size(),replica));
    }
    @Override public synchronized void accept(String action,Object value)throws IOException {
        if(!saved && (action.equals("event") || action.equals("response"))) {
            var event=object(action.equals("event")?value:object(value).get("event"));var owner=owners.get(event.get("node"));
            require(owner!=null && events.size()<V53EvidenceArray.HISTORY_ROWS,"node resource original event owner/bound");
            var point=owner.node.resourceCheckpoint();require(point.complete(),"node resource incomplete observation");
            boundaries.add(Map.of("eventIndex",events.size(),"node",event.get("node"),"sequence",point.sequence(),
                    "usage",V53ResourceTraceFiles.usage(point.usage())));events.add(event);
            // Only storage callbacks match this recorder's transaction names;
            // the owning journal writer remains held until the sink returns.
            if(retirement!=null && action.equals("event"))
                retirement.at((String)event.get("node"),owner.replica,(String)event.get("event"),events.size()-1);
            if(floor!=null && action.equals("event"))
                floor.at((String)event.get("node"),owner.replica,(String)event.get("event"),events.size()-1);
            if(campaign!=null && action.equals("event"))
                campaign.at((String)event.get("node"),owner.replica,(String)event.get("event"),events.size()-1);
        }
        if(action.equals("cut"))save("CUT_PREFIX");
        sink.accept(action,value);
    }
    private synchronized void closePoint(MembershipNodeOwner<?,?> node,boolean returned) {
        require(!saved,"node resource close after capture");
        var owner=owners.values().stream().filter(v->v.node==node).findFirst().orElseThrow();String name=owner.identity.nodeId().value();
        var point=node.resourceCheckpoint();require(point.complete(),"node resource close incomplete observation");
        if(returned)require(closing.contains(name) && closed.add(name) && node.state()==MembershipNodeOwner.State.CLOSED &&
                point.usage().leases()==0,"node resource original close return");
        else require(node.state()!=MembershipNodeOwner.State.CLOSED && closing.add(name),"node resource original close invocation");
        closes.add(Map.of("node",name,"event",returned?"RETURNED":"BEGIN","eventCount",events.size(),
                "sequence",point.sequence(),"usage",V53ResourceTraceFiles.usage(point.usage())));
    }
    void closeOwner(MembershipNodeOwner<?,?> node)throws IOException {
        closePoint(node,false);node.close();closePoint(node,true);
    }
    synchronized void save(String terminal)throws IOException {
        require(!saved && !owners.isEmpty() && Set.of("CUT_PREFIX","CLOSED","FAILED").contains(terminal),"node resource save state");
        require(!terminal.equals("CUT_PREFIX") || life==1 && closes.isEmpty(),"node resource crash is not close");
        require(!terminal.equals("CLOSED") || life==2 && closed.equals(owners.keySet()),"node resource missing original close");
        saved=true;var refs=new ArrayList<Map<String,Object>>();
        for(var entry:owners.entrySet()) {
            var owner=entry.getValue();String file=entry.getKey()+".json";
            String digest=V53ResourceTraceFiles.write(directory.resolve(file),owner.node.resourceObservations());
            refs.add(Map.of("identity",MembershipBootstrapSeed.identity(owner.identity),"registeredAt",owner.registeredAt,"path",file,"sha256",digest));
        }
        byte[] observed=V53EvidenceArray.encode(events,32*1024*1024),points=V53EvidenceArray.encode(boundaries,32*1024*1024);
        byte[] closing=V53EvidenceArray.encode(closes,65536);
        Files.write(directory.resolve("events.json"),observed,StandardOpenOption.CREATE_NEW);
        Files.write(directory.resolve("boundaries.json"),points,StandardOpenOption.CREATE_NEW);
        Files.write(directory.resolve("closes.json"),closing,StandardOpenOption.CREATE_NEW);
        Files.write(directory.resolve("index.json"),canonical(Map.of("schema","gse-v53-node-resource-lifetime-v1","root",root,"life",life,
                "pid",ProcessHandle.current().pid(),"terminal",terminal,"owners",refs,"eventsSha256",hash(observed),
                "boundariesSha256",hash(points),"closesSha256",hash(closing)),16384),StandardOpenOption.CREATE_NEW);
        if(retirement!=null && !terminal.equals("FAILED"))retirement.finishProcess(root,life,terminal,observed);
        if(floor!=null && !terminal.equals("FAILED"))floor.finishProcess(root,life,terminal,observed);
        if(campaign!=null && !terminal.equals("FAILED"))campaign.finishProcess(root,life,terminal,observed);
    }
}
