package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual proposer runtime in a fresh JVM; no external original-vote verifier. */
public final class V53TransitionProcessWorker {
    static void snapshot(String stage)throws java.io.IOException {
        line("SNAPSHOT",stage);require(System.in.read()=='c',"missing parent snapshot acknowledgement");
    }
    static synchronized void line(String kind, Object value) {
        System.out.println(kind+" "+(value instanceof String text?text:new String(canonical(value,16*1024*1024),java.nio.charset.StandardCharsets.UTF_8)));
        System.out.flush();
    }
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]),raw=Path.of(args[2]),scratch=Path.of(args[6]);
        String mode=args[3],point=args[5];long wanted=Long.parseLong(args[4]);
        require(Set.of("halt","kill","resume").contains(mode),"transition worker mode");
        Files.createDirectory(scratch);
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);var index=new AtomicLong();var ordinal=new AtomicInteger();
        var b=ReplicationBounds.defaults();var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        long budget=TimeUnit.MINUTES.toNanos(10);var link=new AtomicReference<MembershipTransport>();
        try(var owner=MembershipGrantJournal.openRetainingFuturePeers(path,application,history,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            line("STORE",Map.of("event",event,"index",index.get()));
            if(!mode.equals("resume") && index.get()==wanted && event.equals(point)) {
                line("CUT",Map.of("index",index.get(),"event",event));
                if(mode.equals("halt"))Runtime.getRuntime().halt(23);
                try{new CountDownLatch(1).await();}catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
            }
        });var endpoint=new MembershipActivationEndpoint(owner,resources,bounds,(peer,request,kind,deadline)->link.get().exchange(peer,request,kind,deadline),
                List.of(),List.of(),scratch.resolve("incoming"),System::nanoTime,budget,builder().configuration(),storage(application,2));
            var transport=new MembershipTransport(owner.activationCapsule(),identity,bounds,resources,endpoint,(event,request,response)->{
                if(event.equals("BEFORE_REQUEST_WRITE") || event.equals("AFTER_REQUEST_READ"))line(event,Base64.getEncoder().encodeToString(request.bytes()));
                if(event.equals("AFTER_RESPONSE_READ") || event.equals("BEFORE_RESPONSE_WRITE"))line(event,Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(response.bytes())));
            });var round=new MembershipRoundDriver<>(owner,endpoint,resources,bounds,transport,scratch.resolve("round"),System::nanoTime,budget,2,
                builder().configuration(),storage(application,2),(event,record)->{
                    if(event.equals("SLOT_BEGIN"))index.set(number(record.value().get("index")));
                    line("ROUND",Map.of("event",event,"record",Base64.getEncoder().encodeToString(record.bytes())));
                    if(event.equals("INSTALLED"))snapshot(mode+"-installed-"+ordinal.incrementAndGet());
                    if(event.equals("SLOT_COMPLETE"))snapshot(mode+"-published-"+index.get());
                },(event,record,voters)->{
                    line("SLOT",Map.of("event",event,"record",Base64.getEncoder().encodeToString(record.bytes()),"voters",voters.stream().sorted().toList()));
                    if(event.equals("APPLIED"))snapshot(mode+"-applied-"+index.get());
                })) {
            link.set(transport);line("OPEN",mode);
            var result=round.start();require(round.state()==MembershipRoundDriver.State.READY,"transition restart not ready");round.readiness();
            var context=owner.activationContext();require(number(context.cut.get("index"))==7 && context.view.get("operation")==null && context.catalog.get("active")==null,"transition incomplete");
            var operation=object(list(context.catalog.get("results")).getLast());require(operation.get("phase").equals("COMPLETED"),"original operation not completed");
            Files.write(raw.resolve("ready.gsrp"),result.bytes());
            Files.write(raw.resolve("ready.json"),canonical(Map.of("state","READY","cut",context.cut,"operation",operation,"publicReady",false),65536));
            line("READY",mode);require(System.in.read()=='s',"missing explicit transition stop");
        }
        require(resources.usage().leases()==0 && resources.usage().queued()==0,"transition child resources leaked");line("CLOSED",mode);
    }
}
