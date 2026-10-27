package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual original disk authority only, without caller historical vote receipts. */
public final class V53NativeRetirementWorker {
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);
        var record=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)record.value().get("groupId"))),UUID.fromString((String)record.value().get("historyId")),record.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,root,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            System.out.println("EVENT "+event);System.out.flush();
            if(event.equals(args[3])) {
                System.out.println("CUT "+event);System.out.flush();if(args[2].equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new java.io.IOException(e);}
                throw new java.io.IOException("external kill did not arrive");
            }
        })) {
            String certificate=owner.currentCertificate().orElseThrow().digest();
            owner.retireSupersededApplication(builder().configuration(),storage(application,2));
            owner.retireSupersededApplication(builder().configuration(),storage(application,2));
            if(!certificate.equals(owner.currentCertificate().orElseThrow().digest()))throw new AssertionError("retirement changed certificate");
            if(Files.exists(path.resolve("applied-end")) || Files.exists(path.resolve("application-replay")))throw new AssertionError("retirement left derived staging");
            System.out.println("RESPONSE "+certificate+" "+V53NativeRetirementTest.publishedIndex(path));
        }
        if(resources.usage().leases()!=0 || resources.usage().queued()!=0)throw new AssertionError("retirement resource leak");
    }
}
