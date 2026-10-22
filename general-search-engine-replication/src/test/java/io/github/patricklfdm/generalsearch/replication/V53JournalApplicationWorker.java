package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh owner over actually persisted phased votes. Only initial provisioning is a fixture. */
public final class V53JournalApplicationWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String point=args[1],mode=args[2];var test=new V53JournalApplicationTest();
        test.configure(root,Files.readAllBytes(root.resolve("base.image")),3,0);
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(root.resolve("node-1/"+MembershipPendingAccept.FILE)));
        var observed=object(parse(Files.readAllBytes(root.resolve("observations.json")),16384));
        test.cohort=new V53PendingCertificateFixture.Cohort(vote.proof(),vote.certificate(),V53JournalApplicationTest.readObservations(observed.get("accepts")),V53JournalApplicationTest.readObservations(observed.get("proofs")));
        var resources=test.f.f.resources();
        try(var store=test.open(root,1,resources,event->{
            V53AppliedEndWorker.print(Map.of("event",event));if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")){V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}throw new java.io.IOException("external kill absent");}
            }
        })) {
            if(point.startsWith("v41-")){System.setProperty("gse.v4.crashBarrier",point);System.setProperty("gse.v4.crashAction",mode.equals("kill")?"wait":"halt");}
            var applied=test.apply(store);V53AppliedEndWorker.print(Map.of("status","PASS","ack",applied.endorsement().acknowledgement().digest(),
                    "image",hash(applied.plan().application.image()),"sequence",applied.plan().application.sequence(),"selectedIndex",store.floorCopyCurrent().capsule.context.cut.get("index")));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("application owner lease leak");
    }
}
