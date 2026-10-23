package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

class V53SelectedSourcesTest {
    @TempDir Path temp;
    @Test void originalFramesBindEverySelectedSourceAcrossAllProfilesAndViews() {
        for(Object[] p:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}})
            for(int at:List.of(0,5,6,7)) {
                var f=new V53PublishedGenerationTest.Fixture((int)p[0],(String)p[1],at);byte[] bytes=MembershipSelectedSources.encodeSources(f.decision);
                var out=new java.io.ByteArrayOutputStream();f.decision.sources().forEach(s->out.writeBytes(s.basis.bytes()));assertArrayEquals(out.toByteArray(),bytes);
                assertEquals(f.decision.sources().size(),MembershipSelectedSources.cuts(bytes,f.selected).size());
                assertEquals(List.of(f.checkpoint.originalParent()),MembershipSelectedSources.parents(bytes,f.selected,f.f.capsule.verify(),new byte[0]));
                assertArrayEquals(bytes,f.plan().files.get(MembershipSelectedSources.FILE));
                assertTrue(bytes.length<=MembershipSelectedSources.MAXIMUM);
            }
    }
    @Test void missingChangedReorderedDuplicatedOrUnboundFramesNeverBecomeSelectedAuthority() {
        var f=new V53PublishedGenerationTest.Fixture(3,"REPLACE",1);byte[] bytes=MembershipSelectedSources.encodeSources(f.decision);
        for(byte[] bad:List.of(new byte[0],Arrays.copyOf(bytes,bytes.length-1),Arrays.copyOf(bytes,bytes.length+1),new byte[MembershipSelectedSources.MAXIMUM+1]))
            assertThrows(RuntimeException.class,()->MembershipSelectedSources.cuts(bad,f.selected));
        var parts=f.decision.sources().stream().map(s->s.basis.bytes()).toList();
        var reversed=new java.io.ByteArrayOutputStream();for(int i=parts.size()-1;i>=0;i--)reversed.writeBytes(parts.get(i));
        assertThrows(IllegalArgumentException.class,()->MembershipSelectedSources.cuts(reversed.toByteArray(),f.selected));
        var duplicate=new java.io.ByteArrayOutputStream();for(int i=0;i<parts.size();i++)duplicate.writeBytes(parts.getFirst());
        assertThrows(IllegalArgumentException.class,()->MembershipSelectedSources.cuts(duplicate.toByteArray(),f.selected));
        var changed=bytes.clone();changed[changed.length-1]^=1;assertThrows(RuntimeException.class,()->MembershipSelectedSources.cuts(changed,f.selected));
        var missing=V53CheckpointPlanTest.finish(f.checkpoint);
        assertThrows(IllegalArgumentException.class,()->MembershipSelectedSources.parents(bytes,f.selected,missing,new byte[0]));
    }
    @Test void actualSelectedSetPinsAllRemoteEndpointsRatherThanOnlyTheLocalBasis()throws Exception {
        var f=new V53AncestorCheckpointTest.Fixture(temp,true);byte[] common=null;
        for(int n:List.of(1,2,3)) {
            Path gen=f.node(n).resolve("generations/b");byte[] bytes=Files.readAllBytes(gen.resolve(MembershipSelectedSources.FILE));
            var selected=decode(Files.readAllBytes(gen.resolve("selected.gsr")),"records","SELECTED");
            assertEquals(List.of(1L,2L,4L),MembershipSelectedSources.cuts(bytes,selected).stream().map(c->number(c.get("index"))).toList());
            if(common==null)common=bytes;else assertArrayEquals(common,bytes);
            assertEquals(List.of(1L,2L),f.applied.get(n).plan().additionalParents().stream().map(a->number(a.cut().get("index"))).toList());
            try(var store=f.open(n,e->{})){f.publish(store,n);assertArrayEquals(bytes,Files.readAllBytes(f.node(n).resolve("generations/a").resolve(MembershipSelectedSources.FILE)));}
        }
        for(int n:List.of(1,2,3))try(var store=f.open(n,e->{})){assertEquals(5L,store.floorCopyCurrent().capsule.context.cut.get("index"));}
    }
    @Test void unusedAncestryIsOmittedOnlyFromNextGenerationAndOriginalFramesRemainExact()throws Exception {
        var f=new V53PublicationAdmissionTest.Fixture(temp,6,true);var cohort=V53PublicationAdmissionTest.certify(f,false);
        var applied=new TreeMap<Integer,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
        var parents=new ArrayList<MembershipAppliedEndFiles.ParentEndorsement>();
        for(int n:f.f.nodes)try(var store=f.open(n,new ArrayList<>())) {
            var result=store.applyCurrent(f.application.configuration(),f.application.storage(),cohort.owned());applied.put(n,result);
            assertTrue(result.plan().additionalParents().isEmpty());acks.add(result.endorsement().acknowledgement());owned.add(result.endorsement().owned());parents.add(result.endorsement().parent().orElseThrow());
        }
        var extra=new HashSet<Owned>();parents.forEach(p->extra.add(p.owned()));
        var bridge=new MembershipSelection.Bridge(parents.getFirst().statement(),parents.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),extra);
        f.f.f.fixture.owned.addAll(cohort.owned());f.f.f.fixture.owned.addAll(owned);f.f.f.fixture.owned.addAll(extra);
        for(int n:f.f.nodes) {
            Path node=f.f.node(temp,n),old=node.resolve("generations/b");var before=V53ReplayFilesTest.files(node);
            byte[] original=Files.readAllBytes(old.resolve(MembershipSelectedSources.FILE)),ancestry=Files.readAllBytes(old.resolve("ancestry.gsr"));
            try(var store=f.open(n,new ArrayList<>())) {
                assertThrows(IllegalArgumentException.class,()->store.publishCurrent(applied.get(n),acks,owned,List.of()));
                store.publishCurrent(applied.get(n),acks,owned,List.of(bridge));assertEquals(9L,store.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            V53JournalPublicationTest.preserved(node,before);assertArrayEquals(ancestry,Files.readAllBytes(old.resolve("ancestry.gsr")));
            assertArrayEquals(original,Files.readAllBytes(node.resolve("generations/a").resolve(MembershipSelectedSources.FILE)));
            assertArrayEquals(MembershipGenerationPlan.ancestry(List.of(bridge)),Files.readAllBytes(node.resolve("generations/a/ancestry.gsr")));
            try(var store=f.open(n,new ArrayList<>())){assertEquals(9L,store.floorCopyCurrent().capsule.context.cut.get("index"));}
        }
    }
    @Test void sourceMemberWriteAndForceRecoverWithoutRewritingOriginalSelection()throws Exception {
        var f=new V53PublishedGenerationTest.Fixture(3,"ADD",1);
        for(String point:List.of("INSTALL_MEMBER_WRITTEN","INSTALL_MEMBER_FORCED")) {
            Path path=temp.resolve(point);f.provision(path);var before=V53ReplayFilesTest.files(path);
            assertThrows(java.io.IOException.class,()->f.install(path,e->{
                if(e.equals(point) && Files.exists(path.resolve("generations/b").resolve(MembershipSelectedSources.FILE)))throw new java.io.IOException("exact selected sources cut");
            }));
            assertTrue(Files.exists(path.resolve("generations/b").resolve(MembershipSelectedSources.FILE)));
            assertFalse(Files.exists(path.resolve("generations/b/selected.gsr")));
            assertEquals("a",V53PublishedGenerationTest.read(path,"selector.gsr","SELECTOR").value().get("generation"));
            f.install(path,e->{});f.install(path,e->{});
            for(var row:before.entrySet())if(!row.getKey().equals("selector.gsr"))assertEquals(row.getValue(),hash(Files.readAllBytes(path.resolve(row.getKey()))));
        }
    }
    @Test void missingOrChangedInstalledOriginalsRejectBeforeAnyReopenForce()throws Exception {
        var f=new V53PublishedGenerationTest.Fixture(3,"ADD",1);
        for(String mode:List.of("missing","changed","linked")) {
            Path path=temp.resolve(mode);f.provision(path);f.install(path,e->{});
            Path member=path.resolve("generations/b").resolve(MembershipSelectedSources.FILE);
            if(mode.equals("missing"))Files.delete(member);
            else if(mode.equals("linked")){Files.delete(member);Files.createSymbolicLink(member,path.resolve("generations/a").resolve(MembershipSelectedSources.FILE));}
            else {var raw=Files.readAllBytes(member);raw[raw.length-1]^=1;Files.write(member,raw);}
            var events=new ArrayList<String>();var resources=new MembershipResources(512*MembershipResources.MIB);
            assertThrows(Exception.class,()->{
                try(var current=new MembershipCurrentGeneration(path,f.root(),V53DeclarationsTest.node(1),resources,List.of(f.promise),List.of(f.basis),List.of(f.selected),f::verify,events::add,true)) {fail("invalid source opened");}
            });
            assertTrue(events.isEmpty());assertEquals(0,resources.usage().leases());
        }
    }
    @Test void floorRechecksFullOriginalFramesEvenWhenManifestHashAndForceObservationMatch() {
        var f=new V53PublishedGenerationTest.Fixture(3,"ADD",1);var plan=f.plan();var files=new TreeMap<>(plan.files);
        byte[] sources=files.get(MembershipSelectedSources.FILE).clone();sources[sources.length-1]^=1;files.put(MembershipSelectedSources.FILE,sources);
        var fields=new TreeMap<>(plan.manifest.value());var rows=new ArrayList<Map<String,Object>>();
        for(Object item:list(fields.get("files"))) {
            var row=new TreeMap<>(object(item));if(row.get("path").equals(MembershipSelectedSources.FILE))row.put("sha256",hash(sources));rows.add(row);
        }
        fields.put("files",rows);var manifest=decode(encode("records","GENERATION",fields),"records","GENERATION");files.put("generation.gsr",manifest.bytes());
        var owner=V53DeclarationsTest.node(1);var capsule=f.capsule();
        var observation=new Owned(owner.nodeId().value(),owner.storageId(),manifest.digest(),cutDigest(capsule.context.cut));
        assertThrows(RuntimeException.class,()->MembershipFloor.Copy.verify(manifest,capsule,owner,Set.of(observation),files));
    }

    @Test void stagedReplayPinsSourceAndFloorMaintenanceUntilExactPublication()throws Exception {stagedMaintenance("REPLAY_CLAIM_FORCED");}
    @Test void forcedEndPinsSourceAndFloorMaintenanceUntilExactPublication()throws Exception {stagedMaintenance("APPLY_BEFORE_RETURN");}
    private void stagedMaintenance(String point)throws Exception {
        var f=new V53AncestorCheckpointTest.Fixture(temp,false);var copies=new ArrayList<MembershipFloor.Copy>();
        for(int n:List.of(1,2))try(var store=f.open(n,e->{})){copies.add(store.floorCopyCurrent());}
        try(var store=f.open(1,e->{if(e.equals(point))throw new java.io.IOException(point);})) {
            assertThrows(java.io.IOException.class,()->f.application.apply(store));
        }
        var events=new ArrayList<String>();
        try(var store=f.open(1,events::add)) {
            var before=V53ReplayFilesTest.files(f.node(1));events.clear();
            String source=(String)store.originalSource().basis.value().get("basisId");events.clear();
            for(org.junit.jupiter.api.function.Executable action:List.<org.junit.jupiter.api.function.Executable>of(store::releaseFloor,()->store.establishFloor(copies),()->store.retireSource(source))) {
                var error=assertThrows(IllegalArgumentException.class,action);assertEquals("staged application pins original source/floor references",error.getMessage());
                assertTrue(events.isEmpty());assertEquals(before,V53ReplayFilesTest.files(f.node(1)));
            }
            f.applied.put(1,f.application.apply(store));f.publish(store,1);assertEquals(5L,store.floorCopyCurrent().capsule.context.cut.get("index"));
            for(int n:List.of(2,3))try(var peer=f.open(n,e->{})){f.publish(peer,n);}
            var completed=new ArrayList<MembershipFloor.Copy>();completed.add(store.floorCopyCurrent());
            try(var peer=f.open(2,e->{})){completed.add(peer.floorCopyCurrent());}
            store.establishFloor(completed);store.retireInactive();store.releaseFloor();assertTrue(store.governingFloor().isEmpty());
        }
    }

    @Test void publicationImageHeadroomRejectsBeforeNewVoteAndFloorReleaseAllowsAdmission()throws Exception {
        var f=new V53PublicationAdmissionTest.Fixture(temp,0,true);var copies=new ArrayList<MembershipFloor.Copy>();
        for(int n:List.of(1,2))try(var store=f.open(n,new ArrayList<>())){copies.add(store.floorCopyCurrent());}
        var resources=f.f.resources();var events=new ArrayList<String>();
        try(var store=MembershipGrantJournal.openApplying(f.node(),f.f.f.root(),V53DeclarationsTest.node(1),resources,f.f.f::verify,events::add)) {
            store.establishFloor(copies);var before=V53ReplayFilesTest.files(f.node());events.clear();
            assertThrows(IllegalArgumentException.class,()->store.acceptCurrent(f.f.entry(),f.f.payload()));
            assertTrue(events.isEmpty());assertTrue(store.currentOwnedTail().isEmpty());assertEquals(before,V53ReplayFilesTest.files(f.node()));
            store.releaseFloor();assertNotNull(store.acceptCurrent(f.f.entry(),f.f.payload()));
            assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void existingImageReservationGrowsAtomicallyWithoutDoubleCountingOrExceedingStaging() {
        var resources=new MembershipResources(64*MembershipResources.MIB);
        var first=resources.reserve(MembershipResources.Unit.APPLICATION,"first",32*MembershipResources.MIB);
        var second=resources.reserve(MembershipResources.Unit.APPLICATION,"second",32*MembershipResources.MIB);
        var full=resources.usage();assertThrows(IllegalArgumentException.class,first::reserveApplicationMaximum);assertEquals(full,resources.usage());
        second.close();first.reserveApplicationMaximum();first.reserveApplicationMaximum();
        assertEquals(1,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));assertEquals(64*MembershipResources.MIB,resources.usage().staging());
        first.close();first.close();assertEquals(0,resources.usage().staging());assertThrows(IllegalArgumentException.class,first::reserveApplicationMaximum);
        try(var source=resources.reserve(MembershipResources.Unit.SOURCE,"source",1)) {
            var before=resources.usage();assertThrows(IllegalArgumentException.class,source::reserveApplicationMaximum);assertEquals(before,resources.usage());
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void interruptedCandidateReusesItsImageReservationUnderTheSevenImageLimit()throws Exception {
        var f=new V53JournalPublicationTest.Fixture(temp,0);var resources=f.resources();
        var unrelated=resources.reserve(MembershipResources.Unit.APPLICATION,"unrelated",1);
        try {
            try(var store=f.open(1,resources,e->{if(e.equals("INSTALL_IMAGE_WRITTEN"))throw new java.io.IOException("image cut");})) {
                assertEquals(7,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                assertThrows(java.io.IOException.class,()->f.publish(store,1));
            }
            assertEquals(1,resources.usage().leases());
            try(var store=f.open(1,resources,e->{})) {
                assertEquals(7,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                f.publish(store,1);assertEquals(1L,store.floorCopyCurrent().capsule.context.cut.get("index"));
                assertTrue(store.currentCertificate().isEmpty());
            }
            assertEquals(1,resources.usage().leases());
        }finally{unrelated.close();}
        assertEquals(0,resources.usage().leases());
    }

}
