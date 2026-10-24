package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

public final class V53FullJournalWorker {
    public static void main(String[] args)throws Exception {
        var data=object(parse(Files.readAllBytes(Path.of(args[0])),1024*1024));String point=args[1],mode=args[2];
        Path node=Path.of((String)data.get("node")),materialization=Path.of((String)data.get("materialization"));
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var observations=V53JournalApplicationTest.readObservations(data.get("observations"));var resources=new MembershipResources(512*MembershipResources.MIB);
        int[] peak={0};Decoded basis;
        try(var owner=MembershipGrantJournal.openBootstrapped(node,materialization,root,identity,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                    throw new java.io.IOException("external kill absent");
                }
            }
        })) {
            basis=owner.prepareCurrent(object(data.get("next")));
            if(!Arrays.equals(basis.bytes(),owner.prepareCurrent(object(data.get("next"))).bytes()))throw new IllegalArgumentException("original basis changed");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("full journal lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"basis",basis.digest(),"journalBytes",Files.size(node.resolve("grants.gsr")),"runtimeEnabled",false));
    }
}
