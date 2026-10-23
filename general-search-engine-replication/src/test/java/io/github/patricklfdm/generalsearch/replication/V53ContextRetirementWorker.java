package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real complete owner; only retained generation/context/floor bytes authorize recovery. */
public final class V53ContextRetirementWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),node=path.resolve("store");String point=args[1],mode=args[2];
        var record=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)record.value().get("groupId"))),
                UUID.fromString((String)record.value().get("historyId")),record.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var input=object(parse(Files.readAllBytes(path.getParent().resolve("inputs.json")),65536));
        var observations=V53JournalApplicationTest.readObservations(input.get("observations"));var resources=new MembershipResources(512*MembershipResources.MIB);
        byte[] vote=Files.readAllBytes(node.resolve("pending.accept")),context=Files.readAllBytes(node.resolve("pending.context"));int[] peak={0};
        try(var owner=MembershipGrantJournal.openContextual(node,root,local,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            var ballot=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));ballot.put("counter",24L);owner.observeCurrent(ballot);
            V53AppliedEndWorker.print(Map.of("event","OBSERVED_24"));owner.retireContextOriginal();var original=owner.retainPendingContext();
            if(!Arrays.equals(vote,original.vote().bytes()) || !Arrays.equals(context,Files.readAllBytes(node.resolve("pending.context")))
                    || Files.exists(node.resolve("generations").resolve((String)original.selector().value().get("generation")))
                    || Files.exists(node.resolve("retirement")) || owner.governingFloor().isEmpty())throw new IllegalArgumentException("incomplete exact context retirement");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("context retirement process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","pending",hash(vote),"context",hash(context),"peakImages",peak[0],"runtimeEnabled",false));
    }
}
