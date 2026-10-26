package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Fresh owner supplied only immutable local paths and the requested new ballot. */
public final class V53OwnedRecoveryWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);String operation=args[2];
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var budget=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();var result=new TreeMap<String,Object>();
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,history,identity,budget,MembershipGrantJournal.MAXIMUM,event->{
            events.add(event);
            if(operation.equals("retire") && args.length==5 && event.equals(args[4])) {
                System.out.println("CUT "+event);System.out.flush();
                if(args[3].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
            }
        })) {
            if(operation.equals("allocate"))result.put("counter",owner.reserveCounter());
            else if(operation.equals("prepare")) {
                var ballot=object(parse(Files.readAllBytes(Path.of(args[3])),4096));owner.prepareCurrent(ballot);
                result.put("basis",owner.originalBasis().orElseThrow().digest());
            }else if(operation.equals("retire"))owner.retireInactive();
            else if(!operation.equals("inspect"))throw new IllegalArgumentException("worker operation");
            var copy=owner.floorCopyCurrent();result.put("cut",copy.capsule.context.cut);result.put("manifest",copy.generation.digest());
            var source=owner.originalSource();result.put("sourceCut",source.capsule.context.cut);
            result.put("copiedObservations",copy.capsule.verifiedAncestry(copy.fileNames().contains("ancestry.gsr")?copy.fileBytes("ancestry.gsr"):new byte[0]).stream().mapToInt(b->b.owned.size()).sum());
        }
        if(budget.usage().leases()!=0)throw new AssertionError("native recovery reservations leaked");
        result.put("events",events);result.put("status","PASS");System.out.print(new String(canonical(result,65536),java.nio.charset.StandardCharsets.UTF_8));
    }
}
