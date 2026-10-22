package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CapturedSourceReleaseTest {
    @TempDir Path temp;
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,V53AdoptionFenceFixture f,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openReclaiming(path,f.initial.root(),V53DeclarationsTest.node(1),resources,
                (root,packet,images)->MembershipCapsule.verify(root,packet,images,f.owned),cut);
    }
    String provision(Path path,V53AdoptionFenceFixture f,boolean tail)throws Exception {
        var initial=new V53CurrentGenerationFixture(f.initial.size,0,tail);f.owned.addAll(initial.fixture.owned);initial.provision(path);
        try(var store=open(path,f,resources(),e->{if(e.equals("SOURCE_DIRECTORY_FORCED"))throw new IOException("captured");})) {
            assertThrows(IOException.class,()->store.prepareCurrent(initial.fixture.source.ballot(20)));
        }
        String id;try(var store=open(path,f,resources(),e->{})) {
            assertTrue(store.originalBasis().isEmpty());id=(String)store.promised().orElseThrow().value().get("basisId");
            store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());var copies=new ArrayList<MembershipFloor.Copy>();copies.add(store.floorCopyCurrent());
            for(int node=2;node<=initial.size/2+1;node++)copies.add(new V53FloorTest().copy(path.getParent().resolve("peer-"+node),initial.size,
                    Math.toIntExact(number(object(f.remote.capsule.get("cut")).get("index"))),node));
            store.establishFloor(copies);store.retireInactive();
        }
        return id;
    }
    void finish(MembershipGrantJournal store,Path path,String id)throws Exception {if(Files.exists(path.resolve("sources").resolve(id)) || Files.exists(path.resolve(MembershipSourceRetirementFiles.FILE)))store.retireSource(id);}
    @Test void coveredCapturedSourceReclaimsWithoutSynthesizingBasis()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(6,7))for(boolean tail:List.of(false,true)) {
            Path dir=temp.resolve(size+"-"+through+"-"+tail);Files.createDirectory(dir);Path path=dir.resolve("authority");var f=new V53AdoptionFenceFixture(size,through);String id=provision(path,f,tail);var resources=resources();
            try(var store=open(path,f,resources,e->{})) {
                var plan=store.planSourceRetirement(id);assertNull(plan.basis);byte[] highest=store.promised().orElseThrow().bytes();var before=new V53SourceReleaseTest().protectedFiles(path,id);
                store.retireSource(id);assertArrayEquals(highest,store.promised().orElseThrow().bytes());assertEquals(before,new V53SourceReleaseTest().protectedFiles(path,id));
                assertFalse(Files.exists(path.resolve("sources").resolve(id)));assertEquals(size/2+1,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
            }
            try(var store=open(path,f,resources,e->{})){assertTrue(store.originalBasis().isEmpty());}assertEquals(0,resources.usage().leases());
        }
    }
    @Test void capturedSourceWithoutALaterFloorRemainsRetained()throws Exception {
        Path path=temp.resolve("same-cut");var f=new V53AdoptionFenceFixture(3,6);f.initial.provision(path);
        try(var store=open(path,f,resources(),e->{if(e.equals("SOURCE_DIRECTORY_FORCED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(20)));}
        try(var store=open(path,f,resources(),e->{})) {
            String id=(String)store.promised().orElseThrow().value().get("basisId");store.prepareCurrent(f.initial.fixture.source.ballot(21));
            new V53SourceRetirementPlanTest().floor(store,temp.resolve("peers"),f.initial);
            assertEquals("captured source requires a strictly later governing floor",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
            assertTrue(Files.exists(path.resolve("sources").resolve(id)));
        }
    }
    @Test void allDecisionJournalAndDeletionBoundariesRecoverCapturedSources()throws Exception {
        for(String point:V53SourceReleaseWorker.CUTS) {
            Path dir=temp.resolve(point);Files.createDirectory(dir);Path path=dir.resolve("authority");var f=new V53AdoptionFenceFixture(3,6);String id=provision(path,f,false);var resources=resources();
            String event=point.split("@")[0];int expected=point.contains("@")?2:1;int[] seen={0};var before=new V53SourceReleaseTest().protectedFiles(path,id);
            try(var store=open(path,f,resources,e->{if(e.equals(event) && ++seen[0]==expected)throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
            try(var store=open(path,f,resources,e->{})){finish(store,path,id);}assertEquals(before,new V53SourceReleaseTest().protectedFiles(path,id));assertFalse(Files.exists(path.resolve("sources").resolve(id)));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void capturedDecisionCanOnlyResumeAnExactOriginalPrefix()throws Exception {
        for(boolean pruned:List.of(false,true)) {
            Path dir=temp.resolve("partial-"+pruned);Files.createDirectory(dir);Path path=dir.resolve("authority");var f=new V53AdoptionFenceFixture(3,6);String id=provision(path,f,false);var resources=resources();
            try(var store=open(path,f,resources,e->{if(e.equals(pruned?"SOURCE_RETIREMENT_JOURNAL_PRUNED":"SOURCE_RETIREMENT_WRITTEN"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
            Path file=path.resolve(MembershipSourceRetirementFiles.FILE);byte[] original=Files.readAllBytes(file);Files.write(file,Arrays.copyOf(original,original.length-1));
            if(pruned)assertEquals("missing or unbound original source",assertThrows(IllegalArgumentException.class,()->open(path,f,resources,e->{})).getMessage());
            else try(var store=open(path,f,resources,e->{})) {
                assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.remote.source.ballot(50)));finish(store,path,id);
            }
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void missingCapturedOriginalCannotBeReplacedByItsPendingDecision()throws Exception {
        Path dir=temp.resolve("missing");Files.createDirectory(dir);Path path=dir.resolve("authority");var f=new V53AdoptionFenceFixture(3,6);String id=provision(path,f,false);
        try(var store=open(path,f,resources(),e->{if(e.equals("SOURCE_RETIREMENT_FORCED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
        try(var paths=Files.walk(path.resolve("sources").resolve(id))){for(Path p:paths.sorted(Comparator.reverseOrder()).toList())Files.delete(p);}
        var before=new V53SourceRetirementPlanTest().inventory(path);var resources=resources();
        assertEquals("missing or unbound original source",assertThrows(IllegalArgumentException.class,()->open(path,f,resources,e->{})).getMessage());
        assertEquals(before,new V53SourceRetirementPlanTest().inventory(path));assertEquals(0,resources.usage().leases());
    }
    @Test void additionalUncoveredAcceptCannotBeHiddenByAnAbsentBasis()throws Exception {
        Path dir=temp.resolve("uncovered");Files.createDirectory(dir);Path path=dir.resolve("authority");var f=new V53AdoptionFenceFixture(3,6);String id=provision(path,f,false);
        Path file=path.resolve("sources").resolve(id).resolve("source.gscp");var original=MembershipSourcePacket.decode(Files.readAllBytes(file));
        var objects=new TreeMap<String,byte[]>();original.objectNames().forEach(h->objects.put(h,original.objectBytes(h)));
        var beyond=new V53AdoptionFenceFixture(3,7);var source=beyond.remote.packet();boolean found=false;
        for(String digest:source.objectNames()) {
            byte[] raw=source.objectBytes(digest);if(raw.length>=HEADER && java.nio.ByteBuffer.wrap(raw).getInt()==0x47534552
                    && Short.toUnsignedInt(java.nio.ByteBuffer.wrap(raw).getShort(8))==number(object(object(CATALOG.get("records")).get("ACCEPT")).get("id"))) {
                var accept=decode(raw,"records","ACCEPT");if(number(accept.value().get("index"))==7){objects.put(digest,raw);found=true;}
            }
        }
        assertTrue(found);var cap=new TreeMap<>(original.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        Files.write(file,MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,original.images()));
        var before=new V53SourceRetirementPlanTest().inventory(path);var resources=resources();
        try(var store=open(path,f,resources,e->{})) {
            assertEquals("captured source has an uncovered ACCEPT object",assertThrows(IllegalArgumentException.class,()->store.planSourceRetirement(id)).getMessage());
        }
        assertEquals(before,new V53SourceRetirementPlanTest().inventory(path));assertEquals(0,resources.usage().leases());
    }
    @Test void opaquePayloadWithRecordMagicIsNotMistakenForAnOwnedAccept()throws Exception {
        Path dir=temp.resolve("opaque");Files.createDirectory(dir);Path path=dir.resolve("authority");var f=new V53AdoptionFenceFixture(3,6);String id=provision(path,f,false);
        Path file=path.resolve("sources").resolve(id).resolve("source.gscp");var original=MembershipSourcePacket.decode(Files.readAllBytes(file));
        var objects=new TreeMap<String,byte[]>();original.objectNames().forEach(h->objects.put(h,original.objectBytes(h)));
        byte[] payload=new byte[HEADER+32];java.nio.ByteBuffer.wrap(payload).putInt(0x47534552).putShort(8,(short)number(object(object(CATALOG.get("records")).get("ACCEPT")).get("id")));
        objects.put(hash(payload),payload);var cap=new TreeMap<>(original.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        Files.write(file,MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,original.images()));
        var resources=resources();try(var store=open(path,f,resources,e->{})){store.retireSource(id);assertFalse(Files.exists(file));}
        assertEquals(0,resources.usage().leases());
    }
    @Test void pendingCompletedDecisionCannotConcealALostOriginalBasisFrame()throws Exception {
        Path dir=temp.resolve("lost-basis");Files.createDirectory(dir);Path path=dir.resolve("authority");String id=V53SourceReleaseWorker.provision(path,3,0);var local=new V53CurrentGenerationFixture(3,0,false);
        try(var store=MembershipGrantJournal.openReclaiming(path,local.root(),V53DeclarationsTest.node(1),resources(),local::verify,e->{if(e.equals("SOURCE_RETIREMENT_FORCED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
        byte[] bytes=Files.readAllBytes(path.resolve("grants.gsr"));var kept=new java.io.ByteArrayOutputStream();int offset=0;boolean dropped=false;
        while(offset<bytes.length) {
            int number=Short.toUnsignedInt(java.nio.ByteBuffer.wrap(bytes).getShort(offset+8));String kind=number==3?"PROMISE":number==4?"BASIS":"SELECTED";
            int length=HEADER+header(Arrays.copyOfRange(bytes,offset,offset+HEADER),"records",kind);byte[] raw=Arrays.copyOfRange(bytes,offset,offset+length);offset+=length;
            if(kind.equals("BASIS") && decode(raw,"records",kind).value().get("basisId").equals(id))dropped=true;else kept.writeBytes(raw);
        }
        assertTrue(dropped);Files.write(path.resolve("grants.gsr"),kept.toByteArray());var before=new V53SourceRetirementPlanTest().inventory(path);var resources=resources();
        assertEquals("captured source requires a strictly later governing floor",assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openReclaiming(path,local.root(),V53DeclarationsTest.node(1),resources,local::verify,e->{})).getMessage());
        assertEquals(before,new V53SourceRetirementPlanTest().inventory(path));assertEquals(0,resources.usage().leases());
    }
    @Test void capturedDecisionCannotHideARealPersistedBasis()throws Exception {
        Path dir=temp.resolve("real");Files.createDirectory(dir);Path path=dir.resolve("authority");String id=V53SourceReleaseWorker.provision(path,3,0);var local=new V53CurrentGenerationFixture(3,0,false);
        try(var store=MembershipGrantJournal.openReclaiming(path,local.root(),V53DeclarationsTest.node(1),resources(),local::verify,e->{if(e.equals("SOURCE_RETIREMENT_FORCED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
        var original=new MembershipSourceRetirementFiles(path).decision().orElseThrow();var omitted=new MembershipSourceRetirementFiles.Decision(original.record(),original.promise(),null,original.capsule());
        Files.write(path.resolve(MembershipSourceRetirementFiles.FILE),omitted.bytes());var before=new V53SourceRetirementPlanTest().inventory(path);var resources=resources();
        assertEquals("source retirement differs from original source",assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openReclaiming(path,local.root(),V53DeclarationsTest.node(1),resources,local::verify,e->{})).getMessage());
        assertEquals(before,new V53SourceRetirementPlanTest().inventory(path));assertEquals(0,resources.usage().leases());
    }
}
