package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual owners observe selected sources before replaying the original installation. */
public final class V53ContextGenerationWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),node=path.resolve("store"),rootPath=path.getParent();String operation=args[1],point=args[2],mode=args[3];
        boolean[] armed={Boolean.parseBoolean(args[4])};String[] parts=point.split("@");int ordinal=parts.length==2?Integer.parseInt(parts[1]):1;int[] hits={0},peak={0};
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var observations=V53JournalApplicationTest.readObservations(object(parse(Files.readAllBytes(rootPath.resolve("inputs.json")),65536)).get("observations"));
        byte[] original=Files.readAllBytes(rootPath.resolve("reference/round-22/selected/node-1/pending.accept"));var vote=MembershipPendingAccept.decode(original);
        var resources=new MembershipResources(512*MembershipResources.MIB);String accepted;
        try(var owner=MembershipGrantJournal.openContextual(node,root,local,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",event));
            if(armed[0] && event.equals(parts[0]) && ++hits[0]==ordinal) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            V53AppliedEndWorker.print(Map.of("event","OPEN_RETURNED"));armed[0]=true;
            if(operation.equals("install")) {
                var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
                add(sources,images,owner.originalSource(),node);
                for(int n:List.of(2,3)) {
                    Path peer=path.resolve("peers/node-"+n);var own=MembershipContext.identity(object(decode(Files.readAllBytes(peer.resolve("node.gsr")),"records","NODE").value().get("identity")));
                    var budget=new MembershipResources(512*MembershipResources.MIB);
                    try(var other=MembershipGrantJournal.openContextual(peer,root,own,budget,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,e->V53RetirementImagesTest.bounded(budget))) {
                        add(sources,images,other.originalSource(),peer);
                    }
                    if(budget.usage().leases()!=0)throw new IllegalArgumentException("peer reservation leak");
                }
                String installed=owner.installCurrent(sources,List.of(),images).digest();V53AppliedEndWorker.print(Map.of("event","RETURNED_INSTALL","manifest",installed));
                if(!installed.equals(owner.installCurrent(sources,List.of(),images).digest()))throw new IllegalArgumentException("changed duplicate install");
                V53AppliedEndWorker.print(Map.of("event","RETURNED_INSTALL","manifest",installed));
            } else if(!operation.equals("retire"))throw new IllegalArgumentException("unknown generation operation");
            if(!Arrays.equals(original,owner.retainPendingContext().vote().bytes()))throw new IllegalArgumentException("changed original before retirement");
            owner.retireContextOriginal();V53AppliedEndWorker.print(Map.of("event","RETURNED_RETIRE"));
            if(owner.retireContextOriginal().isPresent())throw new IllegalArgumentException("duplicate retirement changed");
            V53AppliedEndWorker.print(Map.of("event","RETURNED_RETIRE"));
            if(!Arrays.equals(original,owner.retainPendingContext().vote().bytes()) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=6)
                throw new IllegalArgumentException("generation recovery changed original/steady bound");
            V53ContextRetirementTest.snapshotOwned(node,path.resolve("recovered"));V53AppliedEndWorker.print(Map.of("event","RECOVERED"));
            accepted=owner.acceptRetainedCurrent(vote.entry(),vote.payload()).record();V53AppliedEndWorker.print(Map.of("event","RETURNED_ACCEPT","record",accepted));
            if(!accepted.equals(owner.acceptRetainedCurrent(vote.entry(),vote.payload()).record()) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=7)
                throw new IllegalArgumentException("generation successor changed");
            V53AppliedEndWorker.print(Map.of("event","RETURNED_ACCEPT","record",accepted));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("generation process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","accept",accepted,"peakImages",peak[0],"runtimeEnabled",false));
    }
    static void add(List<MembershipSelection.Source> sources,Map<String,byte[]> images,MembershipSelection.Source source,Path node)throws Exception {
        sources.add(source);for(String hash:source.capsule.packet.images().keySet()) {
            byte[] image=Files.readAllBytes(node.resolve("sources/"+source.basis.value().get("basisId")+"/"+hash+".image"));
            byte[] previous=images.putIfAbsent(hash,image);if(previous!=null && !Arrays.equals(previous,image))throw new IllegalArgumentException("conflicting selected image");
        }
    }
}
