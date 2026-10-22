package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Component crash worker: actual exclusive lock and end files; original protocol authority is a fixture. */
public final class V53AppliedEndWorker {
    static void print(Map<String,Object> value){System.out.println(new String(canonical(value,16384),java.nio.charset.StandardCharsets.US_ASCII));System.out.flush();}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String point=args[1],mode=args[2];
        var fixture=new V53CapsuleFixture(3,"ADD",0);var plan=V53CheckpointPlanTest.plan(fixture.verify(),fixture.source,0);var local=V53DeclarationsTest.node(1);
        var selector=decode(encode("records","SELECTOR",Map.of("root",plan.catalog.value().get("root"),"node","node-1","generation","a","digest",V53ContextFixture.H)),"records","SELECTOR");
        var r=new MembershipResources(512*MembershipResources.MIB);Path lock=root.resolve("owner.lock");
        Object lockKey=MembershipBasisSources.key(lock);
        try(var owner=AdmissionPaths.own(lock,false);var journal=r.reserve(MembershipResources.Unit.JOURNAL,"process-owner",MembershipResources.Unit.JOURNAL.bytes);
                var store=new MembershipAppliedEndFiles(root.resolve("end"),r,MembershipResources.Unit.JOURNAL.bytes)) {
            var result=store.force(plan,selector,local,()->{
                if(!owner.lock().isValid() || !lockKey.equals(MembershipBasisSources.key(lock)))throw new java.io.IOException("lost exclusive owner");
            },event->{
                print(Map.of("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")) {
                        print(Map.of("event","AWAITING_KILL","cut",point));
                        try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                        throw new java.io.IOException("external kill did not arrive");
                    }
                }
            });
            print(Map.of("status","PASS","ack",result.acknowledgement().digest(),"parent",result.owned().parent(),"voter",result.owned().voter()));
        }
        if(r.usage().leases()!=0)throw new IllegalArgumentException("applied-end process lease leak");
    }
}
