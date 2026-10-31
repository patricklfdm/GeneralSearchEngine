package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53PeerRetentionPlanTest.cuts;

/** Real native publication with cold owners; no larger endpoint or journal budget. */
class V53MaintenanceObservationTest {
    @TempDir Path temp;
    private static byte[] ancestry(MembershipFloor.Copy copy) {
        return copy.fileNames().contains("ancestry.gsr")?copy.fileBytes("ancestry.gsr"):new byte[0];
    }

    @Test void optionalMaintenancePreservesFullDebtUntilVerifiedSelection()throws Exception {
        var helper=new V53SelectedRetentionTest();helper.temp=temp;var f=helper.fixture("maintenance-observation");
        f.campaign(1);
        for(int slot=1;slot<=4;slot++) {
            f.publish(slot,slot==2);
            var originals=new ArrayList<MembershipFloor.Copy>();
            for(var target:f.request.targets())try(var owner=f.open(target,"observation-copy-"+slot)) {
                originals.add(owner.floorCopyCurrent());
            }
            for(var target:f.request.targets())try(var owner=f.open(target,"maintenance-observation-"+slot)) {
                byte[] before=Files.readAllBytes(target.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
                for(var copy:originals) {
                    if(slot>2)assertEquals("peer retention pending renewal capacity",
                            assertThrows(IllegalArgumentException.class,()->owner.retainPeerObservation(copy)).getMessage());
                    owner.retainMaintenancePeerObservation(copy);
                }
                var state=owner.peerRetentionState();
                for(var peer:f.request.targets())assertEquals(List.of((long)Math.min(slot,2)),cuts(state.plan().possible(peer.identity())));
                if(slot>2)assertArrayEquals(before,Files.readAllBytes(target.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE)));
                var original=owner.floorCopyCurrent();
                assertEquals(slot==1?List.of(0L,1L):List.of(0L,1L,2L),cuts(state.plan().required(original.capsule,ancestry(original))));
                if(slot==3) {
                    // Deferral must retain a later unresolved dispatch too.
                    var pending=state.plan().dispatch(original.capsule,ancestry(original),original.owner);
                    assertArrayEquals(pending.bytes(),pending.observeForMaintenance(original.capsule,ancestry(original),original).bytes());
                    assertEquals(List.of(2L,3L),cuts(pending.possible(original.owner)));
                    assertThrows(IllegalArgumentException.class,()->pending.observe(original.capsule,ancestry(original),original));
                    // Capacity cannot suppress missing original ancestry checks.
                    assertThrows(IllegalArgumentException.class,()->state.plan().observeForMaintenance(original.capsule,new byte[0],original));
                }
            }
            f.snapshot("observed-"+slot);
        }
        // Only a fresh, verified selected-source merge releases the old debts.
        f.campaign(2);
        for(var target:f.request.targets())try(var owner=f.open(target,"reconciled-observations")) {
            var plan=owner.peerRetentionState().plan();
            for(var row:list(object(parse(plan.bytes(),32768)).get("peers")))assertFalse(object(row).containsKey("renewals"));
            for(var peer:f.request.targets())assertEquals(List.of(2L),cuts(plan.possible(peer.identity())));
        }
        f.publish(5,false);
        MembershipFloor.Copy latest;try(var owner=f.open(f.request.targets().getLast(),"resumed-copy")){latest=owner.floorCopyCurrent();}
        var target=f.request.targets().getFirst();
        try(var owner=f.open(target,"resumed-observation")) {
            var before=owner.peerRetentionState();var after=owner.retainMaintenancePeerObservation(latest);
            assertEquals(before.revision()+1,after.revision());assertEquals(List.of(5L),cuts(after.plan().possible(latest.owner)));
            assertEquals(List.of(2L,5L),cuts(after.plan().required(latest.capsule,ancestry(latest))));
        }
        try(var owner=f.open(target,"resumed-cold-reopen")) {
            assertEquals(List.of(5L),cuts(owner.peerRetentionState().plan().possible(latest.owner)));
        }
        f.snapshot("resumed-observation");
        Files.write(f.raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
        Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","publications",5L,"campaigns",2L,"deferredCuts",List.of(3L,4L)),8192));
        assertEquals(0,f.resources.usage().leases());
    }

    @Test void optionalObservationStillRejectsForeignCopiesAndKeepsGenesisIdempotent()throws Exception {
        var helper=new V53PeerRetentionPlanTest();helper.temp=temp;
        var zero=V53PeerRetentionPlanTest.capsule(3,0);var one=V53PeerRetentionPlanTest.capsule(3,1);
        var plan=MembershipPeerRetentionPlan.genesis(zero);var foreign=helper.copy(4,1,2);
        assertThrows(IllegalArgumentException.class,()->plan.observeForMaintenance(one,new byte[0],foreign));
        var genesis=helper.copy(3,0,2);
        assertArrayEquals(plan.bytes(),plan.observeForMaintenance(zero,new byte[0],genesis).bytes());
        var next=helper.copy(3,1,2);
        assertArrayEquals(plan.observe(one,new byte[0],next).bytes(),plan.observeForMaintenance(one,new byte[0],next).bytes());
    }
}
