package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Fresh typed receiver: an original forced certificate permits native application recovery. */
public final class V53NativeApplicationIngressWorker {
    private static synchronized void line(String kind,String value){System.out.println(kind+" "+value);System.out.flush();}
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]);String mode=args[2],point=args[3];
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);long budget=TimeUnit.SECONDS.toNanos(120);var bounds=ReplicationBounds.defaults();
        try(var owner=MembershipGrantJournal.openBootstrapped(path,application,history,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            line("EVENT",event);if(event.equals(point)){line("CUT",event);if(mode.equals("halt"))Runtime.getRuntime().halt(23);
                try{Thread.sleep(120000);}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}}
        })) {
            var link=new AtomicReference<MembershipTransport>();
            try(var endpoint=new MembershipVotingEndpoint(owner,resources,bounds,(peer,request,kind,deadline)->{
                    if(mode.equals("resume"))throw new AssertionError("forced certificate recovery must not acquire fresh observations");
                    return link.get().exchange(peer,request,kind,deadline);
                },System::nanoTime,System.nanoTime(),budget,builder().configuration(),storage(application,2));
                var server=new MembershipTransport(owner.activationCapsule(),identity,bounds,resources,endpoint,(event,request,response)->{
                    if(event.equals("AFTER_REQUEST_READ"))line("REQUEST",Base64.getEncoder().encodeToString(request.bytes()));
                    if(event.equals("AFTER_RESPONSE_READ"))line("RECEIVED",new String(canonical(V53SelectedPullTest.wire(request,response),1048576),java.nio.charset.StandardCharsets.UTF_8));
                    if(event.equals("BEFORE_RESPONSE_WRITE"))line("WIRE",new String(canonical(V53SelectedPullTest.wire(request,response),1048576),java.nio.charset.StandardCharsets.UTF_8));
                })) {
                link.set(server);line("READY",mode);if(System.in.read()!='s')throw new AssertionError("missing explicit stop");
            }
        }
        if(resources.usage().leases()!=0 || resources.usage().queued()!=0)throw new AssertionError("voting receiver resource leak");line("CLOSED",mode);
    }
}
