package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** No supplied certificate, checkpoint, image or caller vote observations. */
public final class V53PendingPublicationWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var record=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)record.value().get("groupId"))),UUID.fromString((String)record.value().get("historyId")),record.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,root,identity,resources,MembershipGrantJournal.MAXIMUM,event->System.out.println("EVENT "+event))) {
            var applied=owner.applyCurrent(builder().configuration(),storage(application,2));
            V53PendingPublicationTest.save(owner.pendingPublication(applied),Path.of(args[2]));
            if(!owner.floorCopyCurrent().capsule.context.cut.get("index").equals(0L))throw new AssertionError("pending target published");
        }
        if(resources.usage().leases()!=0 || resources.usage().queued()!=0)throw new AssertionError("pending target resource leak");
        System.out.println("RESULT PASS");
    }
}
