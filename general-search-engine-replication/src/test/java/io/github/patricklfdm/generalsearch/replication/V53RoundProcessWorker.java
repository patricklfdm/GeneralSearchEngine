package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Resumes the exact original third-slot request; the child creates no replacement history. */
public final class V53RoundProcessWorker {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),seed=root.getParent().resolve("seed"),node=root.resolve("node-1");String point=args[1],mode=args[2];
        var raw=decode(Files.readAllBytes(node.resolve("root.gsr")),"records","ROOT");
        var identity=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)raw.value().get("groupId"))),
                UUID.fromString((String)raw.value().get("historyId")),HexFormat.of().formatHex(Arrays.copyOfRange(raw.bytes(),16,48)));
        var original=MembershipPendingAccept.decode(Files.readAllBytes(seed.resolve("originals/slot-3/node-1/pending.accept")));
        var observed=object(parse(Files.readAllBytes(seed.resolve("observations.json")),65536));
        var all=V53JournalApplicationTest.readObservations(observed.get("all"));
        var accepts=V53JournalApplicationTest.readObservations(observed.get("accepts"));var proofs=V53JournalApplicationTest.readObservations(observed.get("proofs"));
        var phased=new HashSet<>(accepts);phased.addAll(proofs);
        var acks=new ArrayList<Decoded>();var checkpoints=new HashSet<Owned>();var groups=new TreeMap<Long,List<Decoded>>();var statements=new TreeMap<Long,Decoded>();
        for(int n:List.of(1,2,3)) {
            Path end=seed.resolve("originals/slot-3/node-"+n+"/applied-end");var ack=decode(Files.readAllBytes(end.resolve("ack.gsr")),"records","CHECKPOINT_ACK");
            acks.add(ack);checkpoints.add(owned(ack));
            for(String name:List.of("ancestor-0","parent")) {
                var statement=decode(Files.readAllBytes(end.resolve(name+"-statement.gsr")),"records","CHECKPOINT");
                long start=number(object(statement.value().get("start")).get("index"));statements.put(start,statement);
                groups.computeIfAbsent(start,k->new ArrayList<>()).add(decode(Files.readAllBytes(end.resolve(name+"-ack.gsr")),"records","CHECKPOINT_ACK"));
            }
        }
        var bridges=new ArrayList<MembershipSelection.Bridge>();
        for(var group:groups.entrySet())bridges.add(new MembershipSelection.Bridge(statements.get(group.getKey()),group.getValue(),
                group.getValue().stream().map(V53RoundProcessWorker::owned).collect(java.util.stream.Collectors.toSet())));
        var app=new V53ApplicationReplayTest();app.temp=root;var resources=new MembershipResources(512*MembershipResources.MIB);var counts=new HashMap<String,Integer>();
        try(var store=MembershipGrantJournal.openApplying(node,identity,V53DeclarationsTest.node(1),resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,all),event->{
            V53AppliedEndWorker.print(Map.of("event",event));String effective=event;
            if(event.equals("INSTALL_MEMBER_WRITTEN") || event.equals("INSTALL_MEMBER_FORCED")) {
                int index=counts.merge(event,1,Integer::sum)-1;
                var manifest=decode(Files.readAllBytes(node.resolve("generations/a/generation.gsr")),"records","GENERATION");
                var names=list(manifest.value().get("files")).stream().map(v->(String)object(v).get("path")).filter(n->!n.endsWith(".image")).sorted().toList();
                if(names.get(index).equals(MembershipSelectionCoverage.FILE)) {
                    effective=event.replace("INSTALL_MEMBER","ROUND_COVERAGE");V53AppliedEndWorker.print(Map.of("event",effective));
                }
            }
            if(effective.equals(point)) {
                if(mode.equals("halt"))Runtime.getRuntime().halt(73);
                if(mode.equals("kill")) {
                    V53AppliedEndWorker.print(Map.of("event","AWAITING_KILL","cut",point));
                    try{Thread.sleep(30_000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                    throw new java.io.IOException("external kill absent");
                }
            }
        })) {
            var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
            var manifest=decode(Files.readAllBytes(node.resolve("generations/"+selector.value().get("generation")+"/generation.gsr")),"records","GENERATION");
            long index=number(object(manifest.value().get("cut")).get("index"));
            if(index!=2 && index!=3)throw new IllegalArgumentException("unexpected round process cut");
            if(index==2) {
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
                if(vote==null){store.acceptCurrent(original.entry(),original.payload());vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));}
                if(vote.proof()==null){store.proveCurrent(original.proof(),accepts);vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));}
                if(vote.certificate()==null)store.certifyCurrent(original.certificate(),phased);
                store.publishCurrent(store.applyCurrent(app.configuration(),app.storage(),phased),acks,checkpoints,bridges);
            }
            var copy=store.floorCopyCurrent();
            if(store.currentCertificate().isPresent() || store.currentOwnedTail().isPresent() || number(copy.capsule.context.cut.get("index"))!=3)
                throw new IllegalArgumentException("incomplete round publication");
            V53AppliedEndWorker.print(Map.of("status","PASS","manifest",copy.generation.digest(),"selectedIndex",3L,"journalPublication",true));
        }
        if(resources.usage().leases()!=0)throw new IllegalArgumentException("round process lease leak");
    }
    private static Owned owned(Decoded ack) {
        var v=ack.value();return new Owned((String)v.get("voter"),UUID.fromString((String)v.get("incarnation")),ack.digest(),cutDigest(object(v.get("cut"))));
    }
}
