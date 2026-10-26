package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SelectedRetentionTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture(String name)throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-selected-retention/run-"+UUID.randomUUID()));
        System.out.println("v53SelectedRetentionEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),raw,3,false);f.ownedHistory=true;
        for(var t:f.request.targets())try(var owner=f.open(t,"initialize")){owner.initializePeerRetention();}
        return f;
    }
    @Test void selectedUnionSurvivesSourceRetirementAndDoesNotUndoLaterObservation()throws Exception {
        var f=fixture("union");f.campaign(1);f.publish(1,false);
        var one=f.request.targets().getFirst();var two=f.request.targets().get(1);var three=f.request.targets().get(2);
        try(var owner=f.open(one,"ambiguous-dispatch")){owner.retainPeerDispatch(three.identity());}
        f.campaign(2);
        for(var t:f.request.targets())try(var owner=f.open(t,"merged")) {
            assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(three.identity())));
            assertEquals(1,owner.peerRetentionState().revision());
            var copy=owner.floorCopyCurrent();var selection=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
            var retained=MembershipSelectedRetention.find(copy.capsule,selection,t.identity()).orElseThrow();
            assertFalse(retained.needsCompletion(owner.peerRetentionState()));retained.plan.required(copy.capsule,new byte[0]);
        }
        MembershipFloor.Copy observed;try(var owner=f.open(three,"actual-copy")){observed=owner.floorCopyCurrent();}
        try(var owner=f.open(two,"narrow-after-selection")) {
            assertEquals(2,owner.retainPeerObservation(observed).revision());
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(three.identity())));
        }
        for(int i=0;i<2;i++)try(var owner=f.open(two,"reopen-narrowed")) {
            assertEquals(2,owner.peerRetentionState().revision());
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(three.identity())));
        }
        f.publish(2,true);
        try(var owner=f.open(two,"published")) {
            assertEquals(2,owner.peerRetentionState().revision());
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(three.identity())));
            var copy=owner.floorCopyCurrent();assertTrue(MembershipSelectedRetention.find(copy.capsule,decode(copy.fileBytes("selected.gsr"),"records","SELECTED"),two.identity()).isEmpty());
        }
        Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","events",f.calls),8*1024*1024));
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void missingSelectedSnapshotRefusesBeforeRecordingSelection()throws Exception {
        var f=fixture("missing");var first=f.request.targets().getFirst();var other=f.request.targets().get(2);
        // The optional legacy entry can grant without a ledger. The required
        // selected path must reject it, not silently infer genesis uncertainty.
        Files.delete(other.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
        Map<String,Object> ballot;try(var owner=f.open(first,"allocate")){ballot=Map.of("counter",owner.reserveCounter(),"proposer",first.identity().nodeId().value(),"incarnation",first.identity().storageId().toString());}
        var sources=new ArrayList<MembershipSelection.Source>();
        for(var t:f.request.targets())try(var owner=f.open(t,"prepare")){owner.prepareCurrent(ballot);sources.add(owner.originalSource());}
        try(var owner=f.open(first,"refuse")) {
            var before=V53ReplayFilesTest.files(first.replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(sources,List.of()));
            assertEquals(before,V53ReplayFilesTest.files(first.replicaDirectory()));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void exactIncludedBytesAndOriginalSelectionAreRequired()throws Exception {
        var f=fixture("binding");f.campaign(1);var self=f.request.targets().getFirst();
        try(var owner=f.open(self,"binding")) {
            var copy=owner.floorCopyCurrent();var selected=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
            var intent=MembershipSelectedRetention.find(copy.capsule,selected,self.identity()).orElseThrow();byte[] original=intent.bytes();
            var images=new TreeMap<String,byte[]>();for(String h:copy.capsule.packet.images().keySet())images.put(h,copy.fileBytes(h+".image"));
            for(String mutation:List.of("checksum","included-object","base","trailing","missing")) {
                var objects=new TreeMap<String,byte[]>();for(String h:copy.capsule.packet.objectNames())objects.put(h,copy.capsule.packet.objectBytes(h));objects.remove(hash(original));
                byte[] changed=original.clone();
                if(mutation.equals("trailing"))changed=Arrays.copyOf(changed,changed.length+1);
                else if(!mutation.equals("missing")) {
                    if(mutation.equals("base")) {
                        var b=java.nio.ByteBuffer.wrap(changed);b.position(HEADER);
                        int n=b.getInt();b.position(b.position()+n);n=b.getInt();b.position(b.position()+n);n=b.getInt();changed[b.position()+n-1]^=1;
                    }else changed[changed.length-1]^=1;
                    if(!mutation.equals("checksum"))System.arraycopy(sha(Arrays.copyOf(changed,16),Arrays.copyOfRange(changed,HEADER,changed.length)),0,changed,16,32);
                }
                if(!mutation.equals("missing"))objects.put(hash(changed),changed);
                var packet=V53PeerRetentionSourceTest.objects(copy.capsule.packet,objects);var capsule=copy.capsule.materialization(packet,images,List.of());
                if(Set.of("checksum","trailing","missing").contains(mutation))assertTrue(MembershipSelectedRetention.find(capsule,selected,self.identity()).isEmpty(),mutation);
                else assertThrows(IllegalArgumentException.class,()->MembershipSelectedRetention.find(capsule,selected,self.identity()),mutation);
            }
            var before=owner.peerRetentionState();
            assertFalse(intent.needsCompletion(before));
            assertThrows(IllegalArgumentException.class,()->intent.needsCompletion(new MembershipPeerRetentionFiles.State(before.revision(),"f".repeat(64),before.plan())));
            assertTrue(MembershipSelectedRetention.MAXIMUM<MembershipFormat.FRAME);
        }
    }
    @Test void selectionReservesTheWholeMergeBeforeAnySelectedWrite()throws Exception {
        var f=fixture("selection-capacity");f.campaign(1);f.publish(1,false);
        var first=f.request.targets().getFirst();var self=f.request.targets().get(1);var peer=f.request.targets().get(2);
        try(var owner=f.open(first,"dispatch")){owner.retainPeerDispatch(peer.identity());}
        Map<String,Object> ballot;
        try(var owner=f.open(first,"allocate")){ballot=Map.of("counter",owner.reserveCounter(),"proposer",first.identity().nodeId().value(),"incarnation",first.identity().storageId().toString());}
        var sources=new ArrayList<MembershipSelection.Source>();
        for(var t:f.request.targets())try(var owner=f.open(t,"prepare")){owner.prepareCurrent(ballot);sources.add(owner.originalSource());}
        var decision=new MembershipSelection.Campaign(sources.getFirst()).select(sources,List.of());
        byte[] active=Files.readAllBytes(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
        var intent=MembershipSelectedRetention.capture(decision,self.identity(),active);assertTrue(intent.completionBytes()>0);
        long used=Files.size(self.replicaDirectory().resolve(MembershipGrantJournal.FILE))
                +Files.size(self.replicaDirectory().resolve(MembershipPendingAccept.FILE))+MembershipPendingAccept.PREFIX
                +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA+active.length;
        int maximum=Math.toIntExact(used+decision.selected().bytes().length+intent.completionBytes()-1);
        var before=V53ReplayFilesTest.files(self.replicaDirectory());
        try(var owner=MembershipGrantJournal.openRetainingPeers(self.replicaDirectory(),self.materialization().directory(),f.result.root(),
                self.identity(),f.resources,maximum,event->{})) {
            var failure=assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(sources,List.of()));
            assertEquals("selected retention completion journal capacity",failure.getMessage());
            assertEquals(before,V53ReplayFilesTest.files(self.replicaDirectory()));
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
