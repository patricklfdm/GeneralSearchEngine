package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Fresh process over an actual, completed native departing FINAL. */
public final class V53DepartingRestartWorker {
    @FunctionalInterface interface Attempt {void run()throws Exception;}
    static String rejected(Attempt action,String expected)throws Exception {
        try {action.run();}catch(IllegalArgumentException error) {
            require(expected.equals(error.getMessage()),"unexpected departure refusal: "+error);return error.getMessage();
        }
        throw new AssertionError("departing member accepted forbidden operation");
    }
    public static void main(String[] args)throws Exception {
        Path path=Path.of(args[0]),application=Path.of(args[1]),evidence=Path.of(args[2]),scratch=Path.of(args[3]);
        String mode=args.length==5?args[4]:"resume";
        require(Set.of("resume","halt","kill").contains(mode),"departure worker mode");
        // The endpoint owns its "incoming" child, but its test-private parent
        // must exist before AdmissionPaths binds that child. Never reuse scratch.
        Files.createDirectory(scratch);
        var root=decode(Files.readAllBytes(path.resolve("root.gsr")),"records","ROOT");
        var identity=MembershipContext.identity(object(decode(Files.readAllBytes(path.resolve("node.gsr")),"records","NODE").value().get("identity")));
        var history=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)root.value().get("groupId"))),UUID.fromString((String)root.value().get("historyId")),root.rootDigest());
        var resources=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();var exchanges=new AtomicInteger();
        var request=decode(Files.readAllBytes(evidence.resolve("publication-request.gsrp")),"wire","PUBLISH");
        byte[] expected=Files.readAllBytes(evidence.resolve("publication-ack.gsrp"));
        var before=V53ReplayFilesTest.files(path);var report=new TreeMap<String,Object>();
        try(var owner=MembershipGrantJournal.openRetainingFuturePeers(path,application,history,identity,resources,MembershipGrantJournal.MAXIMUM,event->{
            events.add(event);
            if(!mode.equals("resume") && event.equals("PUBLICATION_ACK_BEFORE_RETURN")) {
                System.out.println("CUT "+event);System.out.flush();
                if(mode.equals("halt"))Runtime.getRuntime().halt(23);
                try{new CountDownLatch(1).await();}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new java.io.IOException(error);}
            }
        })) {
            var context=owner.activationContext();
            require(number(context.cut.get("index"))==6 && !context.voters().contains(identity.nodeId().value()) && context.catalog.get("active")==null,
                    "reopened native FINAL must preserve departure");
            var bounds=ReplicationBounds.defaults();long budget=TimeUnit.SECONDS.toNanos(120);
            try(var endpoint=new MembershipActivationEndpoint(owner,resources,bounds,(peer,frame,kind,deadline)->{
                        exchanges.incrementAndGet();throw new AssertionError("departed owner acquired new observations");
                    },List.of(),List.of(),scratch.resolve("incoming"),System::nanoTime,budget);
                var transport=new MembershipTransport(owner.activationCapsule(),identity,bounds,resources,endpoint,MembershipTransport.Events.NONE)) {
                var sender=MembershipContext.identity(object(request.value().get("sender")));
                for(int n=0;n<2;n++) {
                    byte[] reply=endpoint.handle(sender,request).bytes();
                    Files.write(evidence.resolve("duplicate-"+(n+1)+".gsrp"),reply);
                    require(Arrays.equals(expected,reply),"restarted departure changed original acknowledgement");
                }
                report.put("duplicateReceipts",3L);
                var proposer=context.identities.get("node-1");var ballot=new TreeMap<>(object(request.value().get("ballot")));
                ballot.put("counter",number(ballot.get("counter"))+1);ballot.put("proposer",proposer.nodeId().value());ballot.put("incarnation",proposer.storageId().toString());
                var values=new TreeMap<>(request.value());values.put("sender",MembershipBootstrapSeed.identity(proposer));
                values.put("recipient",MembershipBootstrapSeed.identity(identity));values.put("view",context.authority());values.put("ballot",ballot);
                values.put("payload",Map.of("promise",owner.promised().orElseThrow().digest()));
                var fresh=decode(encode("wire","PREPARE",values),"wire","PREPARE");
                Files.write(evidence.resolve("fresh-prepare.gsrp"),fresh.bytes());
                report.put("incomingPrepare",rejected(()->endpoint.handle(proposer,fresh),"endpoint outside learner reservation"));
                byte[] afterRejection=endpoint.handle(sender,request).bytes();
                Files.write(evidence.resolve("duplicate-3.gsrp"),afterRejection);
                require(Arrays.equals(expected,afterRejection),"rejected PREPARE fenced completed original acknowledgement");
                try(var round=new MembershipRoundDriver<>(owner,endpoint,resources,bounds,transport,scratch.resolve("round"),System::nanoTime,budget,2,
                        builder().configuration(),storage(application,2),(event,record)->{throw new AssertionError("departed owner entered round: "+event);},
                        MembershipSlotDriver.Events.NONE)) {
                    report.put("activation",rejected(round::start,"native round local member not eligible for activation"));
                    require(round.state()==MembershipRoundDriver.State.FAILED,"departed round did not fail");
                    report.put("readiness",rejected(round::readiness,"native round state/busy"));
                    report.put("submit",rejected(()->round.submit("BARRIER",new byte[0]),"native round state/busy"));
                }
            }
        }
        require(exchanges.get()==0,"reopened departure attempted remote exchange");
        require(events.stream().noneMatch(e->Set.of("ALLOCATOR_FORCED","PROMISE_FORCED","FLOOR_COPIES_FORCED","PUBLICATION_SELECTOR_FORCED").contains(e)),
                "reopened departure created new durable authority");
        require(before.equals(V53ReplayFilesTest.files(path)),"reopened departure changed original store");
        require(resources.usage().leases()==0 && resources.usage().queued()==0,"reopened departure leaked resources");
        report.put("status","PASS");report.put("published",6L);report.put("node",identity.nodeId().value());report.put("events",events);
        report.put("remoteExchanges",exchanges.get());report.put("publicReady",false);
        Files.write(evidence.resolve("restart-result.json"),canonical(report,16384));
        System.out.println("v53DepartingRestart=PASS");
    }
}
