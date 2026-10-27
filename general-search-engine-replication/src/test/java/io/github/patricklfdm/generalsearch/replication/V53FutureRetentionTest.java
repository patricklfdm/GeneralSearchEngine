package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53FutureRetentionTest {
    @TempDir Path temp;
    static V53BootstrapPublicationTest.Fixture ready(Path home,Path raw)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(home,raw,3,false);f.ownedHistory=true;f.nativeApplication=true;
        for(var t:f.request.targets())try(var owner=f.open(t,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
        f.snapshot("retaining-genesis");f.campaign(1);
        f.observer=(target,operation,event)->{if(operation.equals("apply-1"))throw new V53NativeApplicationTest.Stop();};
        assertThrows(V53NativeApplicationTest.Stop.class,()->f.publish(1,false));f.observer=(target,operation,event)->{};f.observations.clear();
        f.snapshot("certified");
        for(var t:f.request.targets())try(var owner=f.open(t,"initial-apply")){owner.applyCurrent(builder().configuration(),t.materialization());}
        f.snapshot("before-future");return f;
    }
    @Test void localFutureSurvivesReopenAndPromotesBeforeItsProofIsCleared()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-retention/native-"+UUID.randomUUID()));
        System.out.println("v53FutureRetentionEvidence="+raw.toAbsolutePath());
        var f=ready(Files.createDirectory(temp.resolve("native")),raw);var local=f.request.targets().getFirst();var peer=f.request.targets().get(1);
        try {
            try(var owner=f.open(local,"record-future")) {
                var target=owner.pendingPublication(owner.applyCurrent(builder().configuration(),local.materialization()));
                var result=owner.retainFutureDispatch(peer.identity(),target);assertTrue(result.pending());assertEquals(1,result.revision);
                assertEquals(target.target(),result.target());assertEquals(1,result.peers.size());
                var original=V53ReplayFilesTest.files(local.replicaDirectory());
                assertEquals(result.digest,owner.retainFutureDispatch(peer.identity(),target).digest);
                assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",local.identity().storageId().toString())));
                assertEquals(original,V53ReplayFilesTest.files(local.replicaDirectory()));
                assertEquals(List.of(0L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            f.snapshot("pending-future");
            var acks=new ArrayList<Decoded>();var observations=new HashSet<MembershipContext.Owned>();
            for(var t:f.request.targets())try(var owner=f.open(t,"resume-apply")) {
                var applied=owner.applyCurrent(builder().configuration(),t.materialization());acks.add(applied.endorsement().acknowledgement());observations.add(applied.endorsement().owned());
            }
            try(var owner=f.open(local,"publish-future")) {
                assertTrue(owner.futureRetentionState().pending());var applied=owner.applyCurrent(builder().configuration(),local.materialization());
                owner.publishCurrent(applied,acks,observations,List.of());assertFalse(owner.futureRetentionState().pending());
                assertEquals(2,owner.futureRetentionState().revision);
                assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            f.snapshot("published-future");
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(local.replicaDirectory(),local.materialization().directory(),f.result.root(),local.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
                assertFalse(owner.futureRetentionState().pending());assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
            }
            var events=f.calls.stream().filter(v->v.get("operation").equals("publish-future")).findFirst().orElseThrow();var names=list(events.get("events"));
            assertTrue(names.indexOf("RETENTION_PARENT_FORCED")<names.indexOf("FUTURE_RETENTION_PROMOTED"));
            assertTrue(names.indexOf("FUTURE_RETENTION_PROMOTED")<names.indexOf("FUTURE_RETENTION_CLEARED"));
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void lostFutureAuthorityCannotBeReinitializedAfterCampaign()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-retention/lost-"+UUID.randomUUID()));
        var f=ready(Files.createDirectory(temp.resolve("lost")),raw);var t=f.request.targets().getFirst();
        try {
            Files.delete(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE));
            assertThrows(Exception.class,()->MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{}));
            assertFalse(Files.exists(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE)));assertEquals(0,f.resources.usage().leases());
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void completeFutureCandidateAndPromotionHeadroomAreAdmittedBeforeWriting()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-retention/capacity-"+UUID.randomUUID()));
        var f=ready(Files.createDirectory(temp.resolve("capacity")),raw);var t=f.request.targets().getFirst();var peer=f.request.targets().get(1);
        try {
            // Measure the exact real proposal, then return to its unchanged actual
            // input. The below-budget case must refuse before any candidate write;
            // the exact budget must complete both intent and later promotion.
            try(var owner=f.open(t,"reference-budget")) {
                owner.retainFutureDispatch(peer.identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization())));
            }
            long proposal=Files.size(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE));
            long clear=MembershipFutureRetentionFiles.encode(f.result.root().manifestDigest(),t.identity(),MembershipBallotAllocator.MAX,"0".repeat(64),null,List.of(),Map.of()).length;
            Files.move(t.replicaDirectory(),temp.resolve("reference-budget"));V53JournalApplicationTest.copy(raw.resolve("before-future/node-1"),t.replicaDirectory());
            long used=Files.size(t.replicaDirectory().resolve(MembershipGrantJournal.FILE))
                    +Files.size(t.replicaDirectory().resolve(MembershipPendingAccept.FILE))+MembershipPendingAccept.PREFIX
                    +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA
                    +Files.size(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE))+Files.size(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE));
            int maximum=Math.toIntExact(used+proposal+MembershipPeerRetentionFiles.MAXIMUM+clear);var original=V53ReplayFilesTest.files(t.replicaDirectory());
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,maximum-1,e->{})) {
                var target=owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization()));
                var failure=assertThrows(IllegalArgumentException.class,()->owner.retainFutureDispatch(peer.identity(),target));
                assertEquals("future retention completion journal capacity",failure.getMessage());
            }
            assertEquals(original,V53ReplayFilesTest.files(t.replicaDirectory()));assertFalse(Files.exists(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.NEXT)));
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,maximum,e->{})) {
                assertTrue(owner.retainFutureDispatch(peer.identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization()))).pending());
            }
            var acks=new ArrayList<Decoded>();var observations=new HashSet<MembershipContext.Owned>();
            for(var node:f.request.targets())try(var owner=f.open(node,"capacity-apply")) {
                var applied=owner.applyCurrent(builder().configuration(),node.materialization());acks.add(applied.endorsement().acknowledgement());observations.add(applied.endorsement().owned());
            }
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,maximum,e->{})) {
                owner.publishCurrent(owner.applyCurrent(builder().configuration(),t.materialization()),acks,observations,List.of());
                assertFalse(owner.futureRetentionState().pending());assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
            }
            Files.write(raw.resolve("budget.json"),canonical(Map.of("maximum",(long)maximum,"before",used,"proposal",proposal,"promotion",(long)MembershipPeerRetentionFiles.MAXIMUM,"clear",clear),16384));
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void originalProofAndApplicationCannotBeSubstitutedOnReopen()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-retention/guards-"+UUID.randomUUID()));
        var f=ready(Files.createDirectory(temp.resolve("guards")),raw);var t=f.request.targets().getFirst();var peer=f.request.targets().get(1);
        try {
            MembershipFutureRetentionFiles.State state;
            try(var owner=f.open(t,"original-future")) {
                state=owner.retainFutureDispatch(peer.identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization())));
            }
            f.snapshot("pending-future");int ordinal=0;
            for(String mutation:List.of("checksum","foreign-ack","different-image","missing-image","missing-vote","wrong-candidate")) {
                Files.move(t.replicaDirectory(),temp.resolve("before-mutation-"+ordinal++));V53JournalApplicationTest.copy(raw.resolve("pending-future/node-1"),t.replicaDirectory());
                Path active=t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE);byte[] changed=Files.readAllBytes(active);
                if(mutation.equals("checksum")) {changed[changed.length-1]^=1;Files.write(active,changed);}
                else if(mutation.equals("missing-image"))Files.delete(t.replicaDirectory().resolve("applied-end/application.image"));
                else if(mutation.equals("missing-vote"))Files.write(t.replicaDirectory().resolve(MembershipPendingAccept.FILE),Arrays.copyOf(Files.readAllBytes(t.replicaDirectory().resolve(MembershipPendingAccept.FILE)),MembershipPendingAccept.PREFIX));
                else if(mutation.equals("wrong-candidate"))Files.write(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.NEXT),changed);
                else {
                    var originals=new TreeMap<>(state.originals());var ack=new TreeMap<>(state.record("ack.gsr").value());
                    if(mutation.equals("foreign-ack"))ack.put("incarnation",peer.identity().storageId().toString());
                    else {
                        var catalog=new TreeMap<>(state.record("catalog.gsr").value());catalog.put("application","f".repeat(64));
                        originals.put("catalog.gsr",encode("records","CATALOG",catalog));
                        var statement=new TreeMap<>(state.record("statement.gsr").value());statement.put("applicationAfter","f".repeat(64));statement.put("catalogAfter",hash(originals.get("catalog.gsr")));
                        originals.put("statement.gsr",encode("records","CHECKPOINT",statement));ack.put("statement",hash(originals.get("statement.gsr")));
                    }
                    originals.put("ack.gsr",encode("records","CHECKPOINT_ACK",ack));
                    Files.write(active,MembershipFutureRetentionFiles.encode(state.root,state.owner,state.revision,state.previous,state.parent,state.peers,originals));
                }
                var before=V53ReplayFilesTest.files(t.replicaDirectory());
                assertThrows(Exception.class,()->MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{}),mutation);
                assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()),mutation);assertEquals(0,f.resources.usage().leases());
                V53JournalApplicationTest.copy(t.replicaDirectory(),raw.resolve("rejected-"+mutation));
            }
        }finally{V53NativeApplicationTest.save(f);}
    }
}
