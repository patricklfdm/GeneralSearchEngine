package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Reopens actual native future/source storage; accepts no caller history or votes. */
public final class V53FutureSourceWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var r=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)r.value().get("groupId"))),UUID.fromString((String)r.value().get("historyId")),r.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openRetainingFuturePeers(path,application,root,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            System.out.println("EVENT "+event);System.out.flush();
            if(event.equals(args[3])) {
                System.out.println("CUT "+event);System.out.flush();if(args[2].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                throw new java.io.IOException("external kill did not arrive");
            }
        })) {
            if(!args[2].equals("resume")) {
                long counter=owner.reserveCounter();
                owner.prepareCurrent(Map.of("counter",counter,"proposer",identity.nodeId().value(),"incarnation",identity.storageId().toString()));
            }
            var source=owner.originalSource();var frozen=MembershipPeerRetentionSource.read(source);
            if(frozen.future()==null || !frozen.future().pending())throw new AssertionError("lost future source proof");
            System.out.println("RESPONSE "+source.basis.digest()+" "+hash(frozen.futureBytes()));
        }
        if(resources.usage().leases()!=0)throw new AssertionError("source capture resource leak");
    }
}
