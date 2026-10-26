package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Recovery receives real owner paths, never serialized historical vote observations. */
public final class V53OwnedAdoptionProcessWorker {
    static MembershipIdentity identity(Path path)throws Exception {
        return MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
    }
    public static void main(String[] args)throws Exception {
        var inputs=object(parse(Files.readAllBytes(Path.of(args[0])),65536));String cut=args[1],mode=args[2];
        Path node=Path.of((String)inputs.get("node")),application=Path.of((String)inputs.get("materialization")),source=Path.of((String)inputs.get("source"));
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);MembershipCapsule prefix;Map<String,byte[]> images;int[] peak={0};
        try(var original=MembershipGrantJournal.readRetainedHistory(source,Path.of((String)inputs.get("sourceMaterialization")),root,identity(source),resources,event->{})) {
            prefix=original.capsule();images=original.images();
        }
        if(resources.usage().leases()!=0)throw new AssertionError("source reader reservation leak");
        try(var owner=MembershipGrantJournal.openBootstrapped(node,application,root,identity(node),resources,MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(cut)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",cut));
                    try{Thread.sleep(60_000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            var result=owner.adoptCurrent(prefix,images,List.of());
            if(!Arrays.equals(result.bytes(),owner.adoptCurrent(prefix,images,List.of()).bytes()))throw new IllegalStateException("changed native duplicate");
            var offered=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));offered.put("counter",number(offered.get("counter"))+1);
            try{owner.prepareCurrent(offered);throw new IllegalStateException("removed node admitted new grant");}
            catch(IllegalArgumentException refused){if(!refused.getMessage().equals("grant local eligible identity"))throw refused;}
        }
        if(resources.usage().leases()!=0)throw new AssertionError("native process reservations leaked");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"runtimeEnabled",false));
    }
}
