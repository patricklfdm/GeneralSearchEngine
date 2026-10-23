package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Drives the original maintenance request after reopen; no replacement authority or runtime READY. */
public final class V53MaintenanceLifetimeWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),node=root.resolve("node-1");String point=args[1],mode=args[2];
        var raw=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var identity=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)raw.value().get("groupId"))),
                UUID.fromString((String)raw.value().get("historyId")),HexFormat.of().formatHex(Arrays.copyOfRange(raw.bytes(),16,48)));
        var inputs=object(parse(Files.readAllBytes(root.resolve("inputs.json")),65536));
        var observations=V53JournalApplicationTest.readObservations(inputs.get("observations"));
        var parentOwned=V53JournalApplicationTest.readObservations(inputs.get("parents"));
        MembershipCurrentGeneration.Verifier verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,observations);
        var resources=new MembershipResources(512*MembershipResources.MIB);
        var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
        for(int n:List.of(1,2,3))try(var store=MembershipGrantJournal.openApplying(root.resolve("inputs/node-"+n),identity,
                V53DeclarationsTest.node(n),resources,verifier,e->{})) {
            var source=store.originalSource();sources.add(source);
            for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(root.resolve("inputs/node-"+n+"/sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
        }
        var parentAcks=new ArrayList<Decoded>();for(int n:List.of(1,2,3))parentAcks.add(decode(Files.readAllBytes(root.resolve("parent-"+n+".gsr")),"records","CHECKPOINT_ACK"));
        var bridge=new MembershipSelection.Bridge(decode(Files.readAllBytes(root.resolve("parent-statement.gsr")),"records","CHECKPOINT"),parentAcks,parentOwned);
        MembershipFloor.Copy peer;
        try(var store=MembershipGrantJournal.openApplying(root.resolve("node-2"),identity,V53DeclarationsTest.node(2),resources,verifier,e->{})) {peer=store.floorCopyCurrent();}
        String obsolete=(String)inputs.get("obsolete");
        try(var store=MembershipGrantJournal.openApplying(node,identity,V53DeclarationsTest.node(1),resources,verifier,event->{
            V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                    throw new java.io.IOException("external kill absent");
                }
            }
        })) {
            // Reopen completes saved source/floor decisions before this driver resumes.
            // Source absence skips already-completed work; every deletion still requires the storage owner's authority.
            if(Files.exists(node.resolve("sources/"+obsolete))) {
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                var current=decode(Files.readAllBytes(node.resolve("generations/"+selector.value().get("generation")+"/generation.gsr")),"records","GENERATION");
                if(!current.value().get("selection").equals(store.originalSelection().orElseThrow().digest()))
                    store.installCurrent(sources,List.of(),List.of(bridge),images);
                if(store.governingFloor().isEmpty())store.establishFloor(List.of(store.floorCopyCurrent(),peer));
                store.retireInactive();store.retireSource(obsolete);
            }
            store.releaseFloor();store.rotateJournal();
            var copy=store.floorCopyCurrent();
            if(store.governingFloor().isPresent() || store.currentCertificate().isPresent()
                    || !Arrays.equals(copy.generation.bytes(),store.installCurrent(sources,List.of(),List.of(bridge),images).bytes()))
                throw new IllegalArgumentException("incomplete exact maintenance receipt");
            V53AppliedEndWorker.print(Map.of("status","PASS","manifest",copy.generation.digest(),"cut",copy.capsule.context.cut,
                    "journal",hash(Files.readAllBytes(node.resolve("grants.gsr"))),"runtimeEnabled",false));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("maintenance lifetime lease leak");
    }
}
