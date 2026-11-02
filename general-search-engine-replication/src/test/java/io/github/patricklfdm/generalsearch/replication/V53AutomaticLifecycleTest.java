package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53AutomaticOwnerTest.*;
import static io.github.patricklfdm.generalsearch.replication.V53AutomaticCampaignTest.*;

/** Observation tests do not supply native protocol votes or publications. */
class V53AutomaticLifecycleTest {
    @TempDir Path temp;
    static MembershipAutomaticOwner owner(Fixture f,Probe first,MembershipAutomaticOwner.Factory next,
            int rounds,MembershipAutomaticOwner.Events events) {
        return new MembershipAutomaticOwner(first,next,rounds,f.resources,bound(4),POLICY,f.clock::get,ms(100),events);
    }
    @Test void observesActualDrainFreshSessionAndUnchangedOriginalStart()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.startFailure=lost();
        var observed=Collections.synchronizedList(new ArrayList<MembershipAutomaticOwner.Observation>());
        try(var owner=owner(f,first,()->{assertTrue(first.closes.get()>0);f.clock.set(ms(130));return second;},2,observed::add)) {
            assertSame(second.answer,owner.start().await(5,TimeUnit.SECONDS));
            assertEquals(List.of("START","ROUND_BEGIN","LOSS","RESTART","SESSION_CLOSED","SESSION_OPENED","ROUND_BEGIN","READY"),
                         observed.stream().map(MembershipAutomaticOwner.Observation::event).toList());
            assertEquals(List.of(0,1,1,1,1,1,2,2),observed.stream().map(MembershipAutomaticOwner.Observation::rounds).toList());
            assertTrue(observed.stream().allMatch(v->v.originalStarted()==ms(100)));
            assertEquals(first.original,second.original);assertEquals("HIGHER_BALLOT",observed.get(2).detail());
            assertEquals(second.answer.digest(),observed.getLast().detail());assertTrue(owner.observationFailure().isEmpty());
            owner.close();assertTrue(owner.drained());
            assertEquals("DRAINED",observed.getLast().event());assertEquals(0,observed.getLast().pending());
            assertTrue(observed.stream().anyMatch(v->v.event().equals("TERMINATED") && v.detail().equals("DRAINED")));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void failedObserverIsRetainedWithoutRetryingOrChangingProtocolOutcome()throws Exception {
        for(String cut:List.of("START","ROUND_BEGIN","LOSS","RESTART","SESSION_CLOSED","SESSION_OPENED","READY","CLOSE","TERMINATED","DRAINED")) {
            var f=new Fixture();var first=new Probe();var second=new Probe();first.startFailure=lost();
            var observed=new ArrayList<String>();var failed=new IOException("capture unavailable");
            try(var owner=owner(f,first,()->second,2,event->{observed.add(event.event());if(event.event().equals(cut))throw failed;})) {
                assertSame(second.answer,owner.start().await(5,TimeUnit.SECONDS));
                assertSame(second.answer,owner.submit("DATA",new byte[]{1}).await(5,TimeUnit.SECONDS));owner.close();
                assertSame(failed,owner.observationFailure().orElseThrow().getCause(),cut);
                assertEquals(cut,observed.getLast());assertTrue(owner.failure().isEmpty());assertTrue(owner.drained());
                assertEquals(List.of("start"),first.calls);assertEquals(List.of("start","DATA"),second.calls);
            }
            assertEquals(0,f.resources.usage().leases(),cut);
        }
    }
    @Test void maximumRoundsAndTerminalFailureAreObservedWithoutInventingRetry()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.startFailure=lost();second.startFailure=lost();
        var observed=Collections.synchronizedList(new ArrayList<MembershipAutomaticOwner.Observation>());
        try(var owner=owner(f,first,()->second,2,observed::add)) {
            assertSame(second.startFailure,assertThrows(ExecutionException.class,()->owner.start().await(5,TimeUnit.SECONDS)).getCause());
            owner.close();assertEquals(2,observed.stream().filter(v->v.event().equals("LOSS")).count());
            assertEquals(1,observed.stream().filter(v->v.event().equals("RESTART")).count());
            assertTrue(observed.stream().anyMatch(v->v.event().equals("FAILED") && v.state()==MembershipAutomaticOwner.State.FAILED));
            assertTrue(observed.stream().noneMatch(v->v.event().equals("READY")));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void admittedMutationIsNeverReplayedByAnObservedRestart()throws Exception {
        var f=new Fixture();var first=new Probe();var second=new Probe();first.submitGate=new CountDownLatch(1);first.submitFailure=lost();
        var observed=Collections.synchronizedList(new ArrayList<MembershipAutomaticOwner.Observation>());
        try(var owner=owner(f,first,()->second,2,observed::add)) {
            owner.start().await(5,TimeUnit.SECONDS);var call=owner.submit("DATA",new byte[]{1});await(first.entered);
            first.submitGate.countDown();assertSame(first.submitFailure,assertThrows(ExecutionException.class,()->call.await(5,TimeUnit.SECONDS)).getCause());
            V53MembershipTransportTest.waitFor(()->owner.rounds()==2 && owner.state()==MembershipAutomaticOwner.State.READY);
            assertSame(second.answer,owner.readiness().await(5,TimeUnit.SECONDS));
            assertEquals(List.of("start","DATA"),first.calls);assertEquals(List.of("start","guard"),second.calls);
            assertEquals(2,observed.stream().filter(v->v.event().equals("READY")).count());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void closeBeforeStartDoesNotInventRoundReadinessOrWorkerTermination()throws Exception {
        var f=new Fixture();var first=new Probe();var observed=new ArrayList<MembershipAutomaticOwner.Observation>();
        var owner=owner(f,first,()->first,1,observed::add);owner.close();
        assertEquals(List.of("CLOSE","SESSION_CLOSED","DRAINED"),observed.stream().map(MembershipAutomaticOwner.Observation::event).toList());
        assertTrue(observed.stream().allMatch(v->v.rounds()==0 && v.originalStarted()==0 && v.state()==MembershipAutomaticOwner.State.CLOSED));
        assertTrue(owner.drained());assertEquals(0,f.resources.usage().leases());
    }
    @Test void captureAnchorsOriginalTraceAndNeverOverwritesOrExceedsItsBound()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var capture=new V53AutomaticLifecycleCapture(temp,events);
        var row=new MembershipAutomaticOwner.Observation("START",MembershipAutomaticOwner.State.STARTING,0,0,100,"");
        capture.at("node-1",row);V53CompetingNodeQualification.observe(events,Map.of("node","node-1","event","NODE_OPEN"));
        capture.at("node-2",row);capture.save();
        var values=list(parse(Files.readAllBytes(temp.resolve(V53AutomaticLifecycleCapture.FILE)),1024*1024));
        assertEquals(-1L,number(object(values.getFirst()).get("afterEvent")));
        assertEquals(0L,number(object(values.getLast()).get("afterEvent")));
        assertEquals(1L,number(object(values.getFirst()).get("ordinal")));assertEquals(1L,number(object(values.getLast()).get("ordinal")));
        assertTrue(number(object(values.getFirst()).get("nanoTime"))<=number(events.getFirst().get("nanoTime")));
        assertTrue(number(object(values.getLast()).get("nanoTime"))>=number(events.getFirst().get("nanoTime")));
        assertEquals(1,events.size());assertThrows(FileAlreadyExistsException.class,capture::save);
        for(int i=2;i<256;i++)capture.at("node-1",row);
        assertEquals("automatic lifecycle capture bound",assertThrows(IOException.class,()->capture.at("node-1",row)).getMessage());
    }
    @Test void nativeNodeRetainsObservationFailureAfterAllChildrenDrain()throws Exception {
        var helper=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("raw")),
            V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group")),3,false));
        helper.ownedHistory=true;
        for(var voter:helper.request.targets())try(var journal=helper.open(voter,"initialize-retention")) {
            journal.initializePeerRetention();journal.initializeFutureRetention();
        }
        var target=helper.request.targets().getFirst();var bounds=ReplicationBounds.defaults();
        var config=new MembershipReplicaConfig<>(helper.result.root(),target.identity(),helper.request.targets().stream()
            .map(MembershipBootstrapTarget::identity).filter(v->!v.equals(target.identity())).toList(),target.replicaDirectory(),target.materialization(),bounds,
            AutomaticLeadershipPolicy.forBounds(bounds));
        var hooks=new MembershipNodeOwner.Hooks(event->{},MembershipTransport.Events.NONE,MembershipRoundDriver.Events.NONE,
            MembershipSlotDriver.Events.NONE,event->{throw new IOException("cannot retain lifecycle");});
        try(var node=new MembershipNodeOwner<>(config,io.github.patricklfdm.generalsearch.admission.OfflineApplication.builder().configuration(),
                temp.resolve("incoming"),temp.resolve("outgoing"),System::nanoTime,TimeUnit.SECONDS.toNanos(60),hooks)) {
            node.open();node.close();assertTrue(node.observationFailure().isPresent());assertEquals(0,node.usage().leases());
        }
    }
}
