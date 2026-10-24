package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Reopens exact admitted authority; no peer packet or vote is manufactured. */
public final class V53SourceSuccessorProcessWorker {
    public static void main(String[] args)throws Exception {
        Path inputs=Path.of(args[0]);String point=args[1],mode=args[2];
        var data=object(parse(Files.readAllBytes(inputs),1024*1024));
        var observations=V53JournalApplicationTest.readObservations(data.get("observations"));
        Path node=Path.of((String)data.get("node")),materialization=Path.of((String)data.get("materialization"));String id=(String)data.get("source");
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var resources=new MembershipResources(512*MembershipResources.MIB);int[] peak={0},seen={0};
        String event=point.split("@")[0];int occurrence=point.contains("@")?Integer.parseInt(point.split("@")[1]):1;
        try(var owner=MembershipGrantJournal.openBootstrapped(node,materialization,root,local,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,e->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",e));
            if(e.equals(event) && ++seen[0]==occurrence) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            if(Files.exists(node.resolve("sources/"+id)) || Files.exists(node.resolve(MembershipSourceRetirementFiles.FILE)))owner.retireSource(id);
            if(Files.exists(node.resolve("sources/"+id)) || Files.exists(node.resolve(MembershipSourceRetirementFiles.FILE)))throw new IllegalArgumentException("source retirement incomplete");
            if(!hash(Files.readAllBytes(node.resolve("pending.accept"))).equals(data.get("voteSha256")))throw new IllegalArgumentException("successor vote changed");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("successor source process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"runtimeEnabled",false));
    }
}
