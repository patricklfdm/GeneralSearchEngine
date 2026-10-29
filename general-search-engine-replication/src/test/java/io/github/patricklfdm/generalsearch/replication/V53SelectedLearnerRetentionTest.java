package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual native selected-source merge; learner export remains disabled until
 * the independent before-exposure quorum protocol is connected. */
class V53SelectedLearnerRetentionTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture(String name)throws Exception {
        var helper=new V53LearnerRetentionSourceTest();helper.temp=temp;var f=helper.fixture(name);
        for(var target:f.request.targets())try(var owner=f.open(target,"initialize")) {
            owner.initializePeerRetention();owner.initializeLearnerRetention();
        }
        return f;
    }
    @Test void remoteObligationsMergeBeforeAckSurviveInterruptedCompletionAndLaterCancellation()throws Exception {
        var f=fixture("native-union");var walk=new V53AdmittedCrossViewTest.Walk(f);walk.publish("BARRIER",null);
        var joining=V53DeclarationsTest.node(6);var targets=new ArrayList<MembershipIdentity>();f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
        var request=Map.of("root",f.result.root().manifestDigest(),"expected",walk.current().authority(),"number",1L,"kind","ADD",
                "target",targets.stream().map(MembershipBootstrapSeed::identity).toList());
        walk.publish("RESERVE",Map.of("request",request));walk.publish("PREPARE",Map.of("number",1L,"revision",1L));
        var first=f.request.targets().get(0);var second=f.request.targets().get(1);var third=f.request.targets().get(2);
        try(var owner=f.open(first,"pin-prepared")){owner.retainLearnerOffer(joining);}
        walk.publish("BARRIER",null);
        try(var owner=f.open(second,"pin-next")){owner.retainLearnerOffer(joining);}
        f.ballot=V53LearnerRetentionSourceTest.ballot(f);walk.counter++;
        var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var obsolete=new TreeMap<String,String>();
        for(var target:f.request.targets())try(var owner=f.open(target,"capture-merge")) {
            obsolete.put(target.identity().nodeId().value(),(String)owner.originalBasis().orElseThrow().value().get("basisId"));
            owner.prepareCurrent(f.ballot);var source=owner.originalSource();offers.add(source);
            var frozen=MembershipLearnerRetentionSource.read(source);
            assertEquals(target.equals(third)?List.of():List.of(target.equals(first)?3L:4L),
                    frozen.state().plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
            for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(target.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
        }
        var decision=new MembershipSelection.Campaign(offers.getFirst()).select(offers,List.of());
        byte[] original=Files.readAllBytes(third.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE));
        byte[] peers=Files.readAllBytes(third.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
        var merge=MembershipSelectedLearnerRetention.capture(decision,third.identity(),original);
        var peerMerge=MembershipSelectedRetention.capture(decision,third.identity(),peers);assertTrue(merge.completionBytes()>0);
        long used=Files.size(third.replicaDirectory().resolve(MembershipGrantJournal.FILE))
                +Files.size(third.replicaDirectory().resolve(MembershipPendingAccept.FILE))+MembershipPendingAccept.PREFIX
                +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA+peers.length+original.length;
        int maximum=Math.toIntExact(used+decision.selected().size()+merge.completionBytes()+peerMerge.completionBytes()-1);
        var before=V53ReplayFilesTest.files(third.replicaDirectory());
        try(var owner=MembershipGrantJournal.openRetainingLearners(third.replicaDirectory(),third.materialization().directory(),f.result.root(),third.identity(),f.resources,maximum,e->{})) {
            assertEquals("selected retention completion journal capacity",assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(offers,List.of())).getMessage());
            assertEquals(before,V53ReplayFilesTest.files(third.replicaDirectory()));assertTrue(owner.originalSelection().isEmpty());
        }
        for(var target:f.request.targets())try(var owner=f.open(target,"select-merge")){owner.selectCurrent(offers,List.of());}
        for(var target:f.request.targets()) {
            if(target.equals(third))f.observer=(t,op,event)->{if(op.equals("install-merge") && event.equals("LEARNER_RETENTION_PREFIX_WRITTEN"))throw new IOException("merge cut");};
            try(var owner=f.open(target,"install-merge")) {
                if(target.equals(third))assertThrows(IOException.class,()->owner.installCurrent(offers,List.of(),images));
                else owner.installCurrent(offers,List.of(),images);
            }
            f.observer=(t,op,event)->{};
        }
        f.snapshot("interrupted-merge");
        for(var target:f.request.targets())for(int repeat=0;repeat<2;repeat++)try(var owner=f.open(target,"recover-merge")) {
            var state=owner.learnerRetentionState();assertEquals(target.equals(third)?1:2,state.revision());
            assertEquals(List.of(3L,4L),state.plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
            var copy=owner.floorCopyCurrent();var selected=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
            var retained=MembershipSelectedLearnerRetention.find(copy.capsule,selected,target.identity()).orElseThrow();
            assertFalse(retained.needsCompletion(state));retained.plan.required(copy.capsule,copy.fileBytes("ancestry.gsr"));
            assertThrows(IllegalArgumentException.class,owner::checkLearnerRetentionExport);
        }
        f.snapshot("recovered-merge");walk.maintain("merged-sources-retired",f.request.targets(),obsolete);
        walk.publish("BARRIER",null);walk.publish("CANCEL",Map.of("number",1L));
        for(var target:f.request.targets())try(var owner=f.open(target,"cancel-reopened")) {
            var copy=owner.floorCopyCurrent();assertEquals(6L,copy.capsule.context.cut.get("index"));
            var retained=owner.learnerRetentionState().plan().required(copy.capsule,copy.fileBytes("ancestry.gsr"));
            assertEquals(List.of(3L,4L),retained.stream().map(a->number(a.cut().get("index"))).toList());
            assertTrue(MembershipSelectedLearnerRetention.find(copy.capsule,decode(copy.fileBytes("selected.gsr"),"records","SELECTED"),target.identity()).isEmpty());
        }
        Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","scope","native-local-selected-learner-retention", "slots",6L,
                "retained",List.of(3L,4L),"events",f.calls,"quorumExport",false,"phase3Complete",false),8*1024*1024));
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void includedStateSelectionAndLocalRevisionMustRemainExact()throws Exception {
        var f=fixture("binding");f.campaign(1);var first=f.request.targets().getFirst();
        try(var owner=f.open(first,"verify-binding")) {
            var copy=owner.floorCopyCurrent();var selected=decode(copy.fileBytes("selected.gsr"),"records","SELECTED");
            var intent=MembershipSelectedLearnerRetention.find(copy.capsule,selected,first.identity()).orElseThrow();
            assertFalse(intent.needsCompletion(owner.learnerRetentionState()));byte[] original=intent.bytes();
            var images=new TreeMap<String,byte[]>();for(String h:copy.capsule.packet.images().keySet())images.put(h,copy.fileBytes(h+".image"));
            for(String mutation:List.of("checksum","included-state","base","trailing","missing")) {
                var objects=new TreeMap<String,byte[]>();for(String h:copy.capsule.packet.objectNames())objects.put(h,copy.capsule.packet.objectBytes(h));objects.remove(hash(original));
                byte[] changed=original.clone();
                if(mutation.equals("trailing"))changed=Arrays.copyOf(changed,changed.length+1);
                else if(!mutation.equals("missing")) {
                    if(mutation.equals("base")) {
                        var b=java.nio.ByteBuffer.wrap(changed);b.position(HEADER);int n=b.getInt();b.position(b.position()+n);n=b.getInt();b.position(b.position()+n);n=b.getInt();changed[b.position()+n-1]^=1;
                    }else changed[changed.length-1]^=1;
                    if(!mutation.equals("checksum"))System.arraycopy(sha(Arrays.copyOf(changed,16),Arrays.copyOfRange(changed,HEADER,changed.length)),0,changed,16,32);
                }
                if(!mutation.equals("missing"))objects.put(hash(changed),changed);
                var packet=V53PeerRetentionSourceTest.objects(copy.capsule.packet,objects);var capsule=copy.capsule.materialization(packet,images,List.of());
                if(Set.of("checksum","trailing","missing").contains(mutation))assertTrue(MembershipSelectedLearnerRetention.find(capsule,selected,first.identity()).isEmpty());
                else assertThrows(IllegalArgumentException.class,()->MembershipSelectedLearnerRetention.find(capsule,selected,first.identity()));
            }
            var state=owner.learnerRetentionState();
            assertThrows(IllegalArgumentException.class,()->intent.needsCompletion(new MembershipLearnerRetentionFiles.State(state.revision(),"ff".repeat(32),state.plan())));
            assertTrue(MembershipSelectedLearnerRetention.MAXIMUM<FRAME);
        }
    }
}
