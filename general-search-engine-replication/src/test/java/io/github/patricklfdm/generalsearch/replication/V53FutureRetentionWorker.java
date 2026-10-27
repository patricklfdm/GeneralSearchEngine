package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Only path inputs; every checkpoint observation comes from a real native owner. */
public final class V53FutureRetentionWorker {
    public static void main(String[] args)throws Exception {
        var targets=list(parse(Files.readAllBytes(Path.of(args[0])),65536));
        String action=args[1],mode=args[2],point=args[3];var self=object(targets.getFirst());
        var acks=new ArrayList<Decoded>();var observations=new HashSet<MembershipContext.Owned>();
        if(action.equals("publish"))for(int i=1;i<targets.size();i++) {
            var target=object(targets.get(i));var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var owner=open(target,resources,event->System.out.println("COLLECT "+event))) {
                var applied=owner.applyCurrent(builder().configuration(),storage(Path.of((String)target.get("application")),2));
                acks.add(applied.endorsement().acknowledgement());observations.add(applied.endorsement().owned());
            }
            if(resources.usage().leases()!=0)throw new AssertionError("checkpoint collection leak");
        }
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=open(self,resources,event->{
            System.out.println("EVENT "+event);System.out.flush();
            if(event.equals(point)) {
                System.out.println("CUT "+event);System.out.flush();if(mode.equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                throw new java.io.IOException("external kill did not arrive");
            }
        })) {
            if(action.equals("record")) {
                var applied=owner.applyCurrent(builder().configuration(),storage(Path.of((String)self.get("application")),2));
                owner.retainFutureDispatch(identity(object(targets.get(1))),owner.pendingPublication(applied));
            }else if(action.equals("publish")) {
                var applied=owner.applyCurrent(builder().configuration(),storage(Path.of((String)self.get("application")),2));
                acks.addFirst(applied.endorsement().acknowledgement());observations.add(applied.endorsement().owned());
                owner.publishCurrent(applied,acks,observations,List.of());
            }else if(!action.equals("recover"))throw new IllegalArgumentException("unknown action");
            var state=owner.futureRetentionState();var peer=owner.peerRetentionState();
            System.out.println("RESPONSE "+new String(canonical(Map.of("pending",state.pending(),"revision",state.revision,
                    "digest",state.digest,"plan",parse(peer.plan().bytes(),32768),"peerRevision",peer.revision(),
                    "published",owner.floorCopyCurrent().capsule.context.cut),65536),java.nio.charset.StandardCharsets.US_ASCII));
        }
        if(resources.usage().leases()!=0)throw new AssertionError("future owner leak");
    }
    private static MembershipIdentity identity(Map<String,Object> target)throws Exception {
        Path path=Path.of((String)target.get("replica"));
        return MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
    }
    private static MembershipGrantJournal open(Map<String,Object> target,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        Path path=Path.of((String)target.get("replica")),application=Path.of((String)target.get("application"));
        var r=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)r.value().get("groupId"))),UUID.fromString((String)r.value().get("historyId")),r.rootDigest());
        return MembershipGrantJournal.openRetainingFuturePeers(path,application,root,identity(target),resources,MembershipGrantJournal.MAXIMUM,cut);
    }
}
