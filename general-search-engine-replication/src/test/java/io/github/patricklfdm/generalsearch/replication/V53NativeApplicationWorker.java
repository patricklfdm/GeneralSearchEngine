package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Original native disk inputs only: no caller certificate, phases or observations. */
public final class V53NativeApplicationWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var record=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)record.value().get("groupId"))),UUID.fromString((String)record.value().get("historyId")),record.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,root,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            System.out.println("EVENT "+event);System.out.flush();
            if(event.equals(args[3])) {
                System.out.println("CUT "+event);System.out.flush();
                if(args[2].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
            }
        })) {
            var applied=owner.applyCurrent(builder().configuration(),storage(application,2));
            var repeated=owner.applyCurrent(builder().configuration(),storage(application,2));
            if(!Arrays.equals(applied.endorsement().acknowledgement().bytes(),repeated.endorsement().acknowledgement().bytes()))throw new AssertionError("native retry changed end");
            System.out.println("RESULT "+new String(canonical(Map.of("certificate",applied.plan().originalCertificate().digest(),
                    "catalog",applied.plan().catalog.digest(),"application",hash(applied.plan().application.image()),
                    "published",owner.floorCopyCurrent().capsule.context.cut,"applied",applied.plan().catalog.value().get("cut"),
                    "ack",Base64.getEncoder().encodeToString(applied.endorsement().acknowledgement().bytes())),16384),java.nio.charset.StandardCharsets.UTF_8));
        }
        if(resources.usage().leases()!=0 || resources.usage().queued()!=0)throw new AssertionError("native application resource leak");
    }
}
