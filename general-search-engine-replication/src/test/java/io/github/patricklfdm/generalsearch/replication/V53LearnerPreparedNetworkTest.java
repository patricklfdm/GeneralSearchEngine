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

/** Real PREPARE revisions over TCP. The selected immutable learner remains
 * nonvoting while a successor is received using the same resource budget. */
class V53LearnerPreparedNetworkTest {
    @TempDir Path temp;
    // Five certified slots plus native acquisition, admission and semantic reopen
    // share one declared deadline. The older two-slot helper's 180 seconds is
    // insufficient for this longer history; individual RPC bounds are unchanged.
    static final long BUDGET=TimeUnit.SECONDS.toNanos(600);
    @Test void nativePreparedGenerationReceivesAnAuthenticatedSuccessor()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        var network=new V53NativeDispatchTest();network.temp=temp;
        try(var n=network.new Network(3,helper.controlBounds(),BUDGET,f->{},true)) {
            System.out.println("v53LearnerPreparedEvidence="+n.f.raw.toAbsolutePath());
            try(var round=helper.driver(n,MembershipRoundDriver.Events.NONE,BUDGET)) {
                round.start();int port;
                try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
                var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
                var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
                var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),n.owners.getFirst().activationContext().authority(),MembershipChangeKind.ADD,targets);
                var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("learner-replica"),temp.resolve("learner-operation"));
                byte[] reserve=canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192);
                Files.write(n.f.raw.resolve("learner-reserve-payload.bin"),reserve);round.submit("RESERVE",reserve);
                round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));n.f.snapshot("before-learner-source");
                var resources=new MembershipResources(512*MembershipResources.MIB);
                var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var events=new ArrayList<String>();var refreshWire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("learner-core"),2),
                        n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
                Path raw=n.f.raw,sourceCopy=Files.createDirectory(raw.resolve("learner-source-copy"));MembershipLearnerPlan summary;Decoded receipt;
                try(var unused=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"));
                        var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,(event,q,a)->{
                            if(event.equals("AFTER_RESPONSE_READ"))wire.add(V53SelectedPullTest.wire(q,a));
                        },()->{},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                    var copy=source.fetch(temp.resolve("receiving"));for(String name:copy.fileNames())Files.write(sourceCopy.resolve(name),copy.fileBytes(name));
                    summary=source.plan(events::add);
                    try(var store=source.admit(summary,events::add)) {
                        source.close();var input=MembershipLearnerPreparation.from(store,1);
                        try(var typed=MembershipLearnerMaterialization.prepare(input,builder().configuration(),config,events::add)) {
                            receipt=typed.receipt();assertEquals(request.root().historyId(),typed.state().history());
                            assertTrue(typed.state().documents().isEmpty());assertFalse(Files.exists(config.materialization().directory()));
                            assertFalse(store.capsule().context.voters().contains(joining.nodeId().value()));
                            Files.write(raw.resolve("learner-receipt.gsr"),receipt.bytes());
                            var prepared=typed.retainGeneration();
                            assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.GENERATION));
                            assertFalse(resources.usage().counts().containsKey(MembershipResources.Unit.LEARNER));
                            n.f.snapshot("after-learner-source");
                            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",2L),8192));
                            n.f.snapshot("before-learner-refresh");
                            try(var refresh=MembershipLearnerSource.refresh(prepared,targets.getFirst(),n.bounds,(event,q,a)->{
                                    if(event.equals("AFTER_RESPONSE_READ"))refreshWire.add(V53SelectedPullTest.wire(q,a));
                                },System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                                var next=refresh.fetch(temp.resolve("refresh-receiving"));
                                assertEquals(4L,number(next.capsule.context.cut.get("index")));
                                assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.LEARNER));
                                assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.GENERATION));
                                assertArrayEquals(receipt.bytes(),prepared.receipt().bytes());
                                Path refreshed=Files.createDirectory(raw.resolve("learner-refresh-copy"));
                                for(String name:next.fileNames())Files.write(refreshed.resolve(name),next.fileBytes(name));
                                assertThrows(IllegalArgumentException.class,()->refresh.plan(events::add));
                                assertThrows(IllegalArgumentException.class,()->refresh.admit(summary,events::add));
                            }
                            assertFalse(resources.usage().counts().containsKey(MembershipResources.Unit.LEARNER));
                            assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.GENERATION));
                            n.f.snapshot("after-learner-refresh");
                            V53JournalApplicationTest.copy(MembershipLearnerMaterialization.directory(summary),raw.resolve("typed"));
                        }
                    }
                }
                var plan=MembershipLearnerAdmissionPlan.decode(Files.readAllBytes(request.operationDirectory().resolve(MembershipLearnerAdmissionFiles.FILE)));
                Files.write(raw.resolve("learner-plan.gslp"),plan.bytes());V53LearnerStoreNetworkTest.snapshot(raw.resolve("admitted"),plan);
                assertEquals(0,resources.usage().leases());round.submit("CANCEL",canonical(Map.of("number",1L),8192));
                Files.write(raw.resolve("learner-source-wire.json"),canonical(wire,8*1024*1024));
                Files.write(raw.resolve("learner-typed-events.json"),canonical(events,65536));
                Files.write(raw.resolve("learner-refresh-wire.json"),canonical(refreshWire,8*1024*1024));
                Files.write(raw.resolve("learner-prepared-result.json"),canonical(Map.of("status","PASS","scope","native-prepared-learner-refresh",
                        "voter",false,"liveCore",false,"publicReady",false,"phase3Complete",false,"testBudgetSeconds",600L),4096));
            }
        }
    }
}
