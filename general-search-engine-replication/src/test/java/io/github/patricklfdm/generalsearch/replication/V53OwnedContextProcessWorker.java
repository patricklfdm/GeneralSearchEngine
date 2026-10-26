package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh native owner recovery with no supplied historical observations. */
public final class V53OwnedContextProcessWorker {
    public static void main(String[] args)throws Exception {
        Path inputs=Path.of(args[0]);String point=args[1],mode=args[2];
        var data=object(parse(Files.readAllBytes(inputs),1024*1024));var targets=list(data.get("targets")).stream().map(MembershipFormat::object).toList();
        if(!data.keySet().equals(Set.of("targets")))throw new IllegalArgumentException("native context inputs must contain only admitted paths");
        Path node=Path.of((String)targets.getFirst().get("node")),materialization=Path.of((String)targets.getFirst().get("materialization"));
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var resources=new MembershipResources(512*MembershipResources.MIB);int[] peak={0};
        try(var owner=MembershipGrantJournal.openBootstrapped(node,materialization,root,local,resources,MembershipGrantJournal.MAXIMUM,event->{
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
            var retained=new ArrayList<MembershipFloor.Copy>();
            for(var target:targets.subList(1,targets.size())) {
                Path peer=Path.of((String)target.get("node")),application=Path.of((String)target.get("materialization"));
                var identity=MembershipContext.identity(object(decode(Files.readAllBytes(peer.resolve("node.gsr")),"records","NODE").value().get("identity")));
                var budget=new MembershipResources(512*MembershipResources.MIB);
                try(var other=MembershipGrantJournal.openBootstrapped(peer,application,root,identity,budget,MembershipGrantJournal.MAXIMUM,e->V53RetirementImagesTest.bounded(budget))) {
                    V53ContextGenerationWorker.add(sources,images,other.originalSource(),peer);retained.add(other.floorCopyCurrent());
                }
                if(budget.usage().leases()!=0)throw new IllegalArgumentException("covered context peer lease leak");
            }
            var longest=sources.getLast();for(var source:sources)if(number(source.capsule.context.cut.get("index"))>number(longest.capsule.context.cut.get("index")))longest=source;
            var longestCapsule=longest.capsule;var needed=new HashSet<MembershipCapsule.Anchor>();
            for(var source:sources)if(!source.capsule.terminal().equals(longestCapsule.anchor(number(source.capsule.context.cut.get("index")))))needed.add(source.capsule.terminal());
            var bridges=new ArrayList<MembershipSelection.Bridge>();
            for(var copy:retained)if(copy.capsule.terminal().equals(longestCapsule.terminal())) {
                for(var bridge:copy.capsule.verifiedAncestry(copy.fileNames().contains("ancestry.gsr")?copy.fileBytes("ancestry.gsr"):new byte[0])) {
                    var v=bridge.statement.value();var lower=new MembershipCapsule.Anchor(object(v.get("start")),(String)v.get("catalogBefore"),(String)v.get("applicationBefore"));
                    if(needed.remove(lower))bridges.add(bridge);
                }
            }
            if(!needed.isEmpty())throw new IllegalArgumentException("native context missing original ancestry");
            // The complete owner-authenticated copy retains the bridge's history;
            // its serialized ACKs are deliberately not converted into fresh votes.
            var sourceCopies=new ArrayList<MembershipSelection.Source>();
            for(var source:sources) {
                MembershipCapsule capsule=source.capsule;
                for(var copy:retained)if(copy.capsule.sameProvenPrefix(capsule.packet)) {
                    var sourceImages=new TreeMap<String,byte[]>();for(String hash:capsule.packet.images().keySet())sourceImages.put(hash,images.get(hash));
                    capsule=copy.capsule.materialization(capsule.packet,sourceImages,copy.capsule.verifiedAncestry(copy.fileNames().contains("ancestry.gsr")?copy.fileBytes("ancestry.gsr"):new byte[0]));break;
                }
                sourceCopies.add(source.withVerifiedHistory(capsule));
            }
            images.keySet().retainAll(longest.capsule.packet.images().keySet());owner.installCurrent(sourceCopies,bridges,images);
            if(owner.currentOwnedTail().isPresent() || owner.currentCertificate().isPresent() || number(owner.floorCopyCurrent().capsule.context.cut.get("index"))!=3
                    || Files.exists(node.resolve("pending.context")))throw new IllegalArgumentException("covered context installation incomplete");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("covered context process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"runtimeEnabled",false));
    }
}
