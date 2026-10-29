package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** One whole native PREPARE 1/2/3 history. Kept independent for eventual hosted
 * parallel qualification; compile alone is not executed/native evidence. */
class V53CurrentHeadNetworkTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(900);
    @Test void retiredTypedSecondRevisionAcquiresThirdRevisionAcrossParentReopen()throws Exception {run(false);}
    void run(boolean installInactive)throws Exception {
        var driver=new V53RoundDriverTest();driver.temp=temp;var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network(3,driver.controlBounds(),BUDGET,f->{},true);
                var round=driver.driver(n,MembershipRoundDriver.Events.NONE,BUDGET)) {
            Path raw=n.f.raw;System.out.println((installInactive?"v53LearnerSlotEvidence=":"v53CurrentHeadEvidence=")+raw.toAbsolutePath());round.start();int port;
            try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
            var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),n.owners.getFirst().activationContext().authority(),MembershipChangeKind.ADD,targets);
            var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("learner-replica"),temp.resolve("learner-operation"));
            var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("learner-core"),2),n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
            var resources=new MembershipResources(512*MIB);var events=new ArrayList<String>();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            MembershipTransport.Events capture=(event,q,a)->{if(event.equals("AFTER_RESPONSE_READ"))wire.add(V53SelectedPullTest.wire(q,a));};
            byte[] reserve=canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192);Files.write(raw.resolve("learner-reserve-payload.bin"),reserve);
            round.submit("RESERVE",reserve);round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));n.f.snapshot("before-current-head");
            MembershipLearnerPlan summary;
            try(var noListener=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"));
                    var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,capture,()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                var original=source.fetch(temp.resolve("first-receiving"));copy(original,raw.resolve("revision-one"));summary=source.plan(events::add);
                try(var store=source.admit(summary,events::add);
                        var first=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,events::add)) {
                    source.close();var prepared=first.retainGeneration();round.submit("PREPARE",canonical(Map.of("number",1L,"revision",2L),8192));
                    try(var refresh=MembershipLearnerSource.refresh(prepared,targets.getFirst(),n.bounds,capture,System::nanoTime,System.nanoTime(),BUDGET)) {
                        copy(refresh.fetch(temp.resolve("second-receiving")),raw.resolve("revision-two"));
                        var installed=refresh.installSuccessor(events::add);
                        try(var second=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(installed,2),builder().configuration(),config,events::add)) {
                            Files.write(raw.resolve("current-receipt.gsr"),second.receipt().bytes());
                            var head=second.promoteSuccessor();head.retirePredecessor();
                            assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(2,resources.usage().counts().get(Unit.APPLICATION));
                            assertFalse(Files.exists(request.replicaDirectory().resolve("learner")));assertFalse(Files.exists(MembershipLearnerMaterialization.directory(summary)));
                            V53SuccessorTypedNetworkTest.snapshotSuccessor(raw.resolve("retired-successor"),summary);
                            V53JournalApplicationTest.copy(MembershipLearnerSuccessor.typedDirectory(summary),raw.resolve("retired-typed"));
                        }
                    }
                }
            }
            assertEquals(0,resources.usage().leases());n.f.snapshot("after-current-retirement");
            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",3L),8192));
            try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                    var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.promotedSuccessor(),2),builder().configuration(),config,events::add)) {
                var head=typed.currentHead();var baseline=resources.usage();var original=head.source().packet.bytes();
                try(var refresh=MembershipLearnerSource.refresh(head,targets.getFirst(),n.bounds,capture,System::nanoTime,System.nanoTime(),BUDGET)) {
                    var received=refresh.fetch(temp.resolve("third-receiving"));assertEquals(5L,number(received.capsule.context.cut.get("index")));
                    assertEquals(3L,number(object(list(received.capsule.context.catalog.get("results")).getFirst()).get("revision")));
                    assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(1,resources.usage().counts().get(Unit.LEARNER));
                    assertFalse(received.capsule.context.voters().contains(joining.nodeId().value()));copy(received,raw.resolve("revision-three"));
                    assertArrayEquals(Files.readAllBytes(raw.resolve("current-receipt.gsr")),typed.receipt().bytes());
                    if(installInactive) {
                        var slot=refresh.installSlot(events::add);
                        try(var third=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(slot,3),builder().configuration(),config,events::add)) {
                            Files.write(raw.resolve("third-receipt.gsr"),third.receipt().bytes());
                            assertEquals("learner inactive slot is not the current head",assertThrows(IllegalArgumentException.class,third::currentHead).getMessage());
                        }
                        assertEquals(2,resources.usage().counts().get(Unit.GENERATION));assertFalse(resources.usage().counts().containsKey(Unit.LEARNER));
                        V53JournalApplicationTest.copy(MembershipLearnerSlot.directory(summary),raw.resolve("installed-slot"));
                        V53JournalApplicationTest.copy(MembershipLearnerSlot.typedDirectory(summary),raw.resolve("installed-slot-typed"));
                    }
                }
                if(!installInactive)assertEquals(baseline,resources.usage());
                else assertEquals(2,resources.usage().counts().get(Unit.GENERATION));
                assertArrayEquals(original,head.source().packet.bytes());
                assertFalse(Files.exists(config.materialization().directory()));
            }
            assertEquals(0,resources.usage().leases());
            if(installInactive) {
                try(var store=MembershipLearnerStore.resume(summary,resources,events::add);
                        var second=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store.promotedSuccessor(),2),builder().configuration(),config,events::add)) {
                    var slot=store.resumeSlot(second.currentHead());
                    try(var third=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(slot,3),builder().configuration(),config,events::add)) {
                        assertArrayEquals(Files.readAllBytes(raw.resolve("third-receipt.gsr")),third.receipt().bytes());
                        assertArrayEquals(Files.readAllBytes(raw.resolve("current-receipt.gsr")),second.receipt().bytes());
                    }
                    V53JournalApplicationTest.copy(MembershipLearnerSlot.directory(summary),raw.resolve("reopened-slot"));
                    V53JournalApplicationTest.copy(MembershipLearnerSlot.typedDirectory(summary),raw.resolve("reopened-slot-typed"));
                }
                assertEquals(0,resources.usage().leases());
            }
            n.f.snapshot("after-third-acquisition");round.submit("CANCEL",canonical(Map.of("number",1L),8192));
            Files.write(raw.resolve("current-head-events.json"),canonical(events,65536));Files.write(raw.resolve("current-head-wire.json"),canonical(wire,8*1024*1024));
            Files.write(raw.resolve("current-head-result.json"),canonical(Map.of("status","PASS","scope",installInactive?"native-inactive-slot":"native-current-head-acquisition",
                    "installedThirdRevision",installInactive,"voter",false,"publicReady",false,"phase3Complete",false,"testBudgetSeconds",900L),4096));
        }
    }
    private static void copy(MembershipFloor.Copy copy,Path destination)throws Exception {
        copy.check();Files.createDirectory(destination);for(String name:copy.fileNames())Files.write(destination.resolve(name),copy.fileBytes(name));copy.check();
    }
}
