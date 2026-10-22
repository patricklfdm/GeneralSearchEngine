package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Planning checks exact physical inputs but does not delete any authority. */
class V53SourceRetirementPlanTest {
    @TempDir Path temp;
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,V53CurrentGenerationFixture f)throws Exception {
        return MembershipGrantJournal.openMaintenance(path,f.root(),V53DeclarationsTest.node(1),resources(),f::verify,e->{});
    }
    void floor(MembershipGrantJournal store,Path peers,V53CurrentGenerationFixture f)throws Exception {
        Files.createDirectory(peers);var copies=new ArrayList<MembershipFloor.Copy>();copies.add(store.floorCopyCurrent());
        for(int node=2;node<=f.size/2+1;node++)copies.add(new V53FloorTest().copy(peers.resolve("node-"+node),f.size,
                Math.toIntExact(number(f.admitted.context.cut.get("index"))),node));
        store.establishFloor(copies);
    }
    String basis(MembershipGrantJournal store,V53CurrentGenerationFixture f,int ballot)throws Exception {
        return (String)store.prepareCurrent(f.fixture.source.ballot(ballot)).value().get("basisId");
    }
    Map<String,String> inventory(Path path)throws Exception {
        var result=new TreeMap<String,String>();try(var all=Files.walk(path)){for(Path p:all.filter(Files::isRegularFile).toList())result.put(path.relativize(p).toString(),hash(Files.readAllBytes(p)));}return result;
    }
    @Test void exactPlanPreservesAllFilesAcrossSizesAndGoverningViews()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7)) {
            var f=new V53CurrentGenerationFixture(size,through,false);Path dir=temp.resolve(size+"-"+through);Files.createDirectory(dir);Path path=dir.resolve("authority");f.provision(path);
            try(var store=open(path,f)) {
                floor(store,dir.resolve("peers"),f);String old=basis(store,f,20);basis(store,f,21);var before=inventory(path);
                var plan=store.planSourceRetirement(old);assertEquals(before,inventory(path));assertEquals(old,plan.basisId);
                var expected=new TreeSet<String>();try(var all=Files.list(path.resolve("sources").resolve(old))){all.forEach(p->expected.add("sources/"+old+"/"+p.getFileName()));}
                var actual=new TreeSet<String>();for(Object row:list(plan.record.value().get("files"))){var item=object(row);String name=(String)item.get("path");actual.add(name);assertEquals(Files.size(path.resolve(name)),number(item.get("size")));assertEquals(before.get(name),item.get("sha256"));}
                assertEquals(expected,actual);assertEquals(store.governingFloor().orElseThrow().digest(),plan.record.value().get("floor"));
                assertEquals(hash(Files.readAllBytes(path.resolve("selector.gsr"))),plan.record.value().get("selector"));
                assertArrayEquals(plan.record.bytes(),store.planSourceRetirement(old).record.bytes());
            }
        }
    }
    @Test void journalCandidateRemovesOnlyTheObsoleteOriginalGroupWithoutWriting()throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,false);Path path=temp.resolve("journal");f.provision(path);
        try(var store=open(path,f)) {
            floor(store,temp.resolve("peers"),f);String old=basis(store,f,20),latest=basis(store,f,21);
            var plan=store.planSourceRetirement(old);byte[] bytes=Files.readAllBytes(path.resolve("grants.gsr"));var before=inventory(path);
            String current=decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value().get("promise").toString();
            byte[] candidate=MembershipJournalRotation.excludingSource(bytes,Set.of(current),Set.of(old,latest),plan);
            assertEquals(bytes.length-plan.promise.bytes().length-plan.basis.bytes().length,candidate.length);
            assertArrayEquals(candidate,MembershipJournalRotation.compact(candidate,Set.of(current),Set.of(latest)));
            assertEquals(before,inventory(path));assertArrayEquals(bytes,Files.readAllBytes(path.resolve("grants.gsr")));
            assertEquals("source rotation protected or absent source",assertThrows(IllegalArgumentException.class,
                    ()->MembershipJournalRotation.excludingSource(bytes,Set.of(current,plan.promise.digest()),Set.of(old,latest),plan)).getMessage());
            assertThrows(IllegalArgumentException.class,()->MembershipJournalRotation.excludingSource(candidate,Set.of(current),Set.of(latest),plan));
        }
    }
    @Test void newestGrantAndMissingBasisCannotRetire()throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,false);Path path=temp.resolve("newest");f.provision(path);
        try(var store=open(path,f)) {
            floor(store,temp.resolve("peers"),f);String id=basis(store,f,20);
            assertEquals("source retirement needs a newer durable promise",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
            assertEquals("source retirement requires complete original basis",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(UUID.randomUUID().toString())).getMessage());
        }
    }
    @Test void currentInstalledBasisRemainsProtectedAfterHigherGrant()throws Exception {
        Path path=temp.resolve("current/authority");Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,0);var f=new V53CurrentGenerationFixture(3,0,false);
        try(var store=open(path,f)) {
            String id=(String)store.originalBasis().orElseThrow().value().get("basisId");store.retireInactive();basis(store,f,101);
            assertEquals("source retirement current generation reference",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
        }
    }
    @Test void aCompleteGoverningFloorIsRequiredAndReleaseRevokesPlanning()throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,false);Path path=temp.resolve("floor");f.provision(path);
        try(var store=open(path,f)) {
            String id=basis(store,f,20);basis(store,f,21);
            assertEquals("durable governing floor required before source retirement",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
            floor(store,temp.resolve("peers"),f);store.planSourceRetirement(id);store.releaseFloor();
            assertEquals("durable governing floor required before source retirement",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
        }
    }
    @Test void exactUnresolvedAcceptedBytesRemainOwnedInCurrent()throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,true);Path path=temp.resolve("tail");f.provision(path);
        try(var store=open(path,f)) {
            floor(store,temp.resolve("peers"),f);String id=basis(store,f,20);basis(store,f,21);
            var plan=store.planSourceRetirement(id);assertEquals(f.accepted,plan.basis.value().get("accepted"));
            assertEquals(f.accepted,store.currentOwnedTail().orElseThrow().record());
        }
    }
    @Test void retainedSourceTamperingIsNotHiddenByMatchingDigestReferences()throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,false);Path path=temp.resolve("changed");f.provision(path);
        try(var store=open(path,f)) {
            floor(store,temp.resolve("peers"),f);String id=basis(store,f,20);basis(store,f,21);
            Path image;try(var all=Files.list(path.resolve("sources").resolve(id))){image=all.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}
            byte[] bytes=Files.readAllBytes(image);bytes[0]^=1;Files.write(image,bytes);var before=inventory(path);
            assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id));assertEquals(before,inventory(path));
        }
    }
    @Test void inactiveGenerationCannotBeSkippedBySourcePlanning()throws Exception {
        Path path=temp.resolve("inactive/authority");Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,0);var f=new V53CurrentGenerationFixture(3,0,false);
        try(var store=open(path,f)) {
            String id=(String)store.originalBasis().orElseThrow().value().get("basisId");
            assertEquals("inactive generation must retire before source planning",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
        }
    }
    MembershipCurrentGeneration current(Path path,V53CurrentGenerationFixture f)throws Exception {
        var promise=decode(Files.readAllBytes(path.resolve("generations/a/promise.gsr")),"records","PROMISE");
        return new MembershipCurrentGeneration(path,f.root(),V53DeclarationsTest.node(1),resources(),List.of(promise),List.of(),f::verify,e->{});
    }
    @Test void floorLocalReferenceRemainsProtectedEvenWhenCurrentDoesNotReferenceIt()throws Exception {
        Path path=temp.resolve("reference/authority");Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,0);
        var f=new V53CurrentGenerationFixture(3,0,false);Path alternate=temp.resolve("alternate");f.provision(alternate);
        try(var store=open(path,f);var current=current(alternate,f)) {
            store.retireInactive();var basis=store.originalBasis().orElseThrow();var promise=store.promised().orElseThrow();var source=store.originalSource();
            var own=store.floorCopyCurrent();var peer=new V53FloorTest().copy(temp.resolve("peer"),3,0,2);var copies=List.of(own,peer);
            var retained=new MembershipFloorFiles.Retained(MembershipFloor.create(f.root(),own,copies),copies);basis(store,f,101);
            assertEquals("source retirement governing floor reference",assertThrows(IllegalArgumentException.class,()->MembershipSourceRetirementPlan.create(
                    f.root(),V53DeclarationsTest.node(1),current,retained,store.promised().orElseThrow(),promise,basis,source.capsule,f.fixture.source.images)).getMessage());
        }
    }
    @Test void missingAboveFloorBytesOrLostOwnershipRejectThePlan()throws Exception {
        for(boolean keepBytes:List.of(false,true)) {
            Path dir=temp.resolve("lost-"+keepBytes);Files.createDirectory(dir);Path path=dir.resolve("authority");
            var f=new V53CurrentGenerationFixture(3,0,true);f.provision(path);
            var other=new V53CurrentGenerationFixture(3,0,keepBytes);Path alternate=dir.resolve("alternate");other.provision(alternate);
            if(keepBytes) {
                Path generation=alternate.resolve("generations/a");var value=new TreeMap<>(decode(Files.readAllBytes(generation.resolve("generation.gsr")),"records","GENERATION").value());
                value.put("ownedTail",null);value.put("files",list(value.get("files")).stream().filter(row->!object(row).get("path").equals("owned-tail.gsr")).toList());
                byte[] manifest=encode("records","GENERATION",value);Files.write(generation.resolve("generation.gsr"),manifest);Files.delete(generation.resolve("owned-tail.gsr"));
                var selector=new TreeMap<>(decode(Files.readAllBytes(alternate.resolve("selector.gsr")),"records","SELECTOR").value());selector.put("digest",hash(manifest));Files.write(alternate.resolve("selector.gsr"),encode("records","SELECTOR",selector));
            }
            try(var store=open(path,f);var current=current(alternate,other)) {
                var own=store.floorCopyCurrent();var peer=new V53FloorTest().copy(dir.resolve("peer"),3,0,2);var copies=List.of(own,peer);
                var retained=new MembershipFloorFiles.Retained(store.establishFloor(copies),copies);basis(store,f,20);
                var old=store.originalBasis().orElseThrow();var promise=store.promised().orElseThrow();var source=store.originalSource();basis(store,f,21);
                var error=assertThrows(IllegalArgumentException.class,()->MembershipSourceRetirementPlan.create(f.root(),V53DeclarationsTest.node(1),current,
                        retained,store.promised().orElseThrow(),promise,old,source.capsule,f.fixture.source.images));
                assertEquals(keepBytes?"source retirement loses unresolved ownership":"missing packet object",error.getMessage());
            }
        }
    }

    @Test void obsoleteSelectedGroupLeavesNoOrphanAndCannotPruneHighest()throws Exception {
        var f=new V53CurrentGenerationFixture(3,0,false);Path path=temp.resolve("selected");f.provision(path);
        try(var store=open(path,f)) {
            floor(store,temp.resolve("peers"),f);String old=basis(store,f,20);
            var offered=new V53GenerationInstallFixture(3,0,0,false).offers(store,20);
            var selected=store.selectCurrent(offered,List.of());byte[] beforeHigher=Files.readAllBytes(path.resolve("grants.gsr"));String latest=basis(store,f,21);
            var plan=store.planSourceRetirement(old);byte[] bytes=Files.readAllBytes(path.resolve("grants.gsr"));
            String current=decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value().get("promise").toString();
            byte[] candidate=MembershipJournalRotation.excludingSource(bytes,Set.of(current),Set.of(old,latest),plan);
            assertEquals(bytes.length-plan.promise.bytes().length-plan.basis.bytes().length-selected.bytes().length,candidate.length);
            assertArrayEquals(candidate,MembershipJournalRotation.compact(candidate,Set.of(current),Set.of(latest)));
            assertEquals("source rotation cannot drop highest grant",assertThrows(IllegalArgumentException.class,
                    ()->MembershipJournalRotation.excludingSource(beforeHigher,Set.of(current),Set.of(old),plan)).getMessage());
        }
    }

}
