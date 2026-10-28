package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.concurrent.CountDownLatch;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Resume only the original native-acquired plan/source/retention transaction.
 * No source reconstruction, new historical observations, readiness or votes. */
public final class V53LearnerStoreWorker {
    public static void main(String[] args)throws Exception {
        var plan=MembershipLearnerAdmissionPlan.decode(Files.readAllBytes(Path.of(args[0])));
        String mode=args[1],target=args[2];var resources=new MembershipResources(512*MembershipResources.MIB);
        MembershipBallotAllocator.Cut cut=event->{
            System.out.println("POINT "+event);System.out.flush();
            if(event.equals(target)) {
                System.out.println("CUT "+event);System.out.flush();
                if(mode.equals("halt"))Runtime.getRuntime().halt(23);
                if(mode.equals("kill"))try{new CountDownLatch(1).await();}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
            }
        };
        try(var store=MembershipLearnerStore.resume(plan.summary(),resources,cut)) {
            require(store.summary().equals(plan.summary()),"learner stored summary changed");
            require(!store.capsule().context.voters().contains(plan.request.identity().nodeId().value()),"learner became voter");
            System.out.println("STORE "+plan.summary().planDigest());System.out.flush();
        }
        require(resources.usage().leases()==0,"learner store worker resources leaked");
    }
}
