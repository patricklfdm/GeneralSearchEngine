package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Reopens the actual admitted paths after external process death. */
public final class V53HiddenStagingProcessWorker {
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
                if(budget.usage().leases()!=0)throw new IllegalArgumentException("hidden peer lease leak");
            }
            var longest=sources.getLast();for(var source:sources)if(number(source.capsule.context.cut.get("index"))>number(longest.capsule.context.cut.get("index")))longest=source;
            images.keySet().retainAll(longest.capsule.packet.images().keySet());
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
            var phased=observations.stream().filter(o->o.record().equals(vote.accept().digest()) || o.record().equals(vote.proof().digest())).collect(java.util.stream.Collectors.toSet());
            var proof=object(data.get("appliedAncestry"));
            var statement=decode(HexFormat.of().parseHex((String)proof.get("statement")),"records","CHECKPOINT");
            var acknowledgements=list(proof.get("acknowledgements")).stream().map(v->decode(HexFormat.of().parseHex((String)v),"records","CHECKPOINT_ACK")).toList();
            var hashes=acknowledgements.stream().map(Decoded::digest).collect(java.util.stream.Collectors.toSet());
            var bridge=new MembershipSelection.Bridge(statement,acknowledgements,observations.stream().filter(v->hashes.contains(v.record())).collect(java.util.stream.Collectors.toSet()));
            var originals=originals(node);
            owner.retireCoveredApplication(builder().configuration(),storage(materialization,2),phased,sources,List.of(),List.of(),images,List.of(bridge));
            V53StagedApplicationTest.noStaging(node);
            if(!originals.equals(originals(node)))throw new IllegalArgumentException("hidden staging changed original authority");
            owner.installCurrent(sources,List.of(),images);
            if(owner.currentOwnedTail().isPresent() || owner.currentCertificate().isPresent() || number(owner.floorCopyCurrent().capsule.context.cut.get("index"))!=2)
                throw new IllegalArgumentException("hidden installation incomplete");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("hidden process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"runtimeEnabled",false));
    }
    private static Map<String,String> originals(Path node)throws Exception {
        var result=new TreeMap<String,String>();
        try(var paths=Files.walk(node)) {
            for(var path:paths.filter(Files::isRegularFile).toList()) {
                String name=node.relativize(path).toString();
                // Closing ANY descriptor for the locked inode can release a POSIX
                // process lock. Raw snapshots include this file only after exit.
                if(!name.equals("replica.lock") && !name.startsWith("applied-end/") && !name.startsWith("application-replay/"))
                    result.put(name,hash(Files.readAllBytes(path)));
            }
        }
        return result;
    }

}
