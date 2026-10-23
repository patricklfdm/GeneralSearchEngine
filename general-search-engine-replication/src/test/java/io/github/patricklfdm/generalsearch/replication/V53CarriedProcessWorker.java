package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Exact selected originals are retained beside the case; a child cannot invent a new round. */
public final class V53CarriedProcessWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),seed=root.getParent().resolve("seed"),node=root.resolve("node-1");String point=args[1],mode=args[2];
        var raw=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var identity=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)raw.value().get("groupId"))),UUID.fromString((String)raw.value().get("historyId")),
                HexFormat.of().formatHex(Arrays.copyOfRange(raw.bytes(),16,48)));
        var inputs=object(parse(Files.readAllBytes(seed.resolve("inputs.json")),65536));var observed=V53JournalApplicationTest.readObservations(inputs.get("observations"));
        var resources=new MembershipResources(512*MembershipResources.MIB);MembershipCurrentGeneration.Verifier verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,observed);
        var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
        // Read-only input clones prevent opening an original receipt from resealing it in place.
        Path requests=root.resolve("requests-"+UUID.randomUUID());Files.createDirectory(requests);
        for(int n:List.of(1,2,3)) {
            Path input=requests.resolve("node-"+n);V53JournalApplicationTest.copy(seed.resolve("carried-snapshots/prepared/node-"+n),input);
            try(var store=MembershipGrantJournal.openApplying(input,identity,V53DeclarationsTest.node(n),resources,verifier,e->{})) {
                var source=store.originalSource();sources.add(source);
                for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(input.resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
            }
        }
        Path peerNode=requests.resolve("peer");V53JournalApplicationTest.copy(seed.resolve("carried-snapshots/reaccepted/node-2"),peerNode);MembershipFloor.Copy peer;
        try(var store=MembershipGrantJournal.openApplying(peerNode,identity,V53DeclarationsTest.node(2),resources,verifier,e->{})){peer=store.floorCopyCurrent();}
        var wanted=MembershipPendingAccept.decode(Files.readAllBytes(seed.resolve("carried-snapshots/reaccepted/node-1/pending.accept")));
        String obsolete=(String)inputs.get("obsolete");int[] peak={0};
        try(var store=MembershipGrantJournal.openApplying(node,identity,V53DeclarationsTest.node(1),resources,verifier,event->{
            peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                    throw new java.io.IOException("external kill absent");
                }
            }
        })) {
            if(Files.exists(node.resolve("sources").resolve(obsolete))) {
                var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
                var manifest=decode(Files.readAllBytes(node.resolve("generations/"+selector.value().get("generation")+"/generation.gsr")),"records","GENERATION");
                if(!manifest.value().get("selection").equals(store.originalSelection().orElseThrow().digest()))store.installCurrent(sources,List.of(),images);
                if(!Arrays.equals(wanted.bytes(),Files.readAllBytes(node.resolve("pending.accept"))))store.acceptCurrent(wanted.entry(),wanted.payload());
                if(store.governingFloor().isEmpty())store.establishFloor(List.of(store.floorCopyCurrent(),peer));
                store.retireInactive();store.retireSource(obsolete);
            }
            store.releaseFloor();store.rotateJournal();
            var copy=store.floorCopyCurrent();
            if(!Arrays.equals(wanted.bytes(),Files.readAllBytes(node.resolve("pending.accept"))) || store.governingFloor().isPresent()
                    || number(copy.capsule.context.cut.get("index"))!=1 || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=6)
                throw new IllegalArgumentException("incomplete carried maintenance");
            V53AppliedEndWorker.print(Map.of("status","PASS","manifest",copy.generation.digest(),"pending",hash(wanted.bytes()),"runtimeEnabled",false,"peakImages",peak[0]));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("carried process lease leak");
    }
}
