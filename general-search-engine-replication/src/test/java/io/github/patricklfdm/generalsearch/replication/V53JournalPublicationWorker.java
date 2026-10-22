package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Fresh real journal owner; retained physical voters/ends supply observations, never certificate hashes alone. */
public final class V53JournalPublicationWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String point=args[1],mode=args[2];var test=new V53JournalApplicationTest();
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(root.resolve("original/"+MembershipPendingAccept.FILE)));
        test.configure(root,Files.readAllBytes(root.resolve("base.image")),3,Math.toIntExact(number(vote.entry().value().get("index"))-1));
        var observed=object(parse(Files.readAllBytes(root.resolve("observations.json")),16384));
        test.cohort=new V53PendingCertificateFixture.Cohort(vote.proof(),vote.certificate(),V53JournalApplicationTest.readObservations(observed.get("accepts")),V53JournalApplicationTest.readObservations(observed.get("proofs")));
        Set<Owned> checkpoints=V53JournalApplicationTest.readObservations(observed.get("checkpoints"));var observations=new HashSet<>(test.f.f.f.fixture.owned);observations.addAll(test.cohort.owned());observations.addAll(checkpoints);
        var acks=new ArrayList<Decoded>();for(int n:List.of(1,2,3))if(Files.exists(root.resolve("ack-node-"+n+".gsr")))acks.add(decode(Files.readAllBytes(root.resolve("ack-node-"+n+".gsr")),"records","CHECKPOINT_ACK"));
        var bridges=new ArrayList<MembershipSelection.Bridge>();
        if(observed.containsKey("parents")) {
            var owned=V53JournalApplicationTest.readObservations(observed.get("parents"));observations.addAll(owned);var parentAcks=new ArrayList<Decoded>();
            for(var ack:acks)parentAcks.add(decode(Files.readAllBytes(root.resolve("parent-"+ack.value().get("voter")+".gsr")),"records","CHECKPOINT_ACK"));
            bridges.add(new MembershipSelection.Bridge(decode(Files.readAllBytes(root.resolve("parent-statement.gsr")),"records","CHECKPOINT"),parentAcks,owned));
        }
        var resources=test.f.f.resources();
        try(var store=MembershipGrantJournal.openApplying(test.f.f.node(root,1),test.f.f.f.root(),V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,observations),event->{
            V53AppliedEndWorker.print(Map.of("event",event));if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")){V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}throw new java.io.IOException("external kill absent");}
            }
        })) {
            if(store.currentCertificate().isPresent())store.publishCurrent(test.apply(store),acks,checkpoints,bridges);
            var copy=store.floorCopyCurrent();if(store.currentCertificate().isPresent() || store.currentOwnedTail().isPresent())throw new IllegalArgumentException("covered vote retained");
            V53AppliedEndWorker.print(Map.of("status","PASS","manifest",copy.generation.digest(),"selectedIndex",copy.capsule.context.cut.get("index"),"journalPublication",true));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("publication owner lease leak");
    }
}
