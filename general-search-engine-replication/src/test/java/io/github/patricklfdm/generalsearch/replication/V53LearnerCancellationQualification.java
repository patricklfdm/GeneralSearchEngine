package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** One actual BARRIER/RESERVE/PREPARE/READY/CANCEL history, with the same learner
 * and original proof across close/reopen. No conditional voter/ancestry fixture.
 * Explicit deferred qualification entry with actual quorum-retained learner
 * endpoints. It must pass independent replay before Phase 3 closure. */
class V53LearnerCancellationQualification {
    @TempDir Path temp;
    Path retainedRaw;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(600);
    @Test void nativeReadyCancellationRetainsItsPreparedAncestorAndColdReopensWithoutVoting()throws Exception {run(null);}
    void run(V53LearnerResourceCapture capture)throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;var network=new V53NativeDispatchTest();network.temp=temp;
        try(var n=network.new Network(3,helper.controlBounds(),BUDGET,f->{
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-learner-retention")){owner.initializeLearnerRetention();}
        },true)) {
            Path raw=n.f.raw;retainedRaw=raw;System.out.println("v53LearnerCancellationEvidence="+raw.toAbsolutePath());
            var sourceWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var progressWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var initialEvents=new ArrayList<String>();var cancelEvents=new ArrayList<String>();var resumeEvents=new ArrayList<String>();
            boolean success=false;
            try(var round=helper.driver(n,MembershipRoundDriver.Events.NONE,BUDGET)) {
                round.start();int port;
                try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
                var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
                var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
                var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),n.owners.getFirst().activationContext().authority(),MembershipChangeKind.ADD,targets);
                var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("learner-replica"),temp.resolve("learner-operation"));
                byte[] reserve=canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192);
                Files.write(raw.resolve("learner-reserve-payload.bin"),reserve);round.submit("RESERVE",reserve);
                round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));n.f.snapshot("before-learner-source");
                var resources=capture==null?new MembershipResources(512*MembershipResources.MIB):capture.resources;
                var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("learner-core"),2),
                        n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
                MembershipLearnerPlan summary;Decoded receipt;
                // A listener cannot silently turn this nonvoting learner into a voter.
                try(var unused=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"))) {
                    try(var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,(event,q,a)->{
                            if(event.equals("AFTER_RESPONSE_READ"))sourceWire.add(V53SelectedPullTest.wire(q,a));
                        },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                        copy(source.fetch(temp.resolve("receiving")),raw.resolve("learner-source-copy"));summary=source.plan(V53LearnerResourceCapture.events(capture,initialEvents,"initial"));
                        Files.write(raw.resolve("learner-plan.gslp"),Files.readAllBytes(request.operationDirectory().resolve(MembershipLearnerAdmissionFiles.FILE)));
                        try(var ownedStore=V53LearnerResourceCapture.own(capture,"initial-store",source.admit(summary,V53LearnerResourceCapture.events(capture,initialEvents,"initial")))) {
                            var store=ownedStore.value;
                            source.close();
                            try(var ownedTyped=V53LearnerResourceCapture.own(capture,"initial-typed",MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,V53LearnerResourceCapture.events(capture,initialEvents,"initial")))) {
                                var typed=ownedTyped.value;
                                receipt=typed.receipt();var head=typed.retainGeneration();
                                assertTrue(typed.state().documents().isEmpty());assertFalse(Files.exists(config.materialization().directory()));
                                Files.write(raw.resolve("learner-receipt.gsr"),receipt.bytes());snapshot(raw.resolve("learner-prepared"),summary,resources);V53LearnerResourceCapture.stage(capture,"learner-prepared");
                                n.f.snapshot("after-learner-source");byte[] ready=canonical(Map.of("number",1L,"receipt",receipt.value().get("receipt")),8192);
                                Files.write(raw.resolve("learner-ready-payload.bin"),ready);round.submit("READY",ready);
                                round.submit("CANCEL",canonical(Map.of("number",1L),8192));n.f.snapshot("after-cancel");
                                copy(n.owners.getFirst().floorCopyCurrent(),raw.resolve("cancelled-original"));
                                System.out.println("v53LearnerCancellationStage=certified-cancel");
                                try(var progress=new MembershipLearnerProgress(head,targets.getFirst(),n.bounds,(event,q,a)->{
                                        if(event.equals("AFTER_RESPONSE_READ"))progressWire.add(V53SelectedPullTest.wire(q,a));
                                    },System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                                    copy(progress.fetch(temp.resolve("cancel-receiving")),raw.resolve("learner-progress-copy"));
                                    try(var ownedCancel=V53LearnerResourceCapture.own(capture,"initial-cancel",progress.retainCancellation(V53LearnerResourceCapture.events(capture,cancelEvents,"cancel")))) {
                                        var cancelled=ownedCancel.value;
                                        progress.close();assertEquals("CANCELLED",cancelled.result().get("phase"));
                                        assertArrayEquals(receipt.bytes(),typed.receipt().bytes());
                                        assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.GENERATION));
                                        assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.LEARNER));
                                        assertThrows(IllegalArgumentException.class,store::requireActive);
                                        snapshot(raw.resolve("learner-cancelled"),summary,resources);V53LearnerResourceCapture.stage(capture,"learner-cancelled");
                                    }
                                }
                            }
                        }
                    }
                    assertEquals(0,resources.usage().leases());snapshot(raw.resolve("learner-closed"),summary,resources);V53LearnerResourceCapture.stage(capture,"learner-closed");
                    System.out.println("v53LearnerCancellationStage=retained-and-closed");
                    try(var ownedStore=V53LearnerResourceCapture.own(capture,"resume-store",MembershipLearnerStore.resume(summary,resources,V53LearnerResourceCapture.events(capture,resumeEvents,"resume")));
                            var ownedTyped=V53LearnerResourceCapture.own(capture,"resume-typed",MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(ownedStore.value,1),builder().configuration(),config,V53LearnerResourceCapture.events(capture,resumeEvents,"resume")))) {
                        var store=ownedStore.value;var typed=ownedTyped.value;
                        var head=typed.retainGeneration();
                        try(var ownedCancel=V53LearnerResourceCapture.own(capture,"resume-cancel",MembershipLearnerCancellation.resume(head,V53LearnerResourceCapture.events(capture,resumeEvents,"resume")))) {
                            var cancelled=ownedCancel.value;
                            assertEquals("CANCELLED",cancelled.result().get("phase"));assertArrayEquals(receipt.bytes(),typed.receipt().bytes());
                            assertTrue(typed.state().documents().isEmpty());assertThrows(IllegalArgumentException.class,store::requireActive);
                            assertThrows(IllegalArgumentException.class,()->MembershipLearnerSource.refresh(head,targets.getFirst(),n.bounds,
                                    MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180)));
                            snapshot(raw.resolve("learner-reopened"),summary,resources);V53LearnerResourceCapture.stage(capture,"learner-reopened");
                        }
                    }
                    assertEquals(0,resources.usage().leases());assertFalse(Files.exists(config.materialization().directory()));
                    V53LearnerResourceCapture.stage(capture,"final-closed");
                }
                success=true;System.out.println("v53LearnerCancellationStage=reopened");
            }finally {
                Files.write(raw.resolve("learner-source-wire.json"),canonical(sourceWire,8*1024*1024));
                Files.write(raw.resolve("learner-progress-wire.json"),canonical(progressWire,8*1024*1024));
                Files.write(raw.resolve("learner-initial-events.json"),canonical(initialEvents,65536));
                Files.write(raw.resolve("learner-cancel-events.json"),canonical(cancelEvents,65536));
                Files.write(raw.resolve("learner-resume-events.json"),canonical(resumeEvents,65536));
                Files.write(raw.resolve("learner-cancellation-result.json"),canonical(Map.of("status",success?"PASS":"FAIL","scope","native-learner-cancellation",
                        "voter",false,"liveCore",false,"publicReady",false,"phase3Complete",false,"independentReplayQualified",false,"testBudgetSeconds",600L),4096));
            }
        }
    }
    static void copy(MembershipFloor.Copy original,Path path)throws Exception {
        original.check();Files.createDirectory(path);for(String name:original.fileNames())Files.write(path.resolve(name),original.fileBytes(name));original.check();
    }
    static void snapshot(Path target,MembershipLearnerPlan plan,MembershipResources resources)throws Exception {
        Files.createDirectory(target);var roots=new TreeMap<>(Map.of("operation",plan.request().operationDirectory(),"replica",plan.request().replicaDirectory(),
                "initial-typed",MembershipLearnerMaterialization.directory(plan),"cancellation",MembershipLearnerCancellation.directory(plan)));
        var identities=new TreeMap<String,Object>();int count=0;
        for(var entry:roots.entrySet()) {
            Path root=AdmissionPaths.safe(entry.getValue());boolean present=Files.exists(root,LinkOption.NOFOLLOW_LINKS);var members=new TreeMap<String,Object>();
            if(present) {
                try(var walk=Files.walk(root)) {
                    for(Path path:walk.sorted().toList()) {
                        assertTrue(++count<=256);AdmissionPaths.safe(path);String name=path.equals(root)?".":root.relativize(path).toString();
                        if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))members.put(name,Map.of("key",MembershipBasisSources.key(path).toString(),"directory",true));
                        else {byte[] bytes=AdmissionPaths.read(path,MembershipApplicationImage.MAXIMUM);var file=MembershipBasisSources.inspect(path,bytes.length,hash(bytes));
                            members.put(name,Map.of("key",file.key().toString(),"bytes",file.bytes(),"sha256",file.digest()));}
                    }
                }
                V53JournalApplicationTest.copy(root,target.resolve(entry.getKey()));
            }
            identities.put(entry.getKey(),Map.of("path",root.toString(),"present",present,"members",members));
        }
        Files.write(target.resolve("original-identities.json"),V53CurrentHeadNetworkTest.evidenceJson(identities,1024*1024));
        var use=resources.usage();var counts=new TreeMap<String,Object>();use.counts().forEach((unit,counted)->counts.put(unit.name(),counted.longValue()));
        Files.write(target.resolve("resources.json"),canonical(Map.of("counts",counts,"leases",(long)use.leases(),"metadata",use.metadata(),"staging",use.staging(),"queued",use.queued()),4096));
    }
}
