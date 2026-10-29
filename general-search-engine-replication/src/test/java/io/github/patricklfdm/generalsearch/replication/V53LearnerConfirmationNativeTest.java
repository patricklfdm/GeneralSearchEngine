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

class V53LearnerConfirmationNativeTest {
    @TempDir Path temp;
    static List<Long> indices(MembershipGrantJournal owner)throws Exception {
        return owner.learnerRetentionState().plan().recorded().stream().map(p->number(p.cut().get("index"))).toList();
    }
    @Test void actualAckForcesDischargeAcrossStaleSelectedSourcePublicationAndColdReopen()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;var network=new V53NativeDispatchTest();network.temp=temp;
        long budget=TimeUnit.SECONDS.toNanos(1200);V53BootstrapPublicationTest.Fixture fixture;
        try(var n=network.new Network(3,helper.controlBounds(),budget,f->{
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-learner-retention")){owner.initializeLearnerRetention();}
        },true);var round=helper.driver(n,MembershipRoundDriver.Events.NONE,budget)) {
            fixture=n.f;System.out.println("v53LearnerConfirmationEvidence="+n.f.raw.toAbsolutePath());
            // Fix reachability before either campaign, never swap a selected
            // pair to accommodate the three-point merge.
            n.transports.get(2).close();round.start();
            int port;try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
            var owner=n.owners.getFirst();var pool=n.resources.getFirst();
            var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),owner.activationContext().authority(),MembershipChangeKind.ADD,targets);
            var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("replica"),temp.resolve("operation"));
            round.submit("RESERVE",canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192));
            try(var recording=new MembershipLearnerRetentionQuorum(owner,joining,n.ballot,pool,n.transports.getFirst()::exchange,
                    System::nanoTime,System.nanoTime(),budget)){recording.run();}
            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));
            var resources=new MembershipResources(512*MembershipResources.MIB);
            var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("core"),2),
                    n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
            try(var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,MembershipTransport.Events.NONE,
                    ()->{},System::nanoTime,System.nanoTime(),budget)) {
                source.fetch(temp.resolve("receiving"));var summary=source.plan(e->{});
                try(var store=source.admit(summary,e->{})) {
                    source.close();
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,e->{})) {
                        var head=typed.retainGeneration();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                        try(var server=new MembershipLearnerHeadEndpoint(head,n.bounds,(event,q,a)->{
                            if(event.equals("BEFORE_RESPONSE_WRITE"))wire.add(V53SelectedPullTest.wire(q,a));
                        });var probe=new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,n.transports.getFirst()::exchange,
                                System::nanoTime,System.nanoTime(),budget)) {
                            var observed=probe.run();n.f.snapshot("before-confirmation");
                            assertEquals(List.of(2L,3L),indices(owner));assertEquals(List.of(2L,3L),indices(n.owners.get(1)));
                            var other=V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory());
                            assertThrows(IllegalArgumentException.class,()->n.owners.get(1).retainLearnerConfirmation(observed));
                            assertEquals(other,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
                            var confirmed=owner.retainLearnerConfirmation(observed);
                            assertEquals(List.of(3L),indices(owner));assertEquals(3,confirmed.revision());
                            assertEquals(List.of(2L,3L),confirmed.plan().required(owner.floorCopyCurrent().capsule,
                                    owner.floorCopyCurrent().fileBytes("ancestry.gsr")).stream().map(p->number(p.cut().get("index"))).toList());
                            assertEquals(confirmed,owner.retainLearnerConfirmation(observed));n.f.snapshot("confirmed-local");
                            round.submit("BARRIER",new byte[0]);owner.retainLearnerOffer(joining);
                            assertEquals(List.of(3L,4L),indices(owner));assertEquals(List.of(2L,3L),indices(n.owners.get(1)));
                            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionPlan.mergeRecorded(request.root().manifestDigest(),
                                    List.of(owner.learnerRetentionState().plan(),n.owners.get(1).learnerRetentionState().plan())));
                            V53JournalApplicationTest.copy(request.operationDirectory(),n.f.raw.resolve("learner-originals"));
                            Files.write(n.f.raw.resolve("head-wire.json"),canonical(wire,1024*1024));n.f.snapshot("before-confirmed-selection");
                            probe.close();round.close();
                            try(var next=new MembershipRoundDriver<>(owner,n.endpoints.getFirst(),pool,n.bounds,n.transports.getFirst(),
                                    temp.resolve("confirmed-round"),System::nanoTime,budget,2,builder().configuration(),
                                    n.f.request.targets().getFirst().materialization(),(event,record)->{},(event,record,voters)->{})) {
                                next.start();
                                for(int i=0;i<2;i++) {
                                    var target=n.owners.get(i);assertEquals(List.of(3L,4L),indices(target));
                                    var copy=target.floorCopyCurrent();var chosen=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
                                    var selected=MembershipSelectedLearnerRetention.find(copy.capsule,chosen,target.activationIdentity());
                                    // Publication of the fresh barrier may already
                                    // prune the obsolete install intent.
                                    selected.ifPresent(value->assertFalse(value.needsCompletion(uncheckedState(target))));
                                    assertTrue(object(parse(target.learnerRetentionState().plan().bytes(),16384)).containsKey("confirmation"));
                                    assertFalse(object(parse(target.learnerRetentionState().plan().bytes(),16384)).containsKey("renewals"));
                                }
                                n.f.snapshot("after-confirmed-selection");next.submit("CANCEL",canonical(Map.of("number",1L),8192));
                                n.f.snapshot("confirmed-cancelled");
                            }
                        }
                    }
                }
            }
            assertEquals(0,resources.usage().leases());
        }
        for(int i=0;i<2;i++)for(int repeat=0;repeat<2;repeat++)try(var owner=fixture.open(fixture.request.targets().get(i),"confirmation-cold-reopen")) {
            assertEquals(List.of(3L,4L),indices(owner));assertTrue(object(parse(owner.learnerRetentionState().plan().bytes(),16384)).containsKey("confirmation"));
            var copy=owner.floorCopyCurrent();owner.learnerRetentionState().plan().required(copy.capsule,copy.fileBytes("ancestry.gsr"));
        }
        fixture.snapshot("confirmation-reopened");
    }
    private static MembershipLearnerRetentionFiles.State uncheckedState(MembershipGrantJournal owner) {
        try{return owner.learnerRetentionState();}catch(Exception error){throw new AssertionError(error);}
    }
}
