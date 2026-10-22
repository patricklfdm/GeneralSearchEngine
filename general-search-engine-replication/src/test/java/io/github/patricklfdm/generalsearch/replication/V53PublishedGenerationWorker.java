package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Exact generation file/selector crash worker. Historical/phased ownership here is an explicit fixture. */
public final class V53PublishedGenerationWorker {
    public static void main(String[] args)throws Exception {
        var fixture=new V53PublishedGenerationTest.Fixture(3,"ADD",1);Path path=Path.of(args[0]);
        MembershipBallotAllocator.Cut barrier=event->{
            System.out.println(new String(canonical(Map.of("event",event),4096),java.nio.charset.StandardCharsets.UTF_8));System.out.flush();
            if(event.equals(args[1])) {
                if(args[2].equals("halt"))Runtime.getRuntime().halt(73);
                if(args[2].equals("kill")){System.out.println("AWAITING_KILL");System.out.flush();while(true)java.util.concurrent.locks.LockSupport.parkNanos(1_000_000L);}
            }
        };
        var resources=new MembershipResources(512*MembershipResources.MIB);var plan=fixture.plan();
        try(var owner=MembershipBallotAllocator.openWithGenerationInstall(path,fixture.root(),V53DeclarationsTest.node(1),e->{});
            var current=new MembershipCurrentGeneration(path,fixture.root(),V53DeclarationsTest.node(1),resources,List.of(fixture.promise),List.of(fixture.basis),List.of(fixture.selected),fixture::verify,barrier,true);
            var inactive=new MembershipGenerationFiles(path,current.generation,resources)) {
            plan.verify(fixture.f.capsule.source.root,V53DeclarationsTest.node(1),fixture::verify,List.of(fixture.checkpoint.originalParent()));
            if(current.generation.equals("a"))inactive.install(plan,current.selector.bytes(),owner::checkOwner,current::check,barrier);
            else if(!Arrays.equals(current.manifest.bytes(),plan.manifest.bytes()) || inactive.pending())throw new IllegalArgumentException("changed completed plan");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("resource leak");
        System.out.println(new String(canonical(Map.of("status","PASS","manifest",plan.manifest.digest(),"journalPublication",false),4096),java.nio.charset.StandardCharsets.UTF_8));
    }
}
