package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Explicit whole-history probe: real joint SOURCE pressure, then native FINAL. */
class V53QueueCompletionQualification {
    @TempDir Path temp;
    static final int CHUNK=4*1024*1024;
    int chunk=CHUNK;
    boolean pressureRequired=true;
    final List<Map<String,Object>> points=new ArrayList<>();
    final List<Map<String,Object>> attempts=new ArrayList<>();
    V53NativeDispatchTest.Network network;
    final Set<String> pressureTraces=new HashSet<>();
    V53MaximumApplicationTest.Seed maximumSeed;
    record Session(int reader,UUID trace,UUID basis,UUID image) {}
    synchronized void point(String name) {
        var p=network.resources.getFirst().observationCheckpoint();assertTrue(p.complete());
        points.add(Map.of("event",name,"sequence",p.sequence(),"queued",p.usage().queued(),"eventIndex",network.events.size()));
        System.out.println("v53QueueCompletionStage="+name+" queuedBytes="+p.usage().queued());
    }
    Decoded request(Session session,long sequence,String digest,long offset,boolean commit,boolean image)throws Exception {
        var own=network.owners.getFirst();
        var payload=commit?Map.<String,Object>of("id",(image?session.image():session.basis()).toString(),"digest",digest):
                Map.<String,Object>of("id",(image?session.image():session.basis()).toString(),"action","REQUEST","offset",offset,"digest",digest,"bytes","");
        return MembershipActivation.frame(commit?"TRANSFER_COMMIT":"CHUNK",own.activationContext(),
                network.owners.get(session.reader()).activationIdentity(),own.activationIdentity(),network.ballot,session.trace(),sequence,payload);
    }
    Decoded call(Session session,Decoded request,String kind,long deadline)throws Exception {
        try {
            var result=network.transports.get(session.reader()).exchange(network.owners.getFirst().activationIdentity(),request,kind,deadline).get(30,TimeUnit.SECONDS);
            synchronized(attempts){attempts.add(Map.of("request",request.digest(),"response",result.digest(),"status","PASS"));}return result;
        }catch(ExecutionException failure) {
            var reason=((MembershipTransport.Failure)failure.getCause()).reason.name();
            synchronized(attempts){attempts.add(Map.of("request",request.digest(),"status","FAIL","reason",reason));}throw failure;
        }
    }
    void pressure()throws Exception {
        var own=network.owners.getFirst();var basis=own.originalBasis().orElseThrow();
        // BASIS carries cut/identity/digests, not the entire metadata capsule.
        // This component intentionally transfers that record in one chunk.
        assertTrue(basis.size()<=chunk,"queue completion basis extent");
        var images=own.originalSource().capsule.packet.images();assertEquals(1,images.size());
        String image=images.keySet().iterator().next();long imageBytes=images.get(image);
        assertTrue(imageBytes>chunk && imageBytes<=MembershipApplicationImage.MAXIMUM);
        var sessions=new ArrayList<Session>();var requests=new ArrayList<Decoded>();long deadline=System.nanoTime()+V53SourceQueueQualification.BUDGET;
        var entered=new CountDownLatch(7);var release=new CountDownLatch(1);var pause=new java.util.concurrent.atomic.AtomicBoolean();
        network.beforeResponseWrite.set(q->{
            if(pause.get() && pressureTraces.contains((String)q.value().get("trace")) && number(q.value().get("sequence"))==5) {
                entered.countDown();
                try {if(!release.await(30,TimeUnit.SECONDS))throw new IllegalStateException("pressure response barrier timeout");}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException(error);}
            }
        });
        point("JOINT_BEFORE_PRESSURE");
        for(int i=0;i<4;i++) {
            var session=new Session(1+i%2,UUID.randomUUID(),UUID.randomUUID(),UUID.randomUUID());sessions.add(session);pressureTraces.add(session.trace().toString());
            call(session,request(session,1,basis.digest(),0,false,false),"SOURCE_OFFER",deadline);
            call(session,request(session,2,basis.digest(),0,false,false),"CHUNK",deadline);
            call(session,request(session,3,basis.digest(),0,true,false),"TRANSFER_COMMIT",deadline);
            call(session,request(session,4,image,0,false,true),"SOURCE_OFFER",deadline);
            var q=request(session,5,image,0,false,true);requests.add(q);call(session,q,"CHUNK",deadline);
            V53TransferFaultsTest.drain(network.transports.getFirst(),network.transports.get(session.reader()));
        }
        try(var workers=Executors.newVirtualThreadPerTaskExecutor()) {
            var pending=new ArrayList<CompletableFuture<Decoded>>();pause.set(true);
            try {
                for(int i=0;i<7;i++) {int at=i%4;pending.add(CompletableFuture.supplyAsync(()->{
                    try{return call(sessions.get(at),requests.get(at),"CHUNK",deadline);}catch(Exception failure){throw new CompletionException(failure);}},workers));}
                assertTrue(entered.await(20,TimeUnit.SECONDS));point("SEVEN_SENDS_HELD");
                if(pressureRequired) {
                    var failure=assertThrows(ExecutionException.class,()->call(sessions.getLast(),requests.getLast(),"CHUNK",deadline));
                    assertEquals(MembershipTransport.Reason.IO,((MembershipTransport.Failure)failure.getCause()).reason);
                    point("EIGHTH_SEND_REFUSED");
                }else {
                    // Small-image rehearsal is deliberately not queue-capacity evidence.
                    pause.set(false);call(sessions.getLast(),requests.getLast(),"CHUNK",deadline);
                    V53MembershipTransportTest.waitFor(()->network.transports.getFirst().usage().incoming()==7);point("EIGHTH_SEND_DELIVERED");
                }
            }finally{pause.set(false);release.countDown();}
            for(var future:pending)future.get(30,TimeUnit.SECONDS);
            for(int i=1;i<=2;i++)V53TransferFaultsTest.drain(network.transports.getFirst(),network.transports.get(i));
            call(sessions.getLast(),requests.getLast(),"CHUNK",deadline);
            for(var session:sessions) {
                long sequence=6;
                // The pressure/retry request is still the identical first chunk.
                // Consume every remaining original byte under the same deadline
                // before the terminal COMMIT, including an exact-sized last chunk.
                for(long offset=chunk;offset<imageBytes;offset+=chunk)
                    call(session,request(session,sequence++,image,offset,false,true),"CHUNK",deadline);
                call(session,request(session,sequence,image,0,true,true),"TRANSFER_COMMIT",deadline);
            }
            for(int i=1;i<=2;i++)V53TransferFaultsTest.drain(network.transports.getFirst(),network.transports.get(i));
            point("PRESSURE_DRAINED");network.beforeResponseWrite.set(q->{});
        }
    }
    @Test void admittedRemoveFinishesAfterRealJointQueuePressure()throws Exception {run(true);}
    @Test void smallImageRehearsesSameNativeCompletion()throws Exception {run(false);}
    @Test void multiChunkImageRehearsesSameNativeCompletion()throws Exception {run(false,10000);}
    @Test void segmentedImageRehearsesSameNativeCompletion()throws Exception {run(false,10000,V53WireArchive.Layout.SEGMENTED_BACKUP);}
    @Test void segmentedQueuePressureCompletesSameNativeHistory()throws Exception {run(true,32768,V53WireArchive.Layout.SEGMENTED_BACKUP);}
    private void run(boolean full)throws Exception {
        run(full,full?32768:3000);
    }
    private void run(boolean full,int valueBytes)throws Exception {
        run(full,valueBytes,V53WireArchive.Layout.JSON);
    }
    private void run(boolean full,int valueBytes,V53WireArchive.Layout layout)throws Exception {
        pressureRequired=full;chunk=full?CHUNK:4096;
        var raw=Files.createDirectories(Path.of("target/v53-queue-completion/run-"+UUID.randomUUID()));
        System.out.println("v53QueueCompletionEvidence="+raw.toAbsolutePath());
        var docs=new ArrayList<Doc>();for(int i=0;i<(full?129:2);i++)docs.add(new Doc(i,"q".repeat(valueBytes)));
        var config=builder().configuration();Path backup=temp.resolve("backup");
        MembershipApplicationImage.capture(config,storage(temp.resolve("backup-core"),2),new io.github.patricklfdm.generalsearch.durability.DurableApplicationState<>(
                V53BootstrapSeedTest.IMPORTED,41,docs,config.indexes()),backup);
        execute(raw,backup,layout,V53NativeResourceProfile.SMALL_FIXTURE);
    }
    void maximumImage()throws Exception {
        pressureRequired=true;chunk=CHUNK;
        Path raw=Files.createDirectories(Path.of("target/v53-maximum-queue/run-"+UUID.randomUUID()));
        System.out.println("v53MaximumQueueEvidence="+raw.toAbsolutePath());
        Path seedDirectory=Files.createDirectory(raw.resolve(V53MaximumNativeQualification.SEED));
        maximumSeed=V53MaximumApplicationTest.captureMaximum(temp,seedDirectory);
        var original=V53ReplayFilesTest.files(maximumSeed.source());
        execute(raw,maximumSeed.source(),V53WireArchive.Layout.SEGMENTED_BACKUP,V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING);
        assertEquals(original,V53ReplayFilesTest.files(maximumSeed.source()));
    }
    private void execute(Path raw,Path backup,V53WireArchive.Layout layout,V53NativeResourceProfile profile)throws Exception {
        var helper=new V53MembershipTransportTest();helper.temp=temp;
        var continuous=new V53ContinuousTransitionTest();continuous.temp=temp;continuous.budget=TimeUnit.MINUTES.toNanos(15);
        try(var group=helper.new Group(4,raw,backup,profile)) {
            var fixture=group.fixture;fixture.ownedHistory=true;fixture.nativeApplication=true;
            Map<String,Object> maximumBinding=maximumSeed==null?null:
                    V53MaximumNativeQualification.seedBinding(maximumSeed,raw,temp.resolve("seed-inspection"));
            if(maximumBinding!=null)Files.write(raw.resolve(V53MaximumNativeQualification.SEED).resolve("binding.json"),canonical(maximumBinding,16384),StandardOpenOption.CREATE_NEW);
            for(var target:fixture.request.targets())try(var owner=fixture.open(target,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
            var walk=new V53AdmittedCrossViewTest.Walk(fixture);
            var request=Map.of("root",fixture.result.root().manifestDigest(),"expected",walk.current().authority(),"number",1L,"kind","REMOVE",
                    "target",fixture.request.targets().subList(0,3).stream().map(t->MembershipBootstrapSeed.identity(t.identity())).toList());
            walk.publish("RESERVE",Map.of("request",request));walk.publish("PREPARE",Map.of("number",1L,"revision",1L));
            walk.publish("READY",V53ContextFixture.map("number",1L,"receipt",null));walk.publish("SEAL",Map.of("number",1L));
            var b=ReplicationBounds.defaults();var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                    b.maxRetryAttempts(),30000,b.retryBackoffMillis(),chunk,b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
            var networkHelper=new V53NativeDispatchTest();networkHelper.temp=temp;
            network=layout==V53WireArchive.Layout.JSON?networkHelper.new Network(fixture,bounds,continuous.budget,true,true,256*1024*1024):
                    networkHelper.new Network(fixture,bounds,continuous.budget,true,true,layout,profile);
            boolean passed=false;
            network.observeRequests=true;
            try {
                try(var running=network) {
                    continuous.activate(network,1);var own=network.owners.getFirst();
                    var operation=object(list(own.activationContext().catalog.get("results")).getLast());
                    continuous.publish(network,"INTENT",canonical(Map.of("sealed",V53ContextFixture.map("request",operation.get("request"),
                            "prepared",operation.get("prepared"),"receipt",operation.get("receipt"))),8192));
                    continuous.activate(network,2);pressure();point("FINAL_BEGIN");
                    operation=object(list(own.activationContext().catalog.get("results")).getLast());
                    continuous.publish(network,"FINAL",canonical(Map.of("binding",operation.get("binding")),8192));point("FINAL_PUBLISHED");
                    continuous.activate(network,3);continuous.publish(network,"BARRIER",new byte[0]);point("BARRIER_PUBLISHED");
                    network.endpoints.getFirst().checkInstalled();assertEquals(7L,own.activationContext().cut.get("index"));
                    assertEquals("COMPLETED",object(list(own.activationContext().catalog.get("results")).getLast()).get("phase"));
                    Files.write(raw.resolve("continuous-result.json"),canonical(Map.of("status","PASS","kind","REMOVE","activations",3,"publicReady",false,"automaticLifecycle",false),4096));
                }
                passed=true;
            }finally {
                point("CLOSED");V53ResourceTraceFiles.write(raw.resolve("queue-resources.json"),network.resources.getFirst().observations());
                var receipt=new TreeMap<String,Object>(Map.of("schema","gse-v53-queue-completion-v1","status",passed?"PASS":"FAIL",
                        "pressureRequired",pressureRequired,"points",points,"attempts",attempts,"traces",pressureTraces.stream().sorted().toList(),"phase3Complete",false,"combinedMaximumQualified",false));
                if(layout==V53WireArchive.Layout.SEGMENTED_BACKUP) {
                    receipt.put("schema","gse-v53-segmented-queue-completion-v1");receipt.put("wireLayout",layout.name());
                    receipt.put("bootstrapSource",fixture.request.source().name());
                }
                if(maximumBinding!=null) {
                    receipt.put("schema","gse-v53-maximum-queue-completion-v1");
                    receipt.put("maximumSeed",maximumBinding);
                    receipt.put("resourceProfile",profile.name());receipt.put("stagingLimit",profile.stagingBytes);
                }
                Files.write(raw.resolve("queue-completion.json"),canonical(receipt,1024*1024));
            }
        }
    }
}
