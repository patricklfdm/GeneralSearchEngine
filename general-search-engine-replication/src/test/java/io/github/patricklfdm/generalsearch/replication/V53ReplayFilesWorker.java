package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual core replay/crash worker with an exclusive owner; this component does not issue a checkpoint ACK. */
public final class V53ReplayFilesWorker {
    static void print(Map<String,Object> value){V53AppliedEndWorker.print(value);}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);String point=args[1],mode=args[2];var test=new V53ReplayFilesTest();
        byte[] base=Files.readAllBytes(root.getParent().resolve("base.image"));var r=test.resources();Path lock=root.resolve("owner.lock");Object lockKey=MembershipBasisSources.key(lock);
        try(var owner=AdmissionPaths.own(lock,false);var journal=test.journal(r);var store=new MembershipReplayFiles(root.resolve("scratch"),r)) {
            if(point.startsWith("v41-")){System.setProperty("gse.v4.crashBarrier",point);System.setProperty("gse.v4.crashAction",mode.equals("kill")?"wait":"halt");}
            var result=store.execute(test.selector,test.plan.originalCertificate(),test.identity,work->V53ReplayFilesTest.replay(root,base,work),()->{
                if(!owner.lock().isValid() || !lockKey.equals(MembershipBasisSources.key(lock)))throw new java.io.IOException("lost exclusive owner");
            },event->{
                print(Map.of("event",event));if(event.equals(point)) {
                    if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                    if(mode.equals("kill")){print(Map.of("event","AWAITING_KILL","cut",point));try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}throw new java.io.IOException("external kill absent");}
                }
            });
            print(Map.of("status","PASS","image",hash(result.image()),"sequence",result.sequence(),"scratchAbsent",!Files.exists(root.resolve("scratch"))));
        }
        if(r.usage().leases()!=0)throw new IllegalArgumentException("replay lease leak");
    }
}
