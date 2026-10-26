package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh-process reader: no fixture object, caller grant list or historical Owned set. */
public final class V53OwnedGenerationWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);String mode=args[2];
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),
                UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var budget=new MembershipResources(512*MembershipResources.MIB);
        try(var read=MembershipGrantJournal.readRetainedHistory(path,application,history,identity,budget,event->{
            if(!mode.equals("read") && mode.substring(mode.indexOf(':')+1).equals(event)) {
                System.out.println("CUT "+event);System.out.flush();
                if(mode.startsWith("halt:"))Runtime.getRuntime().halt(23);
                try {Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
            }
        })) {
            var capsule=read.capsule();var ancestry=read.ancestry();
            var images=new TreeMap<String,String>();read.images().forEach((h,bytes)->images.put(h,hash(bytes)));
            int copiedObservations=capsule.verifiedAncestry(ancestry).stream().mapToInt(b->b.owned.size()).sum();
            System.out.print(new String(canonical(Map.of("status","PASS","cut",capsule.context.cut,"packet",hash(capsule.packet.bytes()),
                    "manifest",read.manifest().digest(),"ancestry",hash(ancestry),"images",images.entrySet().stream().map(v->Map.of("digest",v.getKey(),"actual",v.getValue())).toList(),"copiedObservations",copiedObservations),65536),java.nio.charset.StandardCharsets.UTF_8));
        }
        if(budget.usage().leases()!=0)throw new AssertionError("retained reader leaked resources");
    }
}
