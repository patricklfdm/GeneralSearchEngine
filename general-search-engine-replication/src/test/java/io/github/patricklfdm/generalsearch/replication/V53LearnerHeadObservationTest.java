package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53LearnerHeadObservationTest {
    @TempDir Path temp;
    @Test void actualPreparedSelectionBindsObservationAndCloseRevokesIt()throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var f=helper.new Fixture();var typed=f.prepare(e->{})) {
            assertThrows(IllegalArgumentException.class,typed::currentHead);
            var head=typed.retainGeneration();var baseline=f.source.client.usage();
            try(var observed=MembershipLearnerHeadObservation.capture(head)) {
                assertEquals(baseline.queued()+MembershipLearnerHeadObservation.BYTES,f.source.client.usage().queued());
                assertEquals(MembershipLearnerDiscovery.request(f.source.request.change()),observed.request);
                assertEquals(f.source.request.identity(),observed.learner);assertEquals(head.source().terminal(),observed.endpoint);
                var original=f.source.fixture.fixture;var current=head.source();
                var earlier=V53CapsuleFixture.fromHistory(original.source,2).verify();
                var initial=V53CapsuleFixture.fromHistory(original.source,0).verify();
                var plan=MembershipLearnerRetentionPlan.genesis(initial).offer(earlier,new byte[0],observed.learner);
                var bridge=V53LearnerProgressNetworkTest.bridge(original,2,3);
                var retained=current.retainingVerifiedAncestry(List.of(bridge));byte[] ancestry=MembershipGenerationPlan.ancestry(List.of(bridge));
                plan=plan.offer(retained,ancestry,observed.learner);
                assertEquals(2,plan.recorded().size());var narrowed=plan.observe(retained,ancestry,observed);
                assertEquals(List.of(observed.endpoint),narrowed.recorded());
                assertArrayEquals(narrowed.bytes(),narrowed.observe(retained,ancestry,observed).bytes());
                var later=V53CapsuleFixture.fromHistory(original.source,4).verify();
                var forward=V53LearnerProgressNetworkTest.bridge(original,3,4);
                later=later.retainingVerifiedAncestry(List.of(forward));byte[] laterAncestry=MembershipGenerationPlan.ancestry(List.of(forward));
                var uncertain=narrowed.offer(later,laterAncestry,observed.learner);
                assertArrayEquals(uncertain.bytes(),uncertain.observe(later,laterAncestry,observed).bytes(),"old observation cannot discharge a newer offered endpoint");
                var advanced=MembershipLearnerRetentionPlan.genesis(initial).offer(later,laterAncestry,observed.learner);
                assertArrayEquals(advanced.bytes(),advanced.observe(later,laterAncestry,observed).bytes(),"late old observation cannot regress a narrowed ledger");
                var wrong=object(V53ContextFixture.mutable(parse(plan.bytes(),16384)));object(wrong.get("request")).put("expected","ab".repeat(32));
                var foreign=MembershipLearnerRetentionPlan.decode(canonical(wrong,16384));
                assertThrows(IllegalArgumentException.class,()->foreign.observe(retained,ancestry,observed));
                var unoffered=MembershipLearnerRetentionPlan.genesis(initial).offer(earlier,new byte[0],observed.learner);
                assertEquals(List.of(observed.endpoint),unoffered.observe(retained,ancestry,observed).recorded(),
                        "another source may have offered the actual forced head");
                var after=V53ReplayFilesTest.files(f.base);typed.close();
                assertThrows(IllegalArgumentException.class,observed::check);
                assertThrows(IllegalArgumentException.class,()->narrowed.observe(retained,ancestry,observed));
                assertEquals(after,V53ReplayFilesTest.files(f.base));
            }
            assertEquals(baseline.queued(),f.source.client.usage().queued());
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerHeadObservation.capture(head));
            assertEquals(baseline.queued(),f.source.client.usage().queued());
        }
    }
    @Test void currentPromotedHeadObservationUsesExistingBudgetAndDoesNotSelectAnotherGeneration()throws Exception {
        var helper=new V53LearnerSlotTest();helper.temp=temp;
        try(var f=helper.fixture(5,"REPLACE");var typed=helper.current(f)) {
            var head=typed.currentHead();var before=V53ReplayFilesTest.files(f.base);var baseline=f.source.client.usage();
            try(var occupied=f.source.client.reserve(MembershipResources.Unit.CONTROL,"observation-budget",
                    MembershipResources.Unit.CONTROL.bytes)) {
                var rest=new ArrayList<MembershipResources.Lease>();
                try {
                    while(f.source.client.usage().queued()+MembershipLearnerHeadObservation.BYTES<=MembershipResources.QUEUE_LIMIT)
                        rest.add(f.source.client.reserve(MembershipResources.Unit.CONTROL,"busy-"+rest.size(),
                                Math.min(MembershipResources.Unit.CONTROL.bytes,MembershipResources.QUEUE_LIMIT-f.source.client.usage().queued())));
                    var full=f.source.client.usage();assertThrows(IllegalArgumentException.class,()->MembershipLearnerHeadObservation.capture(head));
                    assertEquals(full,f.source.client.usage());
                }finally {rest.forEach(MembershipResources.Lease::close);}
            }
            try(var observation=MembershipLearnerHeadObservation.capture(head)) {
                assertEquals(head.source().terminal(),observation.endpoint);observation.close();
                assertThrows(IllegalArgumentException.class,observation::check);
            }
            assertEquals(before,V53ReplayFilesTest.files(f.base));assertEquals(baseline,f.source.client.usage());
        }
    }
    @Test void nativeTwoEndpointLedgerNarrowsOnlyAfterRealTypedSelectionAndResumesInterruptedUpdate()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;var network=new V53NativeDispatchTest();network.temp=temp;
        long budget=TimeUnit.SECONDS.toNanos(600);V53BootstrapPublicationTest.Fixture fixture;
        try(var n=network.new Network(3,helper.controlBounds(),budget,f->{
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-learner-retention")){owner.initializeLearnerRetention();}
        },true)) {
            fixture=n.f;System.out.println("v53LearnerHeadObservationEvidence="+n.f.raw.toAbsolutePath());
            try(var round=helper.driver(n,MembershipRoundDriver.Events.NONE,budget)) {
                round.start();int port;try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
                var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
                var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
                var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),n.owners.getFirst().activationContext().authority(),MembershipChangeKind.ADD,targets);
                var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("replica"),temp.resolve("operation"));
                round.submit("RESERVE",canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192));
                try(var recording=new MembershipLearnerRetentionQuorum(n.owners.getFirst(),joining,n.ballot,n.resources.getFirst(),
                        n.transports.getFirst()::exchange,System::nanoTime,System.nanoTime(),budget)) {recording.run();}
                round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));
                var resources=new MembershipResources(512*MembershipResources.MIB);
                var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("core"),2),
                        n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
                try(var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,MembershipTransport.Events.NONE,
                        ()->{},System::nanoTime,System.nanoTime(),budget)) {
                    source.fetch(temp.resolve("receiving"));var summary=source.plan(e->{});
                    try(var store=source.admit(summary,e->{})) {
                        source.close();
                        try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,e->{});
                                var observed=MembershipLearnerHeadObservation.capture(typed.retainGeneration())) {
                            n.f.snapshot("before-head-observation");
                            for(int i=0;i<2;i++)assertEquals(List.of(2L,3L),n.owners.get(i).learnerRetentionState().plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
                            var state=n.owners.getFirst().retainLearnerObservation(observed);assertEquals(3,state.revision());
                            assertEquals(List.of(observed.endpoint),state.plan().recorded());
                            assertEquals(state,n.owners.getFirst().retainLearnerObservation(observed));
                            n.hook.set(event->{if(event.equals("LEARNER_RETENTION_WRITTEN"))throw new IOException("observation interrupted before force");});
                            assertThrows(IOException.class,()->n.owners.get(1).retainLearnerObservation(observed));
                            n.hook.set(event->{});n.f.snapshot("after-head-observation");
                            observed.close();var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
                            assertThrows(IllegalArgumentException.class,()->n.owners.getFirst().retainLearnerObservation(observed));
                            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                            assertEquals(state,n.owners.getFirst().learnerRetentionState());
                        }
                    }
                }
                assertEquals(0,resources.usage().leases());
            }
        }
        for(int i=0;i<2;i++) {
            var target=fixture.request.targets().get(i);var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var owner=MembershipGrantJournal.openRetainingLearners(target.replicaDirectory(),target.materialization().directory(),fixture.result.root(),target.identity(),resources,
                    MembershipGrantJournal.MAXIMUM,e->{})) {
                assertEquals(i==0?List.of(3L):List.of(2L,3L),owner.learnerRetentionState().plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
                assertFalse(Files.exists(target.replicaDirectory().resolve(MembershipLearnerRetentionFiles.NEXT)));
            }
            assertEquals(0,resources.usage().leases());
        }
    }
}
