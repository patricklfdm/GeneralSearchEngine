package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Exact original owner recovery; only local storage, never online membership. */
public final class V53ContextMixedProcessWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),node=path.resolve("store"),rootPath=path.getParent();
        String point=args[1],mode=args[2];boolean duringOpen=Boolean.parseBoolean(args[3]),acceptance=args[4].equals("accept");
        String[] parts=point.split("@");int ordinal=parts.length==2?Integer.parseInt(parts[1]):1;int[] hits={0},peak={0};boolean[] armed={duringOpen};
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var observations=V53JournalApplicationTest.readObservations(object(parse(Files.readAllBytes(rootPath.resolve("inputs.json")),65536)).get("observations"));
        Path initial=rootPath.resolve("reference/"+(acceptance?"round-24/source-retired/node-1":"retired/node-2"));
        byte[] original=Files.readAllBytes(initial.resolve("pending.accept"));var vote=MembershipPendingAccept.decode(original);
        String obsolete=(String)vote.promise().value().get("basisId");var resources=new MembershipResources(512*MembershipResources.MIB);
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
            if(acceptance) {
                var ack=owner.acceptRetainedCurrent(vote.entry(),vote.payload());V53AppliedEndWorker.print(Map.of("event","EXPLICIT_ACCEPT_RETURNED","record",ack.record()));
                if(!ack.equals(owner.acceptRetainedCurrent(vote.entry(),vote.payload())))throw new IllegalArgumentException("mixed successor duplicate changed");
                V53AppliedEndWorker.print(Map.of("event","EXPLICIT_ACCEPT_RETURNED","record",ack.record()));
                var accepted=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
                if(!Arrays.equals(vote.entry().bytes(),accepted.entry().bytes()) || !Arrays.equals(vote.payload(),accepted.payload())
                        || !ack.record().equals(accepted.accept().digest()) || number(object(accepted.accept().value().get("ballot")).get("counter"))!=24
                        || accepted.proof()!=null || accepted.certificate()!=null || Files.exists(node.resolve("pending.context")) || Files.exists(node.resolve("floor-copies")))
                    throw new IllegalArgumentException("mixed successor incomplete");
            }else {
                if(Files.exists(node.resolve(MembershipSourceRetirementFiles.FILE)) || Files.exists(node.resolve("sources/"+obsolete)))owner.retireSource(obsolete);
                if(!Arrays.equals(original,owner.retainPendingContext().vote().bytes()) || Files.exists(node.resolve("sources/"+obsolete)))
                    throw new IllegalArgumentException("mixed source retirement changed original");
                V53AppliedEndWorker.print(Map.of("event","EXPLICIT_RETIRE_RETURNED"));
            }
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("mixed process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","operation",acceptance?"accept":"source-retirement","peakImages",peak[0],"runtimeEnabled",false));
    }
}
