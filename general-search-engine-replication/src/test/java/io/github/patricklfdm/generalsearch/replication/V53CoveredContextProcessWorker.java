package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual admitted storage reopen; the parent owns external termination and probes. */
public final class V53CoveredContextProcessWorker {
    public static void main(String[] args)throws Exception {
        Path inputs=Path.of(args[0]);String point=args[1],mode=args[2];
        var data=object(parse(Files.readAllBytes(inputs),1024*1024));var targets=list(data.get("targets")).stream().map(MembershipFormat::object).toList();
        var observations=V53JournalApplicationTest.readObservations(data.get("observations"));
        Path node=Path.of((String)targets.getFirst().get("node")),materialization=Path.of((String)targets.getFirst().get("materialization"));
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var resources=new MembershipResources(512*MembershipResources.MIB);int[] peak={0};
        try(var owner=MembershipGrantJournal.openBootstrapped(node,materialization,root,local,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
            V53ContextGenerationWorker.add(sources,images,owner.originalSource(),node);
            for(var target:targets.subList(1,targets.size())) {
                Path peer=Path.of((String)target.get("node")),application=Path.of((String)target.get("materialization"));
                var identity=MembershipContext.identity(object(decode(Files.readAllBytes(peer.resolve("node.gsr")),"records","NODE").value().get("identity")));
                var budget=new MembershipResources(512*MembershipResources.MIB);
                try(var other=MembershipGrantJournal.openBootstrapped(peer,application,root,identity,budget,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,e->V53RetirementImagesTest.bounded(budget))) {
                    V53ContextGenerationWorker.add(sources,images,other.originalSource(),peer);
                }
                if(budget.usage().leases()!=0)throw new IllegalArgumentException("covered context peer lease leak");
            }
            var longest=sources.getLast();for(var source:sources)if(number(source.capsule.context.cut.get("index"))>number(longest.capsule.context.cut.get("index")))longest=source;
            images.keySet().retainAll(longest.capsule.packet.images().keySet());owner.installCurrent(sources,List.of(),images);
            if(owner.currentOwnedTail().isPresent() || owner.currentCertificate().isPresent() || number(owner.floorCopyCurrent().capsule.context.cut.get("index"))!=1
                    || Files.exists(node.resolve("pending.context")))throw new IllegalArgumentException("covered context installation incomplete");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("covered context process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"runtimeEnabled",false));
    }
}
