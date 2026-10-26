package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual fresh process: only paths and an operation, never imported peer knowledge. */
public final class V53PeerRetentionWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,history,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            if(args.length==5 && args[4].equals(event)) {
                System.out.println("CUT "+event);System.out.flush();
                if(args[3].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
            }
        })) {
            var state=switch(args[2]) {
                case "init"->owner.initializePeerRetention();
                case "update"->owner.reconcilePeerRetention(List.of());
                case "inspect"->owner.peerRetentionState();
                default->throw new IllegalArgumentException("worker operation");
            };
            System.out.println(new String(canonical(Map.of("status","PASS","revision",state.revision(),"digest",state.digest(),"plan",parse(state.plan().bytes(),32768)),65536),java.nio.charset.StandardCharsets.UTF_8));
        }
        if(resources.usage().leases()!=0)throw new AssertionError("retention resource leak");
    }
}
