package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;

/** Exclusive real process writes; the input FINAL certificate remains conditional fixture authority. */
public final class V53DepartingEndWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String point=args[1],mode=args[2],profile=args[3];
        var plan=V53DepartingEndTest.plan(profile);var local=V53DepartingEndTest.local(profile);var selector=V53DepartingEndTest.selector(plan,local);
        var resources=V53DepartingEndTest.resources();Path lock=root.resolve("owner.lock");Object key=MembershipBasisSources.key(lock);
        try(var owner=AdmissionPaths.own(lock,false);var journal=V53DepartingEndTest.journal(resources);
                var store=new MembershipAppliedEndFiles(root.resolve("end"),resources,V53DepartingEndTest.LIMIT)) {
            var result=store.forceCompletion(plan,selector,local,()->{
                if(!owner.lock().isValid() || !key.equals(MembershipBasisSources.key(lock)))throw new java.io.IOException("lost exclusive owner");
            },event->{
                V53AppliedEndWorker.print(Map.of("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            });
            if(!(result instanceof MembershipAppliedEndFiles.Departure))throw new IllegalArgumentException("departing result acquired a vote");
            store.completed(plan,selector,local,result);
            V53AppliedEndWorker.print(Map.of("status","PASS","profile",profile,"completion","NONVOTING",
                    "statement",plan.statement.digest(),"node",local.nodeId().value()));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("departing-end lease leak");
    }
}
