package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh owner for protected capture, context rebind and intermediate retirement. */
public final class V53ContextCaptureWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),node=path.resolve("store"),rootPath=path.getParent();
        String point=args[1],mode=args[2];boolean duringOpen=Boolean.parseBoolean(args[3]);
        String[] parts=point.split("@");int ordinal=parts.length==2?Integer.parseInt(parts[1]):1;int[] hits={0},peak={0};boolean[] armed={duringOpen};
        boolean deleting=point.startsWith("SOURCE_RETIREMENT_") || point.startsWith("JOURNAL_ROTATION_");
        var rr=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var observations=V53JournalApplicationTest.readObservations(object(parse(Files.readAllBytes(rootPath.resolve("inputs.json")),65536)).get("observations"));
        var initial=MembershipPendingContext.decode(Files.readAllBytes(rootPath.resolve("initial/pending.context")));
        var prior=MembershipPendingContext.backingPromise(initial);String old=(String)prior.value().get("basisId");
        var ballot=new TreeMap<>(object(prior.value().get("ballot")));ballot.put("counter",23L);
        byte[] vote=Files.readAllBytes(rootPath.resolve("initial/pending.accept"));var resources=new MembershipResources(512*MembershipResources.MIB);
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
            V53AppliedEndWorker.print(Map.of("event","OPEN_RETURNED"));
            // An empty retained decision is deliberately not auto-completed on
            // open. Finish its exact original deletion before replaying a grant.
            if(Files.exists(node.resolve(MembershipSourceRetirementFiles.FILE)))owner.retireSource(old);
            armed[0]=!deleting;
            var basis=owner.prepareCurrent(ballot);V53AppliedEndWorker.print(Map.of("event","RETURNED_GRANT","counter",23,"record",basis.digest()));armed[0]=true;
            if(Files.exists(node.resolve("sources").resolve(old)))owner.retireSource(old);
            if(!Arrays.equals(vote,owner.retainPendingContext().vote().bytes()) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=6)
                throw new IllegalArgumentException("capture recovery changed original/steady bound");
            V53ContextRetirementTest.snapshotOwned(node,path.resolve("recovered"));V53AppliedEndWorker.print(Map.of("event","RECOVERED"));
            ballot.put("counter",24L);var next=owner.prepareCurrent(ballot);V53AppliedEndWorker.print(Map.of("event","RETURNED_GRANT","counter",24,"record",next.digest()));
            owner.retireSource((String)basis.value().get("basisId"));
            if(!Arrays.equals(vote,owner.retainPendingContext().vote().bytes()) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=6)
                throw new IllegalArgumentException("next capture changed original/steady bound");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("capture process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","peakImages",peak[0],"steadyImages",6,"runtimeEnabled",false));
    }
}
