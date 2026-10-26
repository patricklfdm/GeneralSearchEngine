package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Reopens actual peer owners to obtain original sources, never imported votes. */
public final class V53SelectedRetentionWorker {
    public static void main(String[] args)throws Exception {
        var targets=list(parse(Files.readAllBytes(Path.of(args[0])),65536));var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
        for(Object row:targets) {
            var t=object(row);Path path=Path.of((String)t.get("replica"));var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var owner=open(t,resources,event->{System.out.println("COLLECT "+path.getFileName()+" "+event);System.out.flush();})) {
                var source=owner.originalSource();sources.add(source);
                for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(path.resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
            }
            if(resources.usage().leases()!=0)throw new AssertionError("source owner leak");
        }
        var target=object(targets.get(1));var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=open(target,resources,event->{
            System.out.println("EVENT "+event);System.out.flush();
            if(event.equals(args[2])) {
                System.out.println("CUT "+event);System.out.flush();if(args[1].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                throw new java.io.IOException("external kill did not arrive");
            }
        })) {
            owner.installCurrent(sources,List.of(),images);var state=owner.peerRetentionState();
            System.out.println("RESPONSE "+new String(canonical(Map.of("revision",state.revision(),"digest",state.digest(),"plan",parse(state.plan().bytes(),32768)),65536),java.nio.charset.StandardCharsets.US_ASCII));
        }
        if(resources.usage().leases()!=0)throw new AssertionError("selected owner leak");
    }
    private static MembershipGrantJournal open(Map<String,Object> target,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        Path path=Path.of((String)target.get("replica")),application=Path.of((String)target.get("application"));
        var r=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)r.value().get("groupId"))),UUID.fromString((String)r.value().get("historyId")),r.rootDigest());
        return MembershipGrantJournal.openRetainingPeers(path,application,root,identity,resources,MembershipGrantJournal.MAXIMUM,cut);
    }
}
