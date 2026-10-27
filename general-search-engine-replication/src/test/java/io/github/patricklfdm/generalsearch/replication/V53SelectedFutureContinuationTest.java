package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Complete native handoff regression under development. A source-only or
 * proposal-only pass cannot satisfy this test. No fabricated remote observations. */
class V53SelectedFutureContinuationTest {
    @TempDir Path temp;
    static void install(V53BootstrapPublicationTest.Fixture f,List<MembershipBootstrapTarget<Integer,Doc>> targets,
            List<MembershipSelection.Source> sources,Map<String,byte[]> images)throws Exception {
        for(var t:targets)try(var owner=f.open(t,"future-select")){owner.selectCurrent(sources,List.of());}
        for(var t:targets)try(var owner=f.open(t,"future-install")){owner.installCurrent(sources,List.of(),images);}
    }
    static void carry(V53BootstrapPublicationTest.Fixture f,List<MembershipBootstrapTarget<Integer,Doc>> targets,Map<String,String> obsolete,boolean process)throws Exception {
        var first=targets.getFirst();var old=MembershipPendingAccept.decode(Files.readAllBytes(first.replicaDirectory().resolve("pending.accept")));
        var accepts=new HashSet<MembershipContext.Owned>();
        for(var t:targets)try(var owner=f.open(t,"future-reaccept")){accepts.add(owner.acceptCurrent(old.entry(),old.payload()));}
        V53DistinctMinorityTest.maintain(f,"future-reclaimed",targets,obsolete);
        var vote=MembershipPendingAccept.decode(Files.readAllBytes(first.replicaDirectory().resolve("pending.accept")));
        var fields=new TreeMap<>(vote.accept().value());
        fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",vote.accept(),accepts));
        var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<MembershipContext.Owned>();
        for(var t:targets)try(var owner=f.open(t,"future-reprove")){proofs.add(owner.proveCurrent(proof,accepts));}
        fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"PROOF",proof,proofs));
        var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var owned=new HashSet<>(accepts);owned.addAll(proofs);
        for(var t:targets)try(var owner=f.open(t,"future-recertify")){owner.certifyCurrent(certificate,owned);}
        var acknowledgements=new ArrayList<Decoded>();var ends=new HashSet<MembershipContext.Owned>();
        for(var t:targets)try(var owner=f.open(t,"future-reapply")) {
            var applied=owner.applyCurrent(builder().configuration(),t.materialization());
            acknowledgements.add(applied.endorsement().acknowledgement());ends.add(applied.endorsement().owned());
        }
        if(process) {
            f.snapshot("future-reapplied");
            V53SelectedFutureCrashTest.publicationCuts(f,targets);
        }
        for(var t:targets)try(var owner=f.open(t,"future-republish")) {
            owner.publishCurrent(owner.applyCurrent(builder().configuration(),t.materialization()),acknowledgements,ends,List.of());
            assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            assertFalse(owner.futureRetentionState().pending());
            // Node 1 is offline but remains governing. Imported intentions for
            // nodes 2/3 must survive even though node 1 no longer participates.
            assertEquals(List.of(0L),owner.peerRetentionState().plan().possible(f.request.targets().getFirst().identity()).stream().map(a->number(a.cut().get("index"))).toList());
            for(var peer:targets)assertEquals(List.of(0L,1L),owner.peerRetentionState().plan().possible(peer.identity()).stream().map(a->number(a.cut().get("index"))).toList());
        }
        f.snapshot("future-republished");
    }
    @Test void installedObligationsSurviveAnotherElectionWithoutOriginalHolderAndPublishBeforeCompaction()throws Exception {
        continuation(false);
    }
    void continuation(boolean process)throws Exception {
        var helper=new V53SelectedFutureProofTest();helper.temp=Files.createDirectory(temp.resolve("original"));
        var p=helper.prepared("continuation");var f=p.fixture();var survivors=f.request.targets().subList(1,3);
        try {
            var originals=MembershipSelectedRetention.capture(p.decision(),f.request.targets().getLast().identity(),
                    Files.readAllBytes(f.request.targets().getLast().replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE))).futureObjects();
            assertEquals(2,originals.size());
            install(f,f.request.targets(),p.sources(),p.images());f.snapshot("future-installed");
            // Finish the previous generation's derived cleanup, then transfer the
            // carried vote before a new campaign may reuse its inactive slot.
            var carried=MembershipPendingAccept.decode(Files.readAllBytes(survivors.getFirst().replicaDirectory().resolve("pending.accept")));
            var obsolete=new TreeMap<String,String>();
            for(var t:survivors) {
                var old=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept")));
                obsolete.put(t.identity().nodeId().value(),(String)old.promise().value().get("basisId"));
            }
            for(var t:survivors)try(var owner=f.open(t,"future-retire")) {
                owner.retireSupersededApplication(builder().configuration(),t.materialization());
                owner.acceptCurrent(carried.entry(),carried.payload());
            }
            f.snapshot("future-native-retired");
            V53DistinctMinorityTest.maintain(f,"future-install-maintenance",survivors,obsolete);
            // This second actual campaign omits node 1, the only original holder
            // of one proof. Both surviving owners must expose their inherited
            // obligation through fresh original PROMISE/BASIS, without live input.
            var next=V53DistinctMinorityTest.campaign(f,4,survivors,false);
            var decision=new MembershipSelection.Campaign(next.sources().getLast()).select(next.sources(),List.of());
            for(var source:next.sources()) {
                var frozen=MembershipPeerRetentionSource.read(source);assertNotNull(frozen.projection());
                assertEquals(Set.of("node-1","node-2"),frozen.proofs().stream().map(proof->proof.state().owner.nodeId().value()).collect(java.util.stream.Collectors.toSet()));
                var objects=frozen.objects();var wanted=frozen.proofs().getFirst();
                assertThrows(IllegalArgumentException.class,()->MembershipFutureRetentionSet.decode(frozen.projection(),f.result.root().manifestDigest(),f.request.targets().getFirst().identity(),objects::get));
                assertThrows(IllegalArgumentException.class,()->MembershipFutureRetentionSet.decode(frozen.projection(),f.result.root().manifestDigest(),source.owner,h->h.equals(hash(wanted.bytes()))?null:objects.get(h)));
                byte[] altered=wanted.bytes();altered[altered.length-1]^=1;
                assertThrows(IllegalArgumentException.class,()->MembershipFutureRetentionSet.decode(frozen.projection(),f.result.root().manifestDigest(),source.owner,h->h.equals(hash(wanted.bytes()))?altered:objects.get(h)));
                assertArrayEquals(originals.get(hash(wanted.bytes())),wanted.bytes());
            }
            for(var t:survivors)try(var owner=f.open(t,"verify-inherited-source")) {
                var intent=MembershipSelectedRetention.capture(decision,t.identity(),Files.readAllBytes(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE)));
                assertEquals(originals.keySet(),intent.futureObjects().keySet());
                for(var row:originals.entrySet())assertArrayEquals(row.getValue(),intent.futureObjects().get(row.getKey()));
                owner.installCurrent(next.sources(),List.of(),next.images());
            }
            f.snapshot("future-reinstalled");carry(f,survivors,next.obsolete(),process);
            var copies=new ArrayList<MembershipFloor.Copy>();
            for(var t:survivors)try(var owner=f.open(t,"observe-copy")){copies.add(owner.floorCopyCurrent());}
            for(var t:survivors)try(var owner=f.open(t,"narrow-observed")){for(var copy:copies)owner.retainPeerObservation(copy);}
            V53DistinctMinorityTest.maintain(f,"future-published-maintenance",survivors,Map.of());
            V53DistinctMinorityTest.campaign(f,5,survivors);
            for(var t:survivors)try(var owner=f.open(t,"next-source")) {
                assertTrue(MembershipPeerRetentionSource.read(owner.originalSource()).proofs().isEmpty());
                for(var peer:survivors)assertEquals(List.of(1L),owner.peerRetentionState().plan().possible(peer.identity()).stream().map(a->number(a.cut().get("index"))).toList());
                assertEquals(1L,V53NativeRetirementTest.publishedIndex(t.replicaDirectory()));
                assertEquals(List.of(0L),owner.peerRetentionState().plan().possible(f.request.targets().getFirst().identity()).stream().map(a->number(a.cut().get("index"))).toList());
            }
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void aSelectedCoveredTargetPromotesBeforeExposingTheOwner()throws Exception {
        var helper=new V53SelectedFutureProofTest();helper.temp=Files.createDirectory(temp.resolve("covered"));
        var p=helper.prepared("covered-continuation",true);var f=p.fixture();var t=f.request.targets().get(1);
        try {
            // Node 3 already published; lagging node 2 imports that covered
            // prefix and both original obligations. Its inactive slot is free.
            try(var owner=f.open(t,"covered-select-install")) {
                owner.selectCurrent(p.sources(),List.of());
                owner.retireCoveredApplication(builder().configuration(),t.materialization(),p.sources(),List.of(),List.of(),p.images(),List.of());
                owner.installCurrent(p.sources(),List.of(),p.images());
                for(var peer:f.request.targets().subList(1,3))assertEquals(List.of(0L,1L),owner.peerRetentionState().plan().possible(peer.identity()).stream().map(a->number(a.cut().get("index"))).toList());
            }
            try(var owner=f.open(t,"covered-reopen")) {
                for(var peer:f.request.targets().subList(1,3))assertEquals(2,owner.peerRetentionState().plan().possible(peer.identity()).size());
            }
            f.snapshot("covered-promoted");
        }finally{V53NativeApplicationTest.save(f);}
    }

    @Test void importedCompletionReservationRefusesOneByteShortBeforeSelection()throws Exception {
        var helper=new V53SelectedFutureProofTest();helper.temp=Files.createDirectory(temp.resolve("budget"));
        var p=helper.prepared("completion-budget");var f=p.fixture();var t=f.request.targets().getLast();
        try {
            long used=Files.size(t.replicaDirectory().resolve(MembershipGrantJournal.FILE))
                    +Files.size(t.replicaDirectory().resolve(MembershipPendingAccept.FILE))+MembershipPendingAccept.PREFIX
                    +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA
                    +Files.size(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE))
                    +Files.size(t.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE));
            int maximum=Math.toIntExact(used+p.decision().selected().bytes().length+MembershipPeerRetentionFiles.MAXIMUM);
            var before=V53ReplayFilesTest.files(t.replicaDirectory());
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,maximum-1,event->{})) {
                assertEquals("selected retention completion journal capacity",assertThrows(IllegalArgumentException.class,
                        ()->owner.selectCurrent(p.sources(),List.of())).getMessage());
            }
            assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,maximum,event->{})) {
                owner.selectCurrent(p.sources(),List.of());owner.installCurrent(p.sources(),List.of(),p.images());
            }
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),f.resources,maximum,event->{})) {
                assertEquals(0,owner.peerRetentionState().revision());assertFalse(owner.futureRetentionState().pending());
                var selector=decode(Files.readAllBytes(t.replicaDirectory().resolve("selector.gsr")),"records","SELECTOR");
                var packet=MembershipSourcePacket.decode(Files.readAllBytes(t.replicaDirectory().resolve("generations/"+selector.value().get("generation")+"/source.gscp")));
                for(var source:p.sources())for(var proof:MembershipPeerRetentionSource.read(source).proofs())
                    assertArrayEquals(proof.bytes(),packet.objectBytes(hash(proof.bytes())));
            }
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }

    @Test void coveringInstallRecoversWithoutLosingTheOriginalFutureAfterDerivedDeletion()throws Exception {
        var helper=new V53SelectedFutureProofTest();helper.temp=Files.createDirectory(temp.resolve("covered-cuts"));
        var p=helper.prepared("covered-cuts",true);var f=p.fixture();var t=f.request.targets().get(1);
        try {
            try(var owner=f.open(t,"covered-cut-select")){owner.selectCurrent(p.sources(),List.of());}
            f.snapshot("covered-selected");int ordinal=0;
            for(String point:List.of("SUPERSEDED_END_FILE_DELETED","SUPERSEDED_END_RETIREMENT_DELETED",
                    "INSTALL_SELECTOR_FORCED","RETENTION_PREFIX_WRITTEN","FUTURE_RETENTION_PREFIX_WRITTEN")) {
                Files.move(t.replicaDirectory(),temp.resolve("covered-replaced-"+ordinal++));
                V53JournalApplicationTest.copy(f.raw.resolve("covered-selected/node-2"),t.replicaDirectory());
                var hit=new boolean[1];
                f.observer=(target,op,event)->{if(event.equals(point)){hit[0]=true;throw new java.io.IOException("injected covered cut: "+point);}};
                try {
                    assertThrows(java.io.IOException.class,()->{
                        try(var owner=f.open(t,"covered-cut")) {
                            owner.retireCoveredApplication(builder().configuration(),t.materialization(),p.sources(),List.of(),List.of(),p.images(),List.of());
                            owner.installCurrent(p.sources(),List.of(),p.images());
                        }
                    });
                    assertTrue(hit[0],point);
                }finally{f.observer=(target,op,event)->{};}
                f.snapshot("covered-interrupted-"+point);
                try(var owner=f.open(t,"covered-cut-resume")) {
                    if(V53NativeRetirementTest.publishedIndex(t.replicaDirectory())==0) {
                        // The old selector can still be active after all staging
                        // was retired and the replacement selector was forced.
                        // Resume that exact installation; a pending selector must
                        // not authorize a second, unrelated retirement transaction.
                        if(Files.exists(t.replicaDirectory().resolve(MembershipAppliedEndFiles.DIRECTORY))
                                || Files.exists(t.replicaDirectory().resolve(MembershipReplayFiles.DIRECTORY)))
                            owner.retireCoveredApplication(builder().configuration(),t.materialization(),p.sources(),List.of(),List.of(),p.images(),List.of());
                        owner.installCurrent(p.sources(),List.of(),p.images());
                    }
                    assertFalse(owner.futureRetentionState().pending());
                    for(var peer:f.request.targets().subList(1,3))assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                    assertEquals(1,V53NativeRetirementTest.publishedIndex(t.replicaDirectory()));
                }
                f.snapshot("covered-resumed-"+point);assertEquals(0,f.resources.usage().leases());
            }
        }finally{V53NativeApplicationTest.save(f);}
    }

}
