package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Explicit real 64 MiB queue qualification; no artificial capacity leases. */
class V53SourceQueueQualification {
    @TempDir Path temp;
    static final int CHUNK=4*1024*1024;
    static final long BUDGET=TimeUnit.MINUTES.toNanos(5);
    record Session(int reader, UUID trace, UUID basisTransfer, UUID imageTransfer) {}
    Path raw;
    MembershipResources resources;
    final List<Map<String,Object>> events=new ArrayList<>();
    synchronized void event(String name,Decoded request,Decoded response,MembershipTransport.Connection connection,String reason)throws IOException {
        var row=new TreeMap<String,Object>();row.put("event",name);
        for(var field:List.of("request","response")) {
            var frame=field.equals("request")?request:response;if(frame==null)continue;
            Path path=raw.resolve("frames").resolve(frame.digest()+".bin");
            if(!Files.exists(path))Files.write(path,frame.bytes(),StandardOpenOption.CREATE_NEW);
            row.put(field,frame.digest());
        }
        if(connection!=null)row.put("connection",connection.id().toString());
        if(reason!=null)row.put("reason",reason);
        var point=resources.observationCheckpoint();assertTrue(point.complete());row.put("sequence",point.sequence());
        row.put("queued",point.usage().queued());events.add(row);
    }
    static Decoded request(V53MembershipTransportTest.Group group,Map<String,Object> ballot,Session session,
            long sequence,UUID transfer,String digest,long offset,boolean commit) {
        var payload=commit?Map.<String,Object>of("id",transfer.toString(),"digest",digest):
                Map.<String,Object>of("id",transfer.toString(),"action","REQUEST","offset",offset,"digest",digest,"bytes","");
        return decode(encode("wire",commit?"TRANSFER_COMMIT":"CHUNK",Map.of("root",group.capsule.context.root,
                "view",group.capsule.context.authority(),"ballot",ballot,"sender",MembershipBootstrapSeed.identity(group.identities.get(session.reader())),
                "recipient",MembershipBootstrapSeed.identity(group.identities.getFirst()),"trace",session.trace().toString(),"sequence",sequence,"payload",payload)),"wire",commit?"TRANSFER_COMMIT":"CHUNK");
    }
    Decoded call(MembershipTransport client,MembershipIdentity server,Decoded request,String kind,long deadline)throws Exception {
        event("CALL",request,null,null,null);
        try {
            var reply=client.exchange(server,request,kind,deadline).get(30,TimeUnit.SECONDS);
            event("RETURN",request,reply,null,null);return reply;
        }catch(ExecutionException error) {
            event("CALL_FAILED",request,null,null,((MembershipTransport.Failure)error.getCause()).reason.name());throw error;
        }
    }
    @Test void cachedOriginalChunksRefuseSendThenReleaseAndRetry()throws Exception {
        raw=Files.createDirectories(Path.of(System.getProperty("v53.source.queue.output","target/v53-source-queue"),"run-"+UUID.randomUUID()));
        Files.createDirectory(raw.resolve("frames"));System.out.println("v53SourceQueueEvidence="+raw.toAbsolutePath());
        var config=builder().configuration();var docs=new ArrayList<Doc>();
        for(int i=0;i<129;i++)docs.add(new Doc(i,"q".repeat(32768)));
        Path backup=temp.resolve("backup");MembershipApplicationImage.capture(config,storage(temp.resolve("backup-core"),2),
                new io.github.patricklfdm.generalsearch.durability.DurableApplicationState<>(V53BootstrapSeedTest.IMPORTED,41,docs,config.indexes()),backup);
        var helper=new V53MembershipTransportTest();helper.temp=temp;
        resources=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
        boolean passed=false;
        try(var group=helper.new Group(3,raw,backup)) {
            var target=group.fixture.request.targets().getFirst();
            try(var owner=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),group.fixture.result.root(),
                    target.identity(),resources,MembershipGrantJournal.MAXIMUM,event->{})) {
                var source=owner.beginActivation();var ballot=object(source.basis.value().get("ballot"));
                var captured=Files.createDirectory(raw.resolve("captured"));
                for(var member:group.fixture.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
                var exported=Files.createDirectory(raw.resolve("exported"));var contents=new ArrayList<Map<String,Object>>();
                String image;long imageBytes;
                try(var export=owner.exportSource(source.basis,BUDGET)) {
                    for(var content:export.contents()) {
                        var bytes=new java.io.ByteArrayOutputStream();
                        for(long at=0;at<content.bytes();) {
                            byte[] part=export.read(content.digest(),at,CHUNK);assertTrue(part.length>0);bytes.write(part);at+=part.length;
                        }
                        assertEquals(content.digest(),hash(bytes.toByteArray()));
                        Files.write(exported.resolve(content.digest()+".bin"),bytes.toByteArray());
                        contents.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));
                    }
                    var content=export.contents().stream().filter(v->v.kind()==MembershipTransfer.Kind.APPLICATION).findFirst().orElseThrow();
                    image=content.digest();imageBytes=content.bytes();assertTrue(imageBytes>CHUNK && imageBytes<2L*CHUNK);
                }
                contents.sort(Comparator.comparing(v->(String)v.get("digest")));Files.write(raw.resolve("contents.json"),canonical(contents,65536));
                var b=V53SourceExchangeTest.bounds();var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),ReplicationBounds.defaults().maxInFlightPerPeer(),
                        b.maxPendingClientOperations(),b.maxRetryAttempts(),30000,b.retryBackoffMillis(),CHUNK,b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
                long start=System.nanoTime(),deadline=start+BUDGET;
                var held=new CountDownLatch(5);var release=new CountDownLatch(1);var pause=new java.util.concurrent.atomic.AtomicBoolean();
                var service=new MembershipTransferService(owner,ballot,resources,bounds,()->owner.checkActivation(source.basis,null,false),System::nanoTime,start,BUDGET,
                        (name,q,a)->event(name,q,a,null,null));
                try(service) {
                    var server=group.start(0,service,new MembershipTransport.Events() {
                        public void at(String name,Decoded q,Decoded a)throws IOException{throw new IOException("connection required");}
                        public void at(String name,Decoded q,Decoded a,MembershipTransport.Connection c)throws IOException {
                            event(name,q,a,c,null);
                            if(pause.get() && name.equals("BEFORE_RESPONSE_WRITE") && number(q.value().get("sequence"))==5) {
                                held.countDown();
                                try {if(!release.await(30,TimeUnit.SECONDS))throw new IOException("queue pressure barrier timeout");}
                                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
                            }
                        }
                        public void failed(boolean outbound,Decoded q,MembershipTransport.Reason reason,MembershipTransport.Connection c) {
                            try{event("SERVER_FAILED",q,null,c,reason.name());}catch(IOException error){throw new java.io.UncheckedIOException(error);}
                        }
                    },bounds,resources);
                    var clients=new HashMap<Integer,MembershipTransport>();for(int n=1;n<=2;n++)clients.put(n,group.start(n,group::status,MembershipTransport.Events.NONE,bounds,V53MembershipTransportTest.resources(MembershipResources.QUEUE_LIMIT)));
                    var sessions=new ArrayList<Session>();var dataRequests=new ArrayList<Decoded>();
                    for(int i=0;i<6;i++) {
                        var s=new Session(1+i%2,UUID.randomUUID(),UUID.randomUUID(),UUID.randomUUID());sessions.add(s);
                        var client=clients.get(s.reader());var peer=group.identities.getFirst();
                        call(client,peer,request(group,ballot,s,1,s.basisTransfer(),source.basis.digest(),0,false),"SOURCE_OFFER",deadline);
                        call(client,peer,request(group,ballot,s,2,s.basisTransfer(),source.basis.digest(),0,false),"CHUNK",deadline);
                        call(client,peer,request(group,ballot,s,3,s.basisTransfer(),source.basis.digest(),0,true),"TRANSFER_COMMIT",deadline);
                        call(client,peer,request(group,ballot,s,4,s.imageTransfer(),image,0,false),"SOURCE_OFFER",deadline);
                        var data=request(group,ballot,s,5,s.imageTransfer(),image,0,false);dataRequests.add(data);
                        call(client,peer,data,"CHUNK",deadline);V53TransferFaultsTest.drain(server,client);
                    }
                    var pending=new ArrayList<CompletableFuture<Decoded>>();pause.set(true);
                    try {
                        for(int i=0;i<5;i++) {
                            int index=i;
                            pending.add(CompletableFuture.supplyAsync(()->{try{return call(clients.get(sessions.get(index).reader()),group.identities.getFirst(),dataRequests.get(index),"CHUNK",deadline);}
                                catch(Exception error){throw new CompletionException(error);}}));
                        }
                        assertTrue(held.await(20,TimeUnit.SECONDS));var refused=dataRequests.getLast();var last=sessions.getLast();
                        assertThrows(ExecutionException.class,()->call(clients.get(last.reader()),group.identities.getFirst(),refused,"CHUNK",deadline));
                        event("PRESSURE",refused,null,null,null);
                        assertEquals(1,events.stream().filter(v->v.get("event").equals("SERVER_FAILED") && "CAPACITY".equals(v.get("reason"))).count());
                        assertEquals(6,service.usage().live());
                    }finally{pause.set(false);release.countDown();}
                    for(var future:pending)future.get(30,TimeUnit.SECONDS);
                    for(var client:clients.values())V53TransferFaultsTest.drain(server,client);
                    // Same failed request, unchanged cached bytes, after real send buffers have drained.
                    var last=sessions.getLast();call(clients.get(last.reader()),group.identities.getFirst(),dataRequests.getLast(),"CHUNK",deadline);
                    for(var s:sessions) {
                        call(clients.get(s.reader()),group.identities.getFirst(),request(group,ballot,s,6,s.imageTransfer(),image,CHUNK,false),"CHUNK",deadline);
                        call(clients.get(s.reader()),group.identities.getFirst(),request(group,ballot,s,7,s.imageTransfer(),image,0,true),"TRANSFER_COMMIT",deadline);
                    }
                    for(var client:clients.values())V53TransferFaultsTest.drain(server,client);
                    event("DRAINED",null,null,null,null);
                }
                for(var transport:group.transports)transport.close();event("SERVICE_CLOSED",null,null,null,null);
            }
            group.fixture.snapshot("after");passed=true;
        }catch(Throwable error){passed=false;throw error;
        }finally {
            V53ResourceTraceFiles.write(raw.resolve("resources.json"),resources.observations());
            Files.write(raw.resolve("events.json"),canonical(events,1024*1024));
            Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-source-queue-v1","status",passed?"PASS":"FAIL",
                    "sessions",6,"queueLimit",MembershipResources.QUEUE_LIMIT,"chunkBytes",CHUNK,"phase3Complete",false,"combinedResources",false),65536));
        }
        assertEquals(0,resources.usage().leases());
    }
}
