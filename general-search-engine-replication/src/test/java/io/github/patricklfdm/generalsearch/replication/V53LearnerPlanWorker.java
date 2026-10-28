package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** The parent supplies original source-verified plan metadata. This worker tests
 * only persistence/reseal; it cannot authenticate a capsule or admit a voter. */
public final class V53LearnerPlanWorker {
    public static void main(String[] args)throws Exception {
        var plan=MembershipLearnerAdmissionPlan.decode(Files.readAllBytes(Path.of(args[0])));
        String action=args[1],mode=args[2],target=args[3];
        require(Set.of("create","resume").contains(action) && Set.of("halt","kill","normal").contains(mode),"learner plan worker command");
        var resources=new MembershipResources(512*MembershipResources.MIB);
        MembershipBallotAllocator.Cut cut=event->{
            System.out.println("POINT "+event);System.out.flush();
            if(event.equals(target)) {
                System.out.println("CUT "+event);System.out.flush();
                if(mode.equals("halt"))Runtime.getRuntime().halt(23);
                if(mode.equals("kill"))try{new CountDownLatch(1).await();}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
            }
        };
        try(var files=action.equals("create")?MembershipLearnerAdmissionFiles.create(plan,resources,cut,()->{}):
                MembershipLearnerAdmissionFiles.open(plan.summary(),resources,cut)) {
            require(files.summary().equals(plan.summary()),"learner plan summary changed");
            require(!Files.exists(plan.request.replicaDirectory()),"learner plan created replica authority");
            System.out.println("PLAN "+files.summary().planDigest());System.out.flush();
        }
        require(resources.usage().leases()==0,"learner plan worker resources leaked");
    }
}
