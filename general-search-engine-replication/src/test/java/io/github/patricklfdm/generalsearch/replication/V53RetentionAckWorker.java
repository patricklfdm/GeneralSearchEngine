package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh-process native receiver. The exact original wire request is the only operation input. */
public final class V53RetentionAckWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var request=decode(Files.readAllBytes(Path.of(args[2])),"wire","RETENTION_INTENT");
        var sender=MembershipContext.identity(object(request.value().get("sender")));
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openRetainingPeers(path,application,history,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            System.out.println("EVENT "+event);System.out.flush();
            if(event.equals(args[4])) {
                System.out.println("CUT "+event);System.out.flush();
                if(args[3].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
            }
        })) {
            var response=owner.recordPeerRetention(sender,request);
            if(!Arrays.equals(response.bytes(),owner.recordPeerRetention(sender,request).bytes()))throw new AssertionError("duplicate changed ACK");
            System.out.println("RESPONSE "+Base64.getEncoder().encodeToString(response.bytes()));
        }
        if(resources.usage().leases()!=0 || resources.usage().queued()!=0)throw new AssertionError("retention resource leak");
    }
}
