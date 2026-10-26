package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Removed node recovery supplied only its actual bootstrap-owned paths, no caller history. */
public final class V53OwnedAdoptionWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var rr=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var local=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)rr.value().get("groupId"))),UUID.fromString((String)rr.value().get("historyId")),rr.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();var result=new TreeMap<String,Object>();
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,root,local,resources,MembershipGrantJournal.MAXIMUM,events::add)) {
            var capsule=owner.activationCapsule();var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");
            result.put("manifest",selector.value().get("digest"));result.put("cut",capsule.context.cut);
            try{owner.floorCopyCurrent();throw new IllegalStateException("removed node supplied a governing floor copy");}
            catch(IllegalArgumentException refused){if(!refused.getMessage().equals("floor copy is not a governing voter"))throw refused;result.put("floorRefusal",refused.getMessage());}
            result.put("basisAbsent",owner.originalBasis().isEmpty());result.put("selectionAbsent",owner.originalSelection().isEmpty());
            result.put("promise",owner.promised().orElseThrow().digest());
            try{owner.beginActivation();throw new IllegalStateException("removed node started an election");}
            catch(IllegalArgumentException refused){if(!refused.getMessage().equals("activation requires current voter"))throw refused;result.put("refusal",refused.getMessage());}
        }
        if(resources.usage().leases()!=0)throw new AssertionError("removed owner resource leak");
        result.put("events",events);result.put("status","PASS");System.out.print(new String(canonical(result,65536),java.nio.charset.StandardCharsets.UTF_8));
    }
}
