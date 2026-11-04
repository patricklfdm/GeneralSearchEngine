package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual admitted 5-REPLACE originals, one interrupted seed floor and a cold
 * required old voter. No bootstrap, edited source or injected recovery copy. */
@EnabledIfSystemProperty(named="v53.joint.floor.recovery",matches="true")
class V53JointFloorRecoveryTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.MINUTES.toNanos(12);
    Path raw;

    @Test void originalFourCopyFloorResumesOverTcpBeforeFinalAndStableBarrier()throws Exception {
        var fixture=new V53JoiningIntentExportTest();fixture.temp=temp;boolean success=false;
        try {fixture.jointFloorRecovery(this::recover);success=true;}
        finally {
            if(raw!=null)Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-joint-floor-recovery-v1",
                "status",success?"PASS":"FAIL","profile","5-REPLACE","node","node-2","sameDirectory",true,
                "initialFloor","seed-maintenance-original-copies","recovery","native-tcp","processDeath",false,
                "phase3Complete",false),65536));
        }
    }

    private void recover(V53NativeDispatchTest.Network n,List<MembershipFloor.Copy> copies,
            MembershipGrantJournal joining,MembershipLearnerPlan plan,MembershipResources joiningResources,
            MembershipReplicaConfig<Integer,Doc> config,V53JoiningTrace trace)throws Exception {
        raw=Files.createDirectory(n.f.raw.resolve("joint-floor-recovery"));
        System.out.println("v53JointFloorRecoveryEvidence="+raw.toAbsolutePath());
        var target=n.f.request.targets().get(1);var old=n.owners.get(1);var budget=n.resources.get(1);
        var original=old.floorCopyCurrent();var proposal=MembershipFloor.create(n.f.result.root(),original,copies);
        assertEquals(List.of("node-1","node-2","node-3","node-6"),copies.stream().map(v->v.owner.nodeId().value()).toList());
        Files.write(raw.resolve("proposal.gsr"),proposal.bytes());
        Files.createDirectory(raw.resolve("originals"));
        for(var copy:copies) {
            Path path=copy.owner.nodeId().value().equals("node-6")?config.replicaDirectory():n.f.request.targets().get(Integer.parseInt(copy.owner.nodeId().value().substring(5))-1).replicaDirectory();
            V53JournalApplicationTest.copy(path,raw.resolve("originals/"+copy.owner.nodeId().value()));
        }
        Files.write(raw.resolve("lineage.json"),canonical(Map.of("root",n.f.result.root().manifestDigest(),"node","node-2",
            "replica",target.replicaDirectory().toString(),"application",target.materialization().directory().toString(),
            "cut",original.capsule.context.cut),65536));
        var usage=new ArrayList<Map<String,Object>>();long started=System.nanoTime();
        n.hook.set(event->{
            usage.add(Map.of("event",event,"usage",V53CombinedReceiveResourcesTest.usage(budget)));
            if(event.equals("FLOOR_COPIES_FORCED"))throw new IOException("joint floor interrupted before authority");
        });
        try {
            assertEquals("joint floor interrupted before authority",assertThrows(IOException.class,()->old.establishFloor(copies)).getMessage());
        }finally {n.hook.set(event->{});Files.write(raw.resolve("interrupted-usage.json"),canonical(usage,1024*1024));}
        assertFalse(Files.exists(target.replicaDirectory().resolve("floor-copies/floor.gsr")));
        V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("interrupted"));
        n.endpoints.get(1).close();n.transports.get(1).close();old.close();assertEquals(0,budget.usage().leases());
        V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("after-close"));
        var ownTrace=new V53JoiningTrace("node-2",n.events,n.wire);
        ownTrace.retainGrants(n.grantCapture,target.replicaDirectory());ownTrace.retainRetirements(n.retirementCapture,target.replicaDirectory());
        var resumedUsage=new ArrayList<Map<String,Object>>();var captured=new AtomicBoolean();
        var observed=ownTrace.cut("joint-floor-reopened");
        var reopened=MembershipGrantJournal.openRetainingFuturePeers(target.replicaDirectory(),target.materialization().directory(),
            n.f.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{
                observed.at(event);
                if(captured.get())return;
                resumedUsage.add(Map.of("event",event,"usage",V53CombinedReceiveResourcesTest.usage(budget)));
                if(event.equals("FLOOR_BEFORE_RETURN")) {
                    V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("resumed-floor"));
                    Files.write(raw.resolve("resumed-usage.json"),canonical(resumedUsage,2*1024*1024));
                    synchronized(n.events){Files.write(raw.resolve("floor-events.json"),V53EvidenceArray.encode(n.events,V53EvidenceArray.EVENT_BYTES));}
                    captured.set(true);
                }
            });
        n.owners.set(1,reopened);
        V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("after-reopen"));
        assertEquals(V53CombinedResourceRecoveryTest.disk(raw.resolve("after-close")),V53CombinedResourceRecoveryTest.disk(raw.resolve("after-reopen")));
        var endpoint=new MembershipActivationEndpoint(reopened,budget,n.bounds,
            (peer,request,kind,deadline)->n.links.get(1).get().exchange(peer,request,kind,deadline),List.of(),List.of(),
            temp.resolve("reopened-incoming"),System::nanoTime,BUDGET,builder().configuration(),target.materialization());
        n.endpoints.set(1,endpoint);
        var transport=new MembershipTransport(reopened,n.bounds,budget,endpoint::handle,ownTrace.transport("joint-floor-reopened"));
        n.transports.set(1,transport);n.links.get(1).set(transport);
        // The already admitted joining owner has not started its initialization
        // service yet. Expose its real current prefix on its permanent endpoint;
        // close it before the existing initialization service takes the socket.
        var joinedLink=new AtomicReference<MembershipTransport>();
        try(var joinedEndpoint=new MembershipActivationEndpoint(joining,joiningResources,n.bounds,
                (peer,request,kind,deadline)->joinedLink.get().exchange(peer,request,kind,deadline),List.of(),List.of(),
                temp.resolve("floor-joining-incoming"),System::nanoTime,BUDGET,builder().configuration(),config.materialization());
            var joinedTransport=new MembershipTransport(joining,n.bounds,joiningResources,joinedEndpoint::handle,trace.transport("joint-floor-export"))) {
            joinedLink.set(joinedTransport);
            try(var maintenance=MembershipGenerationMaintenance.beforeGrant(reopened,budget,n.bounds,transport::exchange,()->{},
                    temp.resolve("joint-floor-native-resume"),System::nanoTime,started,BUDGET)) {maintenance.run();}
        }
        assertTrue(captured.get(),"original floor forced before maintenance retirement");
        assertTrue(reopened.governingFloor().isEmpty(),"normal maintenance releases only the completed original floor");
        assertEquals(original.capsule.context.cut,reopened.activationContext().cut);
        V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("after-maintenance"));
        Files.write(raw.resolve("maintenance.json"),canonical(Map.of("status","PASS","originalDeadlineNanos",started+BUDGET,
            "startedNanos",started,"budgetNanos",BUDGET,"before",original.capsule.context.cut,"after",reopened.activationContext().cut),65536));
        System.out.println("v53JointFloorRecovery=original-floor-resumed-over-tcp");
    }
}
