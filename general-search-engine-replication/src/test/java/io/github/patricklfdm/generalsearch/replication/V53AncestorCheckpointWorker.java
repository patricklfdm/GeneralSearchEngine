package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

public final class V53AncestorCheckpointWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String point=args[1],mode=args[2];var app=new V53JournalApplicationTest();app.configure(root,Files.readAllBytes(root.resolve("base.image")),3,4);
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(root.resolve("original/pending.accept")));var data=object(parse(Files.readAllBytes(root.resolve("observations.json")),65536));
        app.cohort=new V53PendingCertificateFixture.Cohort(vote.proof(),vote.certificate(),V53JournalApplicationTest.readObservations(data.get("accepts")),V53JournalApplicationTest.readObservations(data.get("proofs")));
        var checkpoints=V53JournalApplicationTest.readObservations(data.get("checkpoints"));var all=V53JournalApplicationTest.readObservations(data.get("historical"));
        var renewals=V53JournalApplicationTest.readObservations(data.get("bridges"));all.addAll(app.cohort.owned());all.addAll(checkpoints);all.addAll(renewals);
        var acks=new ArrayList<Decoded>();for(int n:List.of(2,3))acks.add(decode(Files.readAllBytes(root.resolve("ack-node-"+n+".gsr")),"records","CHECKPOINT_ACK"));
        var bridges=new ArrayList<MembershipSelection.Bridge>();
        for(int start:List.of(1,2,4)) {
            var statement=decode(Files.readAllBytes(root.resolve("bridge-"+start+"-statement.gsr")),"records","CHECKPOINT");var own=new HashSet<Owned>();var endorsements=new ArrayList<Decoded>();
            for(int n:List.of(2,3)) {
                var ack=decode(Files.readAllBytes(root.resolve("bridge-"+start+"-node-"+n+".gsr")),"records","CHECKPOINT_ACK");endorsements.add(ack);
                renewals.stream().filter(o->o.record().equals(ack.digest())).forEach(own::add);
            }
            bridges.add(new MembershipSelection.Bridge(statement,endorsements,own));
        }
        var resources=app.f.f.resources();
        try(var store=MembershipGrantJournal.openApplying(app.f.f.node(root,1),app.f.f.f.root(),V53DeclarationsTest.node(1),resources,(r,p,i)->MembershipCapsule.verify(r,p,i,all),event->{
            V53AppliedEndWorker.print(Map.of("event",event));if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")){V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}throw new java.io.IOException("external kill absent");}
            }
        })) {
            if(store.currentCertificate().isPresent())store.publishCurrent(app.apply(store),acks,checkpoints,bridges);
            var copy=store.floorCopyCurrent();if(store.currentCertificate().isPresent() || store.currentOwnedTail().isPresent())throw new IllegalArgumentException("covered vote retained");
            V53AppliedEndWorker.print(Map.of("status","PASS","manifest",copy.generation.digest(),"selectedIndex",copy.capsule.context.cut.get("index"),"journalPublication",true));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("ancestor owner lease leak");
    }
}
