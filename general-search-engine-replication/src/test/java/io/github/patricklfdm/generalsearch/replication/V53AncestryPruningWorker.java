package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Reopens retained inputs; never constructs replacement historical fixtures in the child. */
public final class V53AncestryPruningWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),node=root.resolve("node-1");String point=args[1],mode=args[2];
        var rawRoot=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var identity=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rawRoot.value().get("groupId"))),
                UUID.fromString((String)rawRoot.value().get("historyId")),HexFormat.of().formatHex(Arrays.copyOfRange(rawRoot.bytes(),16,48)));
        var app=new V53ApplicationReplayTest();app.temp=root;
        var data=object(parse(Files.readAllBytes(root.resolve("observations.json")),65536));
        var original=V53JournalApplicationTest.readObservations(data.get("accepts"));original.addAll(V53JournalApplicationTest.readObservations(data.get("proofs")));
        var checkpoints=V53JournalApplicationTest.readObservations(data.get("checkpoints"));
        var parents=V53JournalApplicationTest.readObservations(data.get("parents"));
        var all=new HashSet<>(original);all.addAll(checkpoints);all.addAll(parents);all.addAll(V53JournalApplicationTest.readObservations(data.get("historical")));
        var acks=new ArrayList<Decoded>();var parentAcks=new ArrayList<Decoded>();
        for(int n:List.of(2,3)) {
            acks.add(decode(Files.readAllBytes(root.resolve("ack-node-"+n+".gsr")),"records","CHECKPOINT_ACK"));
            parentAcks.add(decode(Files.readAllBytes(root.resolve("parent-node-"+n+".gsr")),"records","CHECKPOINT_ACK"));
        }
        var statement=decode(Files.readAllBytes(root.resolve("parent-statement.gsr")),"records","CHECKPOINT");
        var bridge=new MembershipSelection.Bridge(statement,parentAcks,parents);
        var resources=new MembershipResources(512*MembershipResources.MIB);var counts=new HashMap<String,Integer>();
        try(var store=MembershipGrantJournal.openApplying(node,identity,V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,all),event->{
            V53AppliedEndWorker.print(Map.of("event",event));String effective=event;
            if(event.equals("INSTALL_MEMBER_WRITTEN") || event.equals("INSTALL_MEMBER_FORCED")) {
                int index=counts.merge(event,1,Integer::sum)-1;
                var manifest=decode(Files.readAllBytes(node.resolve("generations/a/generation.gsr")),"records","GENERATION");
                var names=list(manifest.value().get("files")).stream().map(v->(String)object(v).get("path")).filter(n->!n.endsWith(".image")).sorted().toList();
                if(names.get(index).equals(MembershipSelectedSources.FILE)) {
                    effective=event.replace("INSTALL_MEMBER","SELECTED_SOURCES");V53AppliedEndWorker.print(Map.of("event",effective));
                }
            }
            if(effective.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                    throw new java.io.IOException("external kill absent");
                }
            }
        })) {
            if(store.currentCertificate().isPresent())store.publishCurrent(store.applyCurrent(app.configuration(),app.storage(),original),acks,checkpoints,List.of(bridge));
            var copy=store.floorCopyCurrent();
            if(store.currentCertificate().isPresent() || store.currentOwnedTail().isPresent())throw new IllegalArgumentException("covered vote retained");
            V53AppliedEndWorker.print(Map.of("status","PASS","manifest",copy.generation.digest(),"selectedIndex",copy.capsule.context.cut.get("index"),"journalPublication",true));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("pruning owner lease leak");
    }
}
