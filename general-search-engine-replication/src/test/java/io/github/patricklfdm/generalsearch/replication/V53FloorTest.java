package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Governing-copy admission from locally forced generations, not a deletion transaction. */
class V53FloorTest {
    @TempDir Path temp;
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipFloor.Copy copy(Path path,int size,int through,int node) throws Exception {
        var f=new V53CurrentGenerationFixture(size,through,false);f.provision(path);String name="node-"+node;
        Files.write(path.resolve("node.gsr"),encode("records","NODE",Map.of("identity",V53ContextFixture.member(node),"root",f.root().manifestDigest())));
        Files.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",Map.of("counter",0L,"node",name,"root",f.root().manifestDigest())));
        var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value());manifest.put("node",name);
        byte[] raw=encode("records","GENERATION",manifest);Files.write(path.resolve("generations/a/generation.gsr"),raw);
        Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",f.root().manifestDigest(),"node",name,"generation","a","digest",hash(raw))));
        var resources=resources();MembershipFloor.Copy result;
        try(var journal=MembershipGrantJournal.openGenerations(path,f.root(),V53DeclarationsTest.node(node),resources,f::verify,e->{})) {
            result=journal.floorCopyCurrent();assertArrayEquals(raw,result.generation.bytes());
        }
        assertEquals(0,resources.usage().leases());return result;
    }
    @Test void everyGoverningSubsetUsesTheCutsNextAuthority() throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7)) {
            var f=new V53CurrentGenerationFixture(size,through,false);var context=f.admitted.context;var copies=new ArrayList<MembershipFloor.Copy>();
            for(String voter:context.voters())copies.add(copy(temp.resolve(size+"-"+through+"-"+voter),size,through,Integer.parseInt(voter.substring(5))));
            for(int mask=0;mask<(1<<copies.size());mask++) {
                var selected=new ArrayList<MembershipFloor.Copy>();var voters=new HashSet<String>();
                for(int i=0;i<copies.size();i++)if((mask&(1<<i))!=0){selected.add(copies.get(i));voters.add(copies.get(i).owner.nodeId().value());}
                boolean quorum=voters.contains("node-1");
                for(String side:List.of("old","new")){var names=MembershipContext.nodes(context.view,side);quorum&=names.stream().filter(voters::contains).count()>names.size()/2;}
                if(quorum) {
                    var floor=MembershipFloor.create(f.root(),copies.getFirst(),selected);
                    MembershipFloor.verify(floor,f.root(),copies.getFirst(),selected);
                    assertEquals(context.cut,floor.value().get("cut"));assertEquals(selected.size(),list(floor.value().get("sources")).size());
                }else assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.root(),copies.getFirst(),selected));
            }
        }
    }
    Map<String,byte[]> files(MembershipFloor.Copy copy){var result=new TreeMap<String,byte[]>();for(String name:copy.fileNames())result.put(name,copy.fileBytes(name));return result;}
    @Test void exactGenerationForceObservationIsMandatory() throws Exception {
        var copy=copy(temp.resolve("copy"),3,0,1);
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.Copy.verify(copy.generation,copy.capsule,copy.owner,Set.of(),files(copy)));
        for(String record:List.of(copy.capsule.packet.capsule().digest(),"00".repeat(32))) {
            var wrong=new MembershipContext.Owned("node-1",copy.owner.storageId(),record,MembershipContext.cutDigest(copy.capsule.context.cut));
            assertThrows(IllegalArgumentException.class,()->MembershipFloor.Copy.verify(copy.generation,copy.capsule,copy.owner,Set.of(wrong),files(copy)));
        }
        var other=V53DeclarationsTest.node(2);
        var wrong=new MembershipContext.Owned(other.nodeId().value(),other.storageId(),copy.generation.digest(),MembershipContext.cutDigest(copy.capsule.context.cut));
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.Copy.verify(copy.generation,copy.capsule,other,Set.of(wrong),files(copy)));
    }
    @Test void duplicateAndDifferentCutsCannotFormFloor() throws Exception {
        var f=new V53CurrentGenerationFixture(3,6,false);var current=copy(temp.resolve("current"),3,6,1);var old=copy(temp.resolve("old"),3,0,2);
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.root(),current,List.of(current,current)));
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.root(),current,List.of(current,old)));
    }
    @Test void floorMustIncludeExactCurrentLocalCopyAndCannotBeRelabelled() throws Exception {
        var f=new V53CurrentGenerationFixture(3,7,false);var a=copy(temp.resolve("a"),3,7,1);var b=copy(temp.resolve("b"),3,7,2);var c=copy(temp.resolve("c"),3,7,6);
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.root(),a,List.of(b,c)));
        var floor=MembershipFloor.create(f.root(),a,List.of(a,b));assertEquals("node-1",floor.value().get("node"));
        var altered=new TreeMap<>(floor.value());altered.put("node","node-2");var other=decode(encode("records","FLOOR",altered),"records","FLOOR");
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.verify(other,f.root(),a,List.of(a,b)));
        var old=new TreeMap<>(a.generation.value());old.put("generation","b");var generation=decode(encode("records","GENERATION",old),"records","GENERATION");
        var observation=new MembershipContext.Owned("node-1",a.owner.storageId(),generation.digest(),MembershipContext.cutDigest(a.capsule.context.cut));
        var changed=files(a);changed.put("generation.gsr",generation.bytes());var different=MembershipFloor.Copy.verify(generation,a.capsule,a.owner,Set.of(observation),changed);
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.root(),a,List.of(different,b)));
    }
    @Test void removedOwnerRetainsItsFilesAndCannotProduceACopyVote() throws Exception {
        Path path=temp.resolve("removed");copy(path,3,6,3);var remote=new V53AdoptionFenceFixture(3,7);
        var initial=new V53CurrentGenerationFixture(3,6,false);remote.owned.addAll(initial.fixture.owned);
        try(var store=MembershipGrantJournal.openGenerations(path,initial.root(),V53DeclarationsTest.node(3),resources(),
                (r,p,images)->MembershipCapsule.verify(r,p,images,remote.owned),e->{})) {
            store.adoptCurrent(remote.remote.packet(),remote.remote.source.images,List.of());
            assertEquals("floor copy is not a governing voter",assertThrows(IllegalArgumentException.class,store::floorCopyCurrent).getMessage());
        }
        assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
    }
    @Test void lostOrChangedMaterializationNeverCountsAsCompleteCopy() throws Exception {
        var a=copy(temp.resolve("complete"),3,6,1);var forced=new MembershipContext.Owned("node-1",a.owner.storageId(),a.generation.digest(),MembershipContext.cutDigest(a.capsule.context.cut));
        var missing=files(a);missing.remove("source.gscp");
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.Copy.verify(a.generation,a.capsule,a.owner,Set.of(forced),missing));
        var altered=files(a);String image=altered.keySet().stream().filter(n->n.endsWith(".image")).findFirst().orElseThrow();altered.get(image)[0]^=1;
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.Copy.verify(a.generation,a.capsule,a.owner,Set.of(forced),altered));
        var mutable=files(a);var captured=MembershipFloor.Copy.verify(a.generation,a.capsule,a.owner,Set.of(forced),mutable);mutable.get(image)[0]^=1;
        var f=new V53CurrentGenerationFixture(3,6,false);var b=copy(temp.resolve("second"),3,6,2);
        assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(f.root(),captured,List.of(captured,b)));
    }

}
