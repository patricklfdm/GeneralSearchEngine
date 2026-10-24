package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh local owner: obsolete source 22, installed generation 23, original vote 20. */
public final class V53ContextInstalledSourceWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),node=path.resolve("store"),rootPath=path.getParent();
        String point=args[1],mode=args[2];boolean duringOpen=Boolean.parseBoolean(args[3]);
        String[] parts=point.split("@");int ordinal=parts.length==2?Integer.parseInt(parts[1]):1;int[] hits={0},peak={0};boolean[] armed={duringOpen};
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var observations=V53JournalApplicationTest.readObservations(object(parse(Files.readAllBytes(rootPath.resolve("inputs.json")),65536)).get("observations"));
        var prior=MembershipPendingContext.decode(Files.readAllBytes(rootPath.resolve("reference/round-22/source-retired/node-1/pending.context")));
        String old=(String)MembershipPendingContext.backingBasis(prior).value().get("basisId");
        byte[] original=Files.readAllBytes(rootPath.resolve("initial/pending.accept"));var vote=MembershipPendingAccept.decode(original);
        var resources=new MembershipResources(512*MembershipResources.MIB);String accepted;
        try(var owner=MembershipGrantJournal.openContextual(node,root,local,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",event));
            if(armed[0] && event.equals(parts[0]) && ++hits[0]==ordinal) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            V53AppliedEndWorker.print(Map.of("event","OPEN_RETURNED"));armed[0]=true;
            if(Files.exists(node.resolve(MembershipSourceRetirementFiles.FILE)) || Files.exists(node.resolve("sources").resolve(old)))owner.retireSource(old);
            if(!Arrays.equals(original,owner.retainPendingContext().vote().bytes()) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=6)
                throw new IllegalArgumentException("installed source recovery changed original/steady bound");
            V53ContextRetirementTest.snapshotOwned(node,path.resolve("recovered"));V53AppliedEndWorker.print(Map.of("event","RECOVERED"));
            accepted=owner.acceptRetainedCurrent(vote.entry(),vote.payload()).record();V53AppliedEndWorker.print(Map.of("event","RETURNED_ACCEPT","record",accepted));
            if(!accepted.equals(owner.acceptRetainedCurrent(vote.entry(),vote.payload()).record()) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=7)
                throw new IllegalArgumentException("installed source successor changed");
            V53AppliedEndWorker.print(Map.of("event","RETURNED_ACCEPT","record",accepted));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("installed source process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","accept",accepted,"peakImages",peak[0],"runtimeEnabled",false));
    }
}
