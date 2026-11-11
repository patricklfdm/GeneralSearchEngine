package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;
import static io.github.patricklfdm.generalsearch.replication.V53TransferFaultsTest.*;

/** Original native record exports revoked after materialization but before handler return.
 * Fault clocks and local higher-ballot observation are explicit injections, not remote votes. */
class V53TransferReplyLifetimeTest {
    @TempDir Path temp;
    static final List<String> BOUNDARIES=List.of("offer","data","commit","cached-commit");
    static final List<String> FAULTS=List.of("expiry","service-close","owner-close","higher-ballot");

    @Test void serviceCloseRevokesOutsideTheActiveHandlerAndThenDrains()throws Exception {
        Path root=Files.createDirectory(temp.resolve("service-close"));
        scenario(root,3,"offer","service-close");
        var events=list(parse(Files.readAllBytes(root.resolve("events.json")),1024*1024));
        assertEquals(1,events.stream().map(MembershipFormat::object).filter(v->v.get("event").equals("REVOKED")).count());
    }

    static void resource(List<Map<String,Object>> rows,String side,String event,Decoded q,Decoded a,MembershipResources budget) {
        var row=new TreeMap<String,Object>();row.put("side",side);row.put("event",event);row.put("request",encoded(q));
        if(a!=null)row.put("response",encoded(a));row.put("resources",usage(budget));rows.add(row);
    }
    static void wire(Trace trace,List<Map<String,Object>> rows,String side,String event,Decoded q,Decoded a,MembershipResources budget)throws java.io.IOException {
        synchronized(trace){trace.wire(side,event,q,a);resource(rows,side,event,q,a,budget);}
    }

    static void snapshot(V53BootstrapPublicationTest.Fixture fixture,Path path)throws Exception {
        Files.createDirectory(path);
        for(var target:fixture.request.targets())
            V53JournalApplicationTest.copy(target.replicaDirectory(),path.resolve(target.identity().nodeId().value()));
    }
    static Decoded request(MembershipSelection.Source source,MembershipIdentity reader,UUID trace,long sequence,String kind,Map<String,Object> payload) {
        return decode(encode("wire",kind,Map.of("root",source.capsule.context.root,"view",source.capsule.context.authority(),
                "ballot",source.basis.value().get("ballot"),"sender",MembershipBootstrapSeed.identity(reader),
                "recipient",MembershipBootstrapSeed.identity(source.owner),"trace",trace.toString(),"sequence",sequence,"payload",payload)),"wire",kind);
    }
    @Test void materializedRepliesCannotOutliveOriginalScope()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-transfer-reply-lifetime/run-"+UUID.randomUUID()));
        System.out.println("v53TransferReplyLifetimeEvidence="+evidence.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();
        try {
            for(int size:List.of(3,4,5))for(String boundary:BOUNDARIES)for(String fault:FAULTS) {
                String name=size+"-"+boundary+"-"+fault;Path root=Files.createDirectory(evidence.resolve(name));
                scenario(root,size,boundary,fault);rows.add(Map.of("case",name,"size",size,"boundary",boundary,"fault",fault));
                System.out.println("v53TransferReplyLifetimeCase="+name+" PASS");
            }
        }finally {
            Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-transfer-reply-lifetime-v2",
                    "status",rows.size()==48?"PASS":"INCOMPLETE","cases",rows,"publicRuntime",false,"phase3Complete",false),65536));
        }
    }
    void scenario(Path root,int size,String boundary,String fault)throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;var trace=new Trace("reply-lifetime");
        var receiving=resources();var ref=new AtomicReference<MembershipTransferService>();var injected=new AtomicBoolean();
        var closing=new AtomicReference<CompletableFuture<Void>>();
        var resourceRows=new ArrayList<Map<String,Object>>();
        boolean success=false;Path source=Files.createDirectory(root.resolve("source"));
        try(var group=helper.new Group(size,source)) {
            var fixture=group.fixture;fixture.ownedHistory=true;
            try(var owner=fixture.open(fixture.request.targets().getFirst(),"transfer-fault-source")) {
                var original=owner.beginActivation();var promise=owner.promised().orElseThrow();var ballot=object(original.basis.value().get("ballot"));
                snapshot(fixture,source.resolve("captured"));Path exported=Files.createDirectory(source.resolve("exported"));var contents=new ArrayList<Map<String,Object>>();
                try(var export=owner.exportSource(original.basis,BUDGET)) {
                    for(var content:export.contents()) {
                        Files.write(exported.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));
                        contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                    }
                }
                contents.sort(Comparator.comparing(row->(String)row.get("digest")));
                Files.write(source.resolve("contents.json"),canonical(contents,65536));snapshot(fixture,source.resolve("after"));
                var baseline=usage(fixture.resources);var bounds=V53TransferServiceTest.bound(2);long started=System.nanoTime();var offset=new AtomicLong();
                int chunks=(promise.bytes().length+1023)/1024;long commitSequence=chunks+2L;
                var commits=new AtomicInteger();var higher=new TreeMap<String,Object>(ballot);higher.put("counter",number(ballot.get("counter"))+1);
                var service=new MembershipTransferService(owner,ballot,fixture.resources,bounds,
                        ()->owner.checkActivation(original.basis,null,false),()->System.nanoTime()+offset.get(),started,BUDGET,(event,q,a)->{
                    if(!event.equals("TRANSFER_BEFORE_REPLY"))return;
                    synchronized(trace) {
                        trace.add("MATERIALIZED","request",encoded(q),"response",encoded(a),"usage",V53TransferServiceTest.observed(ref.get().usage()));
                        resource(resourceRows,"server",event,q,a,fixture.resources);
                    }
                    boolean at=switch(boundary) {
                        case "offer"->a.kind().equals("SOURCE_OFFER");
                        case "data"->a.kind().equals("CHUNK");
                        case "commit"->a.kind().equals("TRANSFER_COMMIT");
                        case "cached-commit"->a.kind().equals("TRANSFER_COMMIT") && commits.incrementAndGet()==2;
                        default->throw new AssertionError(boundary);
                    };
                    if(at && injected.compareAndSet(false,true)) {
                        trace.add("REVOKE","request",encoded(q),"fault",fault);
                        switch(fault) {
                            case "expiry"->{offset.set(BUDGET);trace.add("CLOCK_OFFSET","offset",BUDGET);}
                            case "service-close"->{
                                // A handler cannot synchronously wait for its own drain.
                                // Observe real revocation here; join the external closer
                                // only after this callback and the transport call return.
                                closing.set(CompletableFuture.runAsync(()->ref.get().close()));
                                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
                                while(!ref.get().usage().closed()) {
                                    if(System.nanoTime()>=deadline)throw new java.io.IOException("external service close did not revoke");
                                    java.util.concurrent.locks.LockSupport.parkNanos(TimeUnit.MILLISECONDS.toNanos(1));
                                }
                            }
                            case "owner-close"->owner.close();
                            case "higher-ballot"->{owner.observeCurrent(higher);trace.add("OBSERVED_BALLOT","ballot",higher);
                                assertThrows(MembershipGrantJournal.HigherBallot.class,()->owner.checkActivation(original.basis,null,false));}
                            default->throw new AssertionError(fault);
                        }
                        trace.add("REVOKED","request",encoded(q));
                    }
                });ref.set(service);
                try(service) {
                    var server=group.start(0,(peer,q)->service.handle(peer,q),(event,q,a)->wire(trace,resourceRows,"server",event,q,a,fixture.resources),bounds,fixture.resources);
                    var client=group.start(1,group::status,(event,q,a)->wire(trace,resourceRows,"client",event,q,a,receiving),bounds,receiving);
                    var reader=group.identities.get(1);UUID id=UUID.randomUUID(),traceId=UUID.randomUUID();
                    var requests=new ArrayList<Decoded>();var answers=new ArrayList<String>();
                    requests.add(request(original,reader,traceId,1,"CHUNK",Map.of("id",id.toString(),"action","REQUEST","offset",0L,"digest",promise.digest(),"bytes","")));answers.add("SOURCE_OFFER");
                    for(int at=0;at<promise.bytes().length;at+=1024) {
                        requests.add(request(original,reader,traceId,requests.size()+1L,"CHUNK",Map.of("id",id.toString(),"action","REQUEST","offset",(long)at,"digest",promise.digest(),"bytes","")));answers.add("CHUNK");
                    }
                    requests.add(request(original,reader,traceId,commitSequence,"TRANSFER_COMMIT",Map.of("id",id.toString(),"digest",promise.digest())));answers.add("TRANSFER_COMMIT");
                    if(boundary.equals("cached-commit")){requests.add(requests.getLast());answers.add("TRANSFER_COMMIT");}
                    int stop=switch(boundary){case "offer"->0;case "data"->1;default->requests.size()-1;};
                    trace.add("OPEN","started",started,"budget",BUDGET,"source",original.basis.digest());
                    for(int n=0;n<=stop;n++) {
                        call(trace,server,client,original.owner,requests.get(n),answers.get(n),started+BUDGET,n==stop);
                    }
                    if(closing.get()!=null)closing.get().get(15,TimeUnit.SECONDS);
                    assertEquals(1,trace.events.stream().filter(v->v.get("event").equals("REVOKED")).count(),
                            "injection itself must complete before its IO failure can qualify");
                    assertTrue(injected.get());assertEquals(new MembershipTransferService.Usage(0,0,0,true),service.usage());
                    trace.add("DRAINED","usage",V53TransferServiceTest.observed(service.usage()),"resources",usage(fixture.resources));
                    if(fault.equals("expiry")){offset.set(0);trace.add("RESET_CLOCK","offset",0L);}
                    // Exact retry and a new trace must both remain unable to reopen this scope.
                    var last=requests.get(stop);call(trace,server,client,original.owner,last,answers.get(stop),started+BUDGET,true);
                    var fresh=request(original,reader,UUID.randomUUID(),1,"CHUNK",object(requests.getFirst().value().get("payload")));
                    trace.add("FRESH_TRACE");call(trace,server,client,original.owner,fresh,"SOURCE_OFFER",started+BUDGET,true);
                    trace.add("AFTER_PROBES","usage",V53TransferServiceTest.observed(service.usage()));
                }
                for(var transport:group.transports)transport.close();
                assertEquals(fault.equals("owner-close")?0:baseline.get("leases"),usage(fixture.resources).get("leases"));
                if(!fault.equals("owner-close"))assertEquals(baseline,usage(fixture.resources));
                assertEquals(0,receiving.usage().leases());
                trace.add("RESOURCES","baseline",baseline,"after",usage(fixture.resources),"clientAfter",usage(receiving));
            }finally {Files.write(root.resolve("calls.json"),canonical(fixture.calls,1024*1024));}
            fixture.snapshot("unused-final");
            Files.move(source.resolve("unused-final"),root.resolve("after"));
            trace.add("CLOSED","resources",usage(fixture.resources),"clientResources",usage(receiving));success=true;
        }finally {
            Files.write(root.resolve("events.json"),canonical(trace.events,1024*1024));
            Files.write(root.resolve("transport-resources.json"),canonical(Map.of("schema","gse-v53-transfer-reply-resources-v1","rows",resourceRows),1024*1024));
            Files.write(root.resolve("result.json"),canonical(Map.of("size",size,"boundary",boundary,"fault",fault,"status",success?"PASS":"FAIL"),65536));
        }
    }
    static void call(Trace trace,MembershipTransport server,MembershipTransport client,MembershipIdentity owner,Decoded q,String answer,long deadline,boolean fails)throws Exception {
        trace.add("CALL","request",encoded(q),"expected",answer,"deadline",deadline);
        var result=client.exchange(owner,q,answer,deadline);
        if(fails) {
            var failure=V53MembershipTransportTest.failure(result);
            trace.add("FAILURE","request",encoded(q),"reason",failure.reason.name());assertEquals(MembershipTransport.Reason.IO,failure.reason);
        }else {
            var response=result.get(15,TimeUnit.SECONDS);trace.add("REPLY","request",encoded(q),"response",encoded(response));
        }
        drain(server,client);
    }
}
