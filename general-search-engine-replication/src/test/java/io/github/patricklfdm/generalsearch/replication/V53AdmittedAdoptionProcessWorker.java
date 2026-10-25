package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Reopens exact admitted authority; no peer packet or vote is manufactured. */
public final class V53AdmittedAdoptionProcessWorker {
    public static void main(String[] args)throws Exception {
        Path inputs=Path.of(args[0]);String point=args[1],mode=args[2];
        var data=object(parse(Files.readAllBytes(inputs),1024*1024));
        var observations=V53JournalApplicationTest.readObservations(data.get("observations"));
        Path node=Path.of((String)data.get("node")),materialization=Path.of((String)data.get("materialization"));Path inputDirectory=inputs.getParent().resolve("remote");
        var packet=MembershipSourcePacket.decode(Files.readAllBytes(inputDirectory.resolve("source.gscp")));
        var images=new TreeMap<String,byte[]>();
        for(String hash:packet.images().keySet())images.put(hash,Files.readAllBytes(inputDirectory.resolve(hash+".image")));
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
            var manifest=owner.adoptCurrent(packet,images,List.of());
            if(!Arrays.equals(manifest.bytes(),owner.adoptCurrent(packet,images,List.of()).bytes()))throw new IllegalArgumentException("adoption duplicate changed exact final generation");
            var offered=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));
            offered.put("counter",number(offered.get("counter"))+1);
            try {owner.prepareCurrent(offered);throw new IllegalStateException("removed voter admitted a new grant");}
            catch(IllegalArgumentException expected) {
                if(!expected.getMessage().equals("grant local eligible identity"))throw expected;
            }
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("admitted adoption process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"runtimeEnabled",false));
    }
}
