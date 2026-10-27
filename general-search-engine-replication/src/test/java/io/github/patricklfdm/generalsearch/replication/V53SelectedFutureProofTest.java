package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual native originals and pure proposals. Durable handoff is qualified
 * separately by V53SelectedFutureContinuationTest. Legacy guards remain. */
class V53SelectedFutureProofTest {
    @TempDir Path temp;
    record Prepared(V53BootstrapPublicationTest.Fixture fixture,List<MembershipSelection.Source> sources,
                    MembershipSelection.Decision decision,Map<String,byte[]> images) {}
    Prepared prepared(String name)throws Exception {
        return prepared(name,false);
    }
    Prepared prepared(String name,boolean covered)throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-selected-future-proof/"+name+"-"+UUID.randomUUID()));
        System.out.println("v53SelectedFutureProof="+raw.toAbsolutePath());
        var f=V53FutureRetentionSourceTest.pending(Files.createDirectory(temp.resolve(name)),raw);
        var two=f.request.targets().get(1);var three=f.request.targets().getLast();
        try(var owner=f.open(two,"second-future")) {
            owner.retainFutureDispatch(three.identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),two.materialization())));
        }
        f.snapshot("two-futures");
        if(covered) {
            var acknowledgements=new ArrayList<Decoded>();var owned=new HashSet<MembershipContext.Owned>();
            for(var t:f.request.targets())try(var owner=f.open(t,"covered-end")) {
                var end=owner.applyCurrent(builder().configuration(),t.materialization()).endorsement();
                acknowledgements.add(end.acknowledgement());owned.add(end.owned());
            }
            try(var owner=f.open(three,"cover-futures")) {
                owner.publishCurrent(owner.applyCurrent(builder().configuration(),three.materialization()),acknowledgements,owned,List.of());
            }
            f.snapshot("covered-futures");
        }
        try(var owner=f.open(three,"allocate-proposal")){assertEquals(3,owner.reserveCounter());}
        var ballot=Map.<String,Object>of("counter",3L,"proposer","node-3","incarnation",three.identity().storageId().toString());
        var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
        for(var t:f.request.targets())try(var owner=f.open(t,"capture-proposal")) {
            owner.prepareCurrent(ballot);var source=owner.originalSource();sources.add(source);
            for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(t.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
        }
        f.snapshot("proposal-sources");V53NativeApplicationTest.save(f);
        var decision=new MembershipSelection.Campaign(sources.getLast()).select(sources,List.of());
        assertEquals(three.identity(),decision.longest().owner);
        assertNull(MembershipPeerRetentionSource.read(decision.longest()).future());
        return new Prepared(f,List.copyOf(sources),decision,images);
    }
    @Test void proposalRetainsEveryFutureIncludingNonLongestSourcesWithoutClaimingPublication()throws Exception {
        var setup=prepared("proposal");var f=setup.fixture();
        try {
            var expected=new TreeMap<String,byte[]>();
            for(var source:setup.sources()) {
                var captured=MembershipPeerRetentionSource.read(source);
                if(captured.futureBytes()!=null)expected.put(hash(captured.futureBytes()),captured.futureBytes());
            }
            assertEquals(2,expected.size());
            for(var t:List.of(f.request.targets().getFirst(),f.request.targets().getLast()))try(var owner=f.open(t,"proposal")) {
                var before=V53ReplayFilesTest.files(t.replicaDirectory());
                var retention=MembershipSelectedRetention.capture(setup.decision(),t.identity(),Files.readAllBytes(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE)));
                assertEquals(expected.keySet(),retention.futureObjects().keySet());assertEquals(2,retention.futures().size());
                assertEquals(0,retention.completionBytes(),"unpublished targets must not enter the ordinary published endpoint ledger");
                assertEquals(List.of(setup.decision().longest().capsule.terminal()),retention.requiredParents());
                var selected=MembershipGenerationPlan.selected(f.result.root(),t.identity(),"a",owner.promised().orElseThrow(),owner.originalBasis().orElseThrow(),
                        setup.decision(),List.of(),setup.images(),Map.of(),retention);
                selected.verifyOwned(decode(Files.readAllBytes(t.replicaDirectory().resolve("root.gsr")),"records","ROOT"),t.identity(),List.of());
                var materialized=selected.verifiedMaterialization();
                var reread=MembershipSelectedRetention.find(materialized,setup.decision().selected(),t.identity()).orElseThrow();
                assertArrayEquals(retention.bytes(),reread.bytes());assertEquals(expected.keySet(),reread.futureObjects().keySet());
                for(var row:expected.entrySet())assertArrayEquals(row.getValue(),materialized.packet.objectBytes(row.getKey()));
                assertEquals(0L,materialized.context.cut.get("index"));
                assertEquals(setup.decision().carried().entry.digest(),setup.decision().selected().value().get("nextEntry"));
                assertEquals(setup.decision().longest().capsule.packet.images(),materialized.packet.images());
                var copy=retention.futureObjects();copy.values().iterator().next()[0]^=1;
                for(var row:expected.entrySet())assertArrayEquals(row.getValue(),retention.futureObjects().get(row.getKey()));
                Path proposed=Files.createDirectory(f.raw.resolve("proposed-"+t.identity().nodeId().value()));
                for(var file:selected.files.entrySet())Files.write(proposed.resolve(file.getKey()),file.getValue());
                Files.write(proposed.resolve("proposed-selector.gsr"),selected.selector.bytes());
                // A legacy owner without durable imported-proof storage still
                // refuses this source; proposal construction itself is read-only.
                assertEquals("selected future retention propagation required",assertThrows(IllegalArgumentException.class,
                        ()->MembershipPeerRetentionSource.requireSelectable(setup.sources().getFirst())).getMessage());
                assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));
            }
            f.snapshot("after-proposal");
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void alreadyPublishedFutureIsRetainedAsAnAuthenticatedParentWithoutInventingANewTail()throws Exception {
        var setup=prepared("covered",true);var f=setup.fixture();var t=f.request.targets().getLast();
        try(var owner=f.open(t,"covered-proposal")) {
            assertNull(setup.decision().carried());assertNull(setup.decision().selected().value().get("nextEntry"));
            var retention=MembershipSelectedRetention.capture(setup.decision(),t.identity(),Files.readAllBytes(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE)));
            assertEquals(List.of(0L,1L),retention.requiredParents().stream().map(a->number(a.cut().get("index"))).toList());
            assertEquals(2,retention.futureObjects().size());assertTrue(retention.completionBytes()>0);
            var plan=MembershipGenerationPlan.selected(f.result.root(),t.identity(),"b",owner.promised().orElseThrow(),owner.originalBasis().orElseThrow(),
                    setup.decision(),List.of(),setup.images(),Map.of(),retention);
            plan.verifyOwned(decode(Files.readAllBytes(t.replicaDirectory().resolve("root.gsr")),"records","ROOT"),t.identity(),retention.requiredParents());
            assertEquals(1L,plan.verifiedMaterialization().context.cut.get("index"));
            assertArrayEquals(retention.bytes(),MembershipSelectedRetention.find(plan.verifiedMaterialization(),setup.decision().selected(),t.identity()).orElseThrow().bytes());
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void exactSeparateProofOwnerAndEnvelopeAreRequiredOnReadback()throws Exception {
        var setup=prepared("guards");var f=setup.fixture();var t=f.request.targets().getLast();
        try(var owner=f.open(t,"guard")) {
            var one=setup.sources().getFirst();var two=setup.sources().get(1);var frozen=MembershipPeerRetentionSource.read(one);
            byte[] wrapper=MembershipPeerRetentionSource.wrapper(frozen);
            var included=MembershipPeerRetentionSource.included(one.capsule.packet.envelope(),one.basis,one.owner,wrapper,frozen.futureBytes());
            assertArrayEquals(frozen.futureBytes(),included.futureBytes());assertEquals(frozen.future().target(),included.future().target());
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.included(one.capsule.packet.envelope(),one.basis,one.owner,wrapper,null));
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.included(one.capsule.packet.envelope(),one.basis,two.owner,wrapper,frozen.futureBytes()));
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.included(one.capsule.packet.envelope(),one.basis,one.owner,wrapper,MembershipPeerRetentionSource.read(two).futureBytes()));
            var changed=new TreeMap<>(one.basis.value());changed.put("accepted","f".repeat(64));
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.included(one.capsule.packet.envelope(),decode(encode("records","BASIS",changed),"records","BASIS"),one.owner,wrapper,frozen.futureBytes()));
            var retention=MembershipSelectedRetention.capture(setup.decision(),t.identity(),Files.readAllBytes(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE)));
            byte[] before=Files.readAllBytes(t.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
            var wrongTail=new TreeMap<>(setup.decision().selected().value());wrongTail.put("nextEntry","f".repeat(64));
            var substituted=new MembershipSelection.Decision(decode(encode("records","SELECTED",wrongTail),"records","SELECTED"),
                    setup.decision().longest(),setup.decision().carried(),setup.sources());
            assertEquals("selected retention future is not carried entry",assertThrows(IllegalArgumentException.class,
                    ()->MembershipSelectedRetention.capture(substituted,t.identity(),before)).getMessage());
            // Conditional malformed-source fixture only: change a result while
            // preserving the actual selected entry. This must never become an
            // accepted second result or an imported application observation.
            var other=MembershipPeerRetentionSource.read(two);var oldFuture=other.future();var forged=oldFuture.originals();
            var catalog=new TreeMap<>(oldFuture.record("catalog.gsr").value());catalog.put("application","f".repeat(64));
            forged.put("catalog.gsr",encode("records","CATALOG",catalog));
            var statement=new TreeMap<>(oldFuture.record("statement.gsr").value());
            statement.put("catalogAfter",hash(forged.get("catalog.gsr")));statement.put("applicationAfter","f".repeat(64));
            forged.put("statement.gsr",encode("records","CHECKPOINT",statement));
            var acknowledgement=new TreeMap<>(oldFuture.record("ack.gsr").value());acknowledgement.put("statement",hash(forged.get("statement.gsr")));
            forged.put("ack.gsr",encode("records","CHECKPOINT_ACK",acknowledgement));
            byte[] conflicting=MembershipFutureRetentionFiles.encode(oldFuture.root,oldFuture.owner,oldFuture.revision,oldFuture.previous,oldFuture.parent,oldFuture.peers,forged);
            var members=new TreeMap<String,byte[]>();for(String h:two.capsule.packet.objectNames())members.put(h,two.capsule.packet.objectBytes(h));
            members.remove(hash(MembershipPeerRetentionSource.wrapper(other)));members.remove(hash(other.futureBytes()));
            var changedPacket=MembershipPeerRetentionSource.freeze(V53PeerRetentionSourceTest.objects(two.capsule.packet,members),other.promise(),two.owner,other.localBytes(),conflicting);
            var conflictingSource=V53FutureRetentionSourceTest.conditional(two,changedPacket,setup.images());
            var conditionalSources=List.of(one,conflictingSource,setup.sources().getLast());
            var conditional=new MembershipSelection.Campaign(conditionalSources.getLast()).select(conditionalSources,List.of());
            assertEquals("selected retention conflicting future result",assertThrows(IllegalArgumentException.class,
                    ()->MembershipSelectedRetention.capture(conditional,t.identity(),before)).getMessage());
            var plan=MembershipGenerationPlan.selected(f.result.root(),t.identity(),"a",owner.promised().orElseThrow(),owner.originalBasis().orElseThrow(),setup.decision(),List.of(),setup.images(),Map.of(),retention);
            var original=plan.verifiedMaterialization();
            for(String omitted:retention.futureObjects().keySet()) {
                var objects=new TreeMap<String,byte[]>();for(String h:original.packet.objectNames())if(!h.equals(omitted))objects.put(h,original.packet.objectBytes(h));
                var packet=V53PeerRetentionSourceTest.objects(original.packet,objects);var capsule=original.materialization(packet,setup.images(),List.of());
                assertEquals("selected retention future object missing",assertThrows(IllegalArgumentException.class,
                        ()->MembershipSelectedRetention.find(capsule,setup.decision().selected(),t.identity())).getMessage());
            }
            assertTrue(retention.bytes().length<MembershipSelectedRetention.MAXIMUM);
            assertTrue(MembershipSelectedRetention.MAXIMUM<MembershipFormat.FRAME);
            assertTrue(plan.metadata<=MembershipResources.Unit.GENERATION.bytes);
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
}
