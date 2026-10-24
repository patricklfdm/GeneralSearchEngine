package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh owner for exact source/context/floor handoff; no synthetic recovery authority. */
public final class V53ContextCompletionWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),node=path.resolve("store"),reference=path.getParent().resolve("reference");
        String point=args[1],mode=args[2];String[] parts=point.split("@");int ordinal=parts.length==2?Integer.parseInt(parts[1]):1;int[] hits={0},peak={0};
        var rootRecord=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rootRecord.value().get("groupId"))),
                UUID.fromString((String)rootRecord.value().get("historyId")),rootRecord.rootDigest());
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(node.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var input=object(parse(Files.readAllBytes(path.getParent().resolve("inputs.json")),65536));
        var observations=V53JournalApplicationTest.readObservations(input.get("observations"));
        var original=MembershipPendingAccept.decode(Files.readAllBytes(reference.resolve("reopened/pending.accept")));
        String predecessor=(String)original.promise().value().get("basisId");
        var resources=new MembershipResources(512*MembershipResources.MIB);MembershipContext.Owned acknowledged;
        try(var owner=MembershipGrantJournal.openContextual(node,root,local,resources,(r,p,i)->MembershipCapsule.verify(r,p,i,observations),MembershipGrantJournal.MAXIMUM,event->{
            V53RetirementImagesTest.bounded(resources);peak[0]=Math.max(peak[0],resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
            V53AppliedEndWorker.print(Map.of("event",event));
            if(event.equals(parts[0]) && ++hits[0]==ordinal) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(60_000);}catch(InterruptedException ex){Thread.currentThread().interrupt();throw new java.io.IOException(ex);}
                    throw new java.io.IOException("external kill did not arrive");
                }
            }
        })) {
            V53AppliedEndWorker.print(Map.of("event","OPEN_RETURNED"));
            if(Files.exists(node.resolve("sources").resolve(predecessor)))owner.retireSource(predecessor);
            acknowledged=owner.acceptRetainedCurrent(original.entry(),original.payload());
            V53AppliedEndWorker.print(Map.of("event","RETURNED_ACCEPT","record",acknowledged.record()));
            if(!acknowledged.equals(owner.acceptRetainedCurrent(original.entry(),original.payload())))throw new IllegalArgumentException("changed duplicate acceptance");
            V53AppliedEndWorker.print(Map.of("event","RETURNED_ACCEPT","record",acknowledged.record()));
            var actual=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
            if(!Arrays.equals(original.entry().bytes(),actual.entry().bytes()) || !Arrays.equals(original.payload(),actual.payload())
                    || actual.proof()!=null || actual.certificate()!=null || !acknowledged.record().equals(actual.accept().digest())
                    || Files.exists(node.resolve("pending.context")) || Files.exists(node.resolve("pending.accept.next"))
                    || Files.exists(node.resolve("floor-copies")) || resources.usage().counts().get(MembershipResources.Unit.APPLICATION)!=6)
                throw new IllegalArgumentException("incomplete exact context completion");
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("context completion process lease leak");
        V53AppliedEndWorker.print(Map.of("status","PASS","accept",acknowledged.record(),"peakImages",peak[0],"runtimeEnabled",false));
    }
}
