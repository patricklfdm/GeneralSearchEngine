package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual local owner/floor/source storage. Historical membership edges remain conditional fixtures. */
class V53RetirementImagesTest {
    @TempDir Path temp;
    static final String BINDING="retirement/"+MembershipRetirementImages.FILE;
    static final List<String> BORROW_CUTS=List.of("RETIREMENT_BORROW_PREFIX_WRITTEN","RETIREMENT_BORROW_WRITTEN",
            "RETIREMENT_BORROW_FORCED","RETIREMENT_BORROWED_IMAGES_FORCED","RETIREMENT_BORROW_CLEARED");
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,int size,int through,MembershipResources used,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=new V53CurrentGenerationFixture(size,through,false);
        return MembershipGrantJournal.openMaintenance(path,f.root(),V53DeclarationsTest.node(1),used,f::verify,cut);
    }
    Path provision(String name,int size,int through)throws Exception {
        Path parent=temp.resolve(name);Files.createDirectory(parent);Path path=parent.resolve("store");
        V53RetirementWorker.provision(path,size,through);var used=resources();
        try(var owner=open(path,size,through,used,e->{})) {owner.prepareCurrent(new V53CurrentGenerationFixture(size,through,false).fixture.source.ballot(101));}
        assertEquals(0,used.usage().leases());return path;
    }
    static void copy(Path from,Path to)throws IOException {
        try(var walk=Files.walk(from)){for(Path p:walk.toList()){Path target=to.resolve(from.relativize(p));if(Files.isDirectory(p))Files.createDirectories(target);else Files.copy(p,target);}}
    }
    static Map<String,String> protectedBytes(Path path)throws IOException {
        var result=new TreeMap<String,String>();try(var walk=Files.walk(path)){for(Path p:walk.filter(Files::isRegularFile).toList()) {
            String name=path.relativize(p).toString();if(!name.startsWith("retirement/") && !name.startsWith("generations/a/"))result.put(name,hash(Files.readAllBytes(p)));
        }}return result;
    }
    static void bounded(MembershipResources used) {
        var usage=used.usage();assertTrue(usage.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=7);
        assertTrue(usage.counts().getOrDefault(MembershipResources.Unit.SOURCE,0)<=6);
        assertTrue(usage.metadata()<=MembershipResources.METADATA_LIMIT);assertTrue(usage.staging()<=512*MembershipResources.MIB);
    }
    @Test void stableJointAndNewViewsRetireWithinSevenImagesAndKeepAllProtectedBytes()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7)) {
            Path path=provision("complete-"+size+"-"+through,size,through);var before=protectedBytes(path);var used=resources();boolean[] borrowed={false};int[] peak={0,0};
            try(var owner=open(path,size,through,used,event->{
                bounded(used);peak[0]=Math.max(peak[0],used.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0));
                peak[1]=Math.max(peak[1],used.usage().counts().getOrDefault(MembershipResources.Unit.SOURCE,0));
                if(event.equals("RETIREMENT_PARENT_FORCED")) {
                    borrowed[0]=Files.exists(path.resolve(BINDING));
                    try(var members=Files.list(path.resolve("retirement/source"))){assertEquals(size==3,members.anyMatch(p->p.toString().endsWith(".image")));}
                }
            })) {assertTrue(owner.retireInactive().isPresent());assertTrue(owner.retireInactive().isEmpty());}
            assertEquals(size>3,borrowed[0]);assertEquals(7,peak[0]);assertEquals(size/2+4,peak[1]);
            assertEquals(before,protectedBytes(path));assertFalse(Files.exists(path.resolve("generations/a")));assertFalse(Files.exists(path.resolve("retirement")));assertEquals(0,used.usage().leases());
        }
    }
    @Test void eachBorrowedBoundaryResumesAndAuthorityRecoveryCanBeInterruptedAgain()throws Exception {
        Path seed=provision("seed",5,0);var points=new ArrayList<>(V53RetirementTest.CUTS);points.remove("RETIREMENT_IMAGE_WRITTEN");points.remove("RETIREMENT_IMAGE_FORCED");points.addAll(BORROW_CUTS);
        for(String point:points) {
            Path path=temp.resolve(point);copy(seed,path);var before=protectedBytes(path);var used=resources();
            try(var owner=open(path,5,0,used,event->{bounded(used);if(event.equals(point))throw new IOException("cut "+point);})) {assertThrows(IOException.class,owner::retireInactive,point);}
            assertEquals(0,used.usage().leases());assertEquals(before,protectedBytes(path));
            if(Files.exists(path.resolve("retirement/retirement.gsr"))) {
                byte[] original=Files.readAllBytes(path.resolve("retirement/retirement.gsr"));
                try(var owner=open(path,5,0,used,event->{bounded(used);if(event.equals("RETIREMENT_AUTHORITY_RESEALED"))throw new IOException("repeat");})) {assertThrows(IOException.class,owner::retireInactive,point);}
                assertArrayEquals(original,Files.readAllBytes(path.resolve("retirement/retirement.gsr")));assertEquals(0,used.usage().leases());
            }
            try(var owner=open(path,5,0,used,event->bounded(used))) {owner.retireInactive();assertTrue(owner.retireInactive().isEmpty());}
            assertFalse(Files.exists(path.resolve("generations/a")));assertFalse(Files.exists(path.resolve("retirement")));assertEquals(before,protectedBytes(path));assertEquals(0,used.usage().leases());
        }
    }
    void interrupt(Path path,String point)throws Exception {
        var used=resources();try(var owner=open(path,5,0,used,event->{if(event.equals(point))throw new IOException("stop");})) {assertThrows(IOException.class,owner::retireInactive);}
        assertEquals(0,used.usage().leases());
    }
    @Test void missingChangedOrNoncanonicalBindingNeverRepairsItselfFromOriginalImages()throws Exception {
        Path seed=provision("binding-seed",5,0);interrupt(seed,"RETIREMENT_PARENT_FORCED");
        for(String mutation:List.of("missing","truncated","changed","extra-field","foreign-floor","foreign-generation","boolean-size")) {
            Path path=temp.resolve(mutation);copy(seed,path);Path binding=path.resolve(BINDING);byte[] raw=Files.readAllBytes(binding);
            if(mutation.equals("missing"))Files.delete(binding);
            else if(mutation.equals("truncated"))Files.write(binding,Arrays.copyOf(raw,raw.length/2));
            else if(mutation.equals("changed")){raw[raw.length-1]^=1;Files.write(binding,raw);}
            else {
                var value=new TreeMap<>(object(parse(raw,65536)));
                if(mutation.equals("extra-field"))value.put("extra",true);
                if(mutation.equals("foreign-floor"))value.put("floor","00".repeat(32));
                if(mutation.equals("foreign-generation") || mutation.equals("boolean-size")) {
                    var rows=new ArrayList<Object>(list(value.get("images")));var row=new TreeMap<>(object(rows.getFirst()));
                    row.put(mutation.equals("boolean-size")?"size":"generation",mutation.equals("boolean-size")?false:"00".repeat(32));rows.set(0,row);value.put("images",rows);
                }
                Files.write(binding,canonical(value,65536));
            }
            var used=resources();try(var owner=open(path,5,0,used,event->{})) {assertThrows(Exception.class,owner::retireInactive,mutation);}
            assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));assertEquals(0,used.usage().leases());
        }
    }
    @Test void partialCandidateRequiresTheOriginalExactPrefix()throws Exception {
        Path path=provision("prefix",5,0);interrupt(path,"RETIREMENT_BORROW_PREFIX_WRITTEN");Path binding=path.resolve(BINDING);byte[] raw=Files.readAllBytes(binding);raw[raw.length-1]^=1;Files.write(binding,raw);
        var used=resources();try(var owner=open(path,5,0,used,event->{})) {assertThrows(Exception.class,owner::retireInactive);}
        assertFalse(Files.exists(path.resolve("retirement/retirement.gsr")));assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));assertEquals(0,used.usage().leases());
    }
    @Test void borrowingPinsTheCompleteFloorIncludingItsLiveInodeAndCleanupLifetime()throws Exception {
        Path path=provision("inode",5,0);var used=resources();
        Path image;try(var walk=Files.walk(path.resolve("floor-copies"))){image=walk.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}
        try(var owner=open(path,5,0,used,event->{if(event.equals("RETIREMENT_DELETE_VALIDATED")) {
            Path next=temp.resolve("same-bytes");Files.copy(image,next);Files.move(next,image,StandardCopyOption.REPLACE_EXISTING);
        }})) {assertThrows(IllegalArgumentException.class,owner::retireInactive);}
        assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));assertEquals(0,used.usage().leases());
        Path cleanup=provision("cleanup",5,0);interrupt(cleanup,"RETIREMENT_DIRECTORY_DELETED");
        try(var owner=open(cleanup,5,0,used,event->{})) {
            assertThrows(IllegalArgumentException.class,owner::releaseFloor);
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(new V53CurrentGenerationFixture(5,0,false).fixture.source.ballot(102)));
            owner.retireInactive();owner.releaseFloor();assertNotNull(owner.prepareCurrent(new V53CurrentGenerationFixture(5,0,false).fixture.source.ballot(102)));
        }
        assertEquals(0,used.usage().leases());
    }
    @Test void absentExactImageCannotBeReplacedWithAnotherFloorImage()throws Exception {
        Path path=provision("absent",5,0);interrupt(path,"RETIREMENT_PARENT_FORCED");
        var record=decode(Files.readAllBytes(path.resolve("retirement/retirement.gsr")),"records","RETIREMENT");
        var f=new V53CurrentGenerationFixture(5,0,false);var used=resources();
        try(var floors=new MembershipFloorFiles(path,f.root(),V53DeclarationsTest.node(1),used,f::verify)) {
            var retained=floors.retained().orElseThrow();byte[] binding=MembershipRetirementImages.create(record,retained);
            var resolved=MembershipRetirementImages.resolve(binding,record,retained);assertEquals(1,resolved.size());
            for(String kind:List.of("digest","length")) {
                var value=new TreeMap<>(record.value());var rows=new ArrayList<Object>();
                for(Object raw:list(value.get("files"))) {
                    var row=new TreeMap<>(object(raw));String name=(String)row.get("path");
                    if(name.endsWith(".image")) {
                        if(kind.equals("length"))row.put("size",number(row.get("size"))+1);
                        else {row.put("path","generations/a/"+"00".repeat(32)+".image");row.put("sha256","00".repeat(32));}
                    }
                    rows.add(row);
                }
                value.put("files",rows);var altered=decode(encode("records","RETIREMENT",value),"records","RETIREMENT");
                assertThrows(IllegalArgumentException.class,()->MembershipRetirementImages.create(altered,retained));
            }
        }
        assertEquals(0,used.usage().leases());assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
    }
    @Test void oldPacketMayDifferWhileOnlyItsExactImageIsBorrowed()throws Exception {
        Path path=temp.resolve("different-packet");var f=new V53GenerationInstallFixture(5,0,1,false);f.initial.provision(path);
        byte[] oldPacket=Files.readAllBytes(path.resolve("generations/a/source.gscp"));var used=resources();
        var peers=new ArrayList<MembershipFloor.Copy>();
        for(int node=2;node<=3;node++)peers.add(new V53FloorTest().copy(temp.resolve("new-peer-"+node),5,1,node));
        try(var owner=MembershipGrantJournal.openMaintenance(path,f.root(),V53DeclarationsTest.node(1),used,f::verify,event->{
            if(event.equals("RETIREMENT_FILE_DELETED"))throw new IOException("old image removed");
        })) {
            owner.prepareCurrent(f.initial.fixture.source.ballot(100));var offers=f.offers(owner,100);
            owner.selectCurrent(offers,f.bridges);owner.installCurrent(offers,f.bridges,f.images());owner.prepareCurrent(f.initial.fixture.source.ballot(101));
            var local=owner.floorCopyCurrent();assertFalse(Arrays.equals(oldPacket,local.fileBytes("source.gscp")));peers.addFirst(local);owner.establishFloor(peers);
            assertThrows(IOException.class,owner::retireInactive);
        }
        assertEquals(0,used.usage().leases());assertArrayEquals(oldPacket,Files.readAllBytes(path.resolve("retirement/source/source.gscp")));
        assertTrue(Files.exists(path.resolve(BINDING)));
        try(var owner=MembershipGrantJournal.openMaintenance(path,f.root(),V53DeclarationsTest.node(1),used,f::verify,event->bounded(used))) {owner.retireInactive();owner.releaseFloor();}
        assertEquals(0,used.usage().leases());assertFalse(Files.exists(path.resolve("generations/a")));
    }
    @Test void extraSourcePressureStillRefusesBeforeAnyRetirementWrite()throws Exception {
        Path path=provision("source-capacity",5,0);var used=resources();
        try(var owner=open(path,5,0,used,event->{});var pressure=used.reserve(MembershipResources.Unit.SOURCE,"pressure",1)) {
            assertThrows(IllegalArgumentException.class,owner::retireInactive);assertFalse(Files.exists(path.resolve("retirement")));assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
        }
        assertEquals(0,used.usage().leases());
    }
}
