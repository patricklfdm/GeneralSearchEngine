package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual native source and original generation, before any learner admission. */
class V53LearnerSourceNetworkTest {
    @TempDir Path temp;
    @Test void fullOriginalReservationAndGenerationArriveWithoutALocalVoter()throws Exception {
        exercise((source,request,raw)->{});
    }
    @FunctionalInterface interface Observer {void acquired(MembershipLearnerSource source,MembershipLearnerRequest request,Path raw)throws Exception;}
    void exercise(Observer observer)throws Exception {
        exercise(observer,false);
    }
    void exercise(Observer observer,boolean retainedScratch)throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        var nativeHelper=new V53NativeDispatchTest();nativeHelper.temp=temp;
        try(var n=nativeHelper.new Network(3,helper.controlBounds(),V53NativeDispatchTest.BUDGET,f->{},true)) {
            try(var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
                round.start();var original=n.owners.getFirst().activationContext();int port;
                try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
                var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
                var target=new ArrayList<MembershipIdentity>();for(var t:n.f.request.targets())target.add(t.identity());target.add(joining);
                var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),original.authority(),MembershipChangeKind.ADD,target);
                var learner=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("absent-learner"),temp.resolve("absent-plan"));
                byte[] command=canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192);
                Files.write(n.f.raw.resolve("learner-reserve-payload.bin"),command);round.submit("RESERVE",command);
                n.f.snapshot("before-learner-source");
                var resources=new MembershipResources(512*MembershipResources.MIB);var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                Path scratch=temp.resolve("learner-source"),copied=Files.createDirectory(n.f.raw.resolve("learner-source-copy"));
                var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
                try(var source=new MembershipLearnerSource(learner,target.getFirst(),resources,n.bounds,(event,request,response)->{
                        if(event.equals("AFTER_RESPONSE_READ"))wire.add(V53SelectedPullTest.wire(request,response));
                    },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                    try(var unused=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"))) {
                        var copy=source.fetch(scratch);assertSame(copy,source.source());
                        var actual=n.owners.getFirst().floorCopyCurrent();assertEquals(actual.fileNames(),copy.fileNames());
                        for(String name:actual.fileNames()) {
                            assertArrayEquals(actual.fileBytes(name),copy.fileBytes(name),name);Files.write(copied.resolve(name),copy.fileBytes(name));
                        }
                        assertEquals(n.owners.getFirst().activationContext().catalog,copy.capsule.context.catalog);
                        assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.LEARNER));
                        assertFalse(copy.capsule.context.voters().contains(joining.nodeId().value()));
                        assertFalse(Files.exists(learner.replicaDirectory()));assertFalse(Files.exists(learner.operationDirectory()));
                        observer.acquired(source,learner,n.f.raw);
                    }
                    assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                }
                if(retainedScratch) {
                    assertTrue(Files.isDirectory(scratch));
                    assertEquals(V53ReplayFilesTest.files(copied),V53ReplayFilesTest.files(scratch));
                    assertTrue(Files.isRegularFile(learner.operationDirectory().resolve(MembershipLearnerAdmissionFiles.RETAIN_NEXT)));
                }else assertFalse(Files.exists(scratch));
                assertEquals(0,resources.usage().leases());
                n.f.snapshot("after-learner-source");round.submit("CANCEL",canonical(Map.of("number",1L),8192));
                try(var cancelled=new MembershipLearnerSource(learner,target.getFirst(),resources,n.bounds,MembershipTransport.Events.NONE,()->{},
                        System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                    assertThrows(java.io.IOException.class,()->cancelled.fetch(temp.resolve("cancelled")));
                }
                assertEquals(0,resources.usage().leases());
                Files.write(n.f.raw.resolve("learner-source-wire.json"),canonical(wire,8*1024*1024));
                Files.write(n.f.raw.resolve("learner-source-result.json"),canonical(Map.of("status","PASS","scope","native-reservation-complete-source",
                        "voter",false,"materialized",false,"publicReady",false,"phase3Complete",false),4096));
            }
        }
    }
}
