package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;

/** Real source pull retries, cached replies and transfer-service teardown. */
class V53SourceControlResourcesTest {
    @TempDir Path temp;
    static final List<String> CASES=List.of("lost-offer","lost-data","lost-commit","exhausted-offer");
    static String encoded(Decoded frame){return Base64.getEncoder().encodeToString(frame.bytes());}
    @Test void originalRequestsResponsesAndCompletedCacheKeepSeparateLifetimes()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-source-control-resources/run-"+UUID.randomUUID()));
        System.out.println("v53SourceControlResources="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(String mode:CASES) {
            Path raw=Files.createDirectory(evidence.resolve(mode));var helper=new V53MembershipTransportTest();helper.temp=temp;
            var capture=new AtomicReference<V53ResourceTransitionCapture>();
            var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>() {
                @Override public boolean add(Map<String,Object> event){capture.get().event(size(),event);return super.add(event);}
            });
            var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var drops=new AtomicInteger();
            try(var group=helper.new Group(3,raw)) {
                var f=group.fixture;f.ownedHistory=true;
                capture.set(new V53ResourceTransitionCapture(raw,group.capsule.context.root));
                var serverBudget=capture.get().create(group.identities.get(0),0);
                var clientBudget=capture.get().create(group.identities.get(1),0);
                try(var owner=f.open(f.request.targets().getFirst(),"source-control")) {
                    var source=owner.beginActivation();var promise=owner.promised().orElseThrow();var ballot=object(source.basis.value().get("ballot"));
                    var captured=Files.createDirectory(raw.resolve("captured"));
                    for(var target:f.request.targets())V53JournalApplicationTest.copy(target.replicaDirectory(),captured.resolve(target.identity().nodeId().value()));
                    var contents=new ArrayList<Map<String,Object>>();var exported=Files.createDirectory(raw.resolve("exported"));
                    try(var export=owner.exportSource(source.basis,BUDGET)) {
                        for(var content:export.contents()) {
                            Files.write(exported.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));
                            contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                        }
                    }
                    contents.sort(Comparator.comparing(v->(String)v.get("digest")));Files.write(raw.resolve("contents.json"),canonical(contents,65536));
                    var bounds=V53TransferServiceTest.bound(2);long start=System.nanoTime();var last=new AtomicReference<Decoded>();
                    var serviceEvents=(MembershipTransport.Events)(event,q,a)->{
                        var row=new TreeMap<String,Object>(Map.of("node","node-1","event",event,"request",encoded(q)));
                        if(a!=null)row.put("response",encoded(a));events.add(row);
                    };
                    var service=new MembershipTransferService(owner,ballot,serverBudget,bounds,()->owner.checkActivation(source.basis,null,false),System::nanoTime,start,BUDGET,serviceEvents);
                    var trace=new V53ConnectionTrace("node-1",events,wire);
                    var server=group.start(0,service,new MembershipTransport.Events() {
                        @Override public void at(String event,Decoded q,Decoded a){throw new IllegalStateException("connection required");}
                        @Override public void at(String event,Decoded q,Decoded a,MembershipTransport.Connection connection)throws IOException {
                            synchronized(events) {
                                trace.at(event,q,a,connection);
                                String wanted=mode.endsWith("offer")?"SOURCE_OFFER":mode.equals("lost-data")?"CHUNK":"TRANSFER_COMMIT";
                                if(event.equals("BEFORE_RESPONSE_WRITE") && a.kind().equals(wanted) && (drops.get()==0 || mode.equals("exhausted-offer"))) {
                                    drops.incrementAndGet();wire.getLast().put("withheld",true);
                                    events.add(Map.of("node","node-1","event","SOURCE_REPLY_DROP","connection",connection.id().toString(),"request",q.digest()));
                                    throw new IOException("declared source reply loss");
                                }
                            }
                        }
                        @Override public void failed(boolean outbound,Decoded q,MembershipTransport.Reason reason,MembershipTransport.Connection connection){trace.failed(outbound,q,reason,connection);}
                    },bounds,serverBudget);
                    var client=group.start(1,group::status,new V53ConnectionTrace("node-2",events,wire),bounds,clientBudget);
                    MembershipSourcePull.Link link=(peer,q,kind,deadline)->{
                        last.set(q);events.add(Map.of("node","node-2","event","SOURCE_CALL","request",encoded(q),"deadline",deadline));
                        return client.exchange(peer,q,kind,deadline).handle((reply,error)->{
                            var row=new TreeMap<String,Object>(Map.of("node","node-2","event",error==null?"SOURCE_REPLY":"SOURCE_FAILURE","request",encoded(q)));
                            if(error==null)row.put("response",encoded(reply));else row.put("reason",((MembershipTransport.Failure)V53TransferFaultsTest.cause(error)).reason.name());
                            events.add(row);if(error!=null)throw new CompletionException(error);return reply;
                        });
                    };
                    try(service) {
                        try(var pull=new MembershipSourcePull(source.capsule,group.identities.get(1),group.identities.get(0),ballot,UUID.randomUUID(),clientBudget,bounds,link,()->{},System::nanoTime,start,BUDGET)) {
                            if(mode.equals("exhausted-offer"))assertThrows(MembershipTransport.Failure.class,()->pull.fetchRecord(promise.digest(),"PROMISE",v->{}));
                            else {
                                var result=pull.fetchRecord(promise.digest(),"PROMISE",v->V53RecordExchangeTest.promise(v,source.capsule.context,ballot));
                                assertArrayEquals(promise.bytes(),result.bytes());Files.write(raw.resolve("record.gsr"),result.bytes());
                            }
                        }
                        V53TransferFaultsTest.drain(server,client);events.add(Map.of("node","node-2","event","SOURCE_PULL_CLOSED"));
                        assertEquals(0,clientBudget.usage().leases());
                        if(!mode.equals("exhausted-offer")) {
                            events.add(Map.of("node","node-2","event","SOURCE_CACHE_RETRY","request",encoded(last.get())));
                            assertEquals("TRANSFER_COMMIT",client.exchange(group.identities.get(0),last.get(),"TRANSFER_COMMIT",start+BUDGET).get(10,TimeUnit.SECONDS).kind());
                            V53TransferFaultsTest.drain(server,client);
                        }
                        events.add(Map.of("node","node-1","event","SOURCE_SERVICE_CLOSE_BEGIN"));
                    }
                    events.add(Map.of("node","node-1","event","SOURCE_SERVICE_CLOSE_RETURNED"));
                    assertEquals(0,serverBudget.usage().leases());assertEquals(mode.equals("exhausted-offer")?3:1,drops.get());
                }
                f.snapshot("after");
            }
            byte[] bytes=V53EvidenceArray.encode(events,4*1024*1024);Files.write(raw.resolve("events.json"),bytes);
            Files.write(raw.resolve("wire.json"),canonical(wire,4*1024*1024));capture.get().save(bytes);
            cases.add(Map.of("case",mode,"drops",drops.get()));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-source-control-resources-v1","status","PASS","cases",cases,
                "execution","loopback-tcp-component","completeMembershipHistory",false,"phase3Complete",false),65536));
    }
    @Test void sessionOwnersAreBoundedDistinctAndIncludeOriginalIdentities() {
        var source=V53DeclarationsTest.node(1);var reader=V53DeclarationsTest.node(2);var trace=UUID.randomUUID();
        String a=MembershipSourceResources.session("source-session","a".repeat(64),source,reader,trace);
        String b=MembershipSourceResources.session("source-session","a".repeat(64),source,reader,trace);
        assertNotEquals(a,b);assertTrue(a.length()<=128);assertEquals(a.substring(0,79),b.substring(0,79));
        for(String changed:List.of(MembershipSourceResources.session("source-session","b".repeat(64),source,reader,trace),
                MembershipSourceResources.session("source-session","a".repeat(64),reader,source,trace),
                MembershipSourceResources.session("source-session","a".repeat(64),source,reader,UUID.randomUUID())))
            assertNotEquals(a.substring(0,79),changed.substring(0,79));
    }
}
