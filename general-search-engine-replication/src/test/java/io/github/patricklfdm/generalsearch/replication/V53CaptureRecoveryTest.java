package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CaptureRecoveryTest {
    @TempDir Path temp;
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,V53CurrentGenerationFixture f,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openCapturing(path,f.root(),V53DeclarationsTest.node(1),r,f::verify,cut);
    }
    void interrupt(Path path,V53CurrentGenerationFixture f,String point)throws Exception {
        try(var store=open(path,f,resources(),e->{if(e.equals(point))throw new IOException("cut "+point);})) {
            assertThrows(IOException.class,()->store.prepareCurrent(f.fixture.source.ballot(20)));
        }
    }
    Map<String,String> files(Path path)throws Exception{return new V53SourceRetirementPlanTest().inventory(path);}
    Map<String,String> protectedFiles(Path path)throws Exception {
        var values=new TreeMap<>(files(path));values.keySet().removeIf(p->p.equals("grants.gsr") || p.equals(MembershipCaptureFiles.FILE) || p.startsWith("sources/"));return values;
    }
    @Test void recoversEveryCaptureBoundaryAndReturnsSameOriginalOnDuplicate()throws Exception {
        for(String point:V53CaptureRecoveryWorker.CUTS) {
            Path path=temp.resolve(point);var f=new V53CurrentGenerationFixture(3,1,true);f.provision(path);var protectedBytes=protectedFiles(path);interrupt(path,f,point);
            var r=resources();try(var store=open(path,f,r,e->{})) {
                var original=store.originalBasis().orElseThrow();assertEquals(f.accepted,original.value().get("accepted"));
                var before=files(path);assertArrayEquals(original.bytes(),store.prepareCurrent(f.fixture.source.ballot(20)).bytes());assertEquals(before,files(path));
                assertEquals(2,r.usage().counts().get(MembershipResources.Unit.APPLICATION));assertEquals(1,r.usage().counts().get(MembershipResources.Unit.SOURCE));
            }
            assertEquals(protectedBytes,protectedFiles(path));assertFalse(Files.exists(path.resolve(MembershipCaptureFiles.FILE)));assertEquals(0,r.usage().leases());
        }
    }
    @Test void completeProfilesRetainActualTailAndDoNotChangeOriginalGeneration()throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7))for(boolean tail:List.of(false,true)) {
            Path path=temp.resolve(size+"-"+through+"-"+tail);var f=new V53CurrentGenerationFixture(size,through,tail);f.provision(path);var before=protectedFiles(path);var r=resources();
            try(var store=open(path,f,r,e->{})){var basis=store.prepareCurrent(f.fixture.source.ballot(20));assertEquals(f.accepted,basis.value().get("accepted"));}
            try(var store=open(path,f,r,e->{})){assertEquals(f.accepted,store.originalBasis().orElseThrow().value().get("accepted"));}assertEquals(before,protectedFiles(path));assertEquals(0,r.usage().leases());
        }
    }
    @Test void repeatedRecoveryDeathKeepsTheSameGrantIdentity()throws Exception {
        Path path=temp.resolve("repeat");var f=new V53CurrentGenerationFixture(5,7,true);f.provision(path);interrupt(path,f,"SOURCE_PACKET_PREFIX_WRITTEN");
        var promise=Files.readAllBytes(path.resolve("grants.gsr"));var r=resources();
        for(String event:List.of("SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_IMAGE_PREFIX_WRITTEN","SOURCE_DIRECTORY_FORCED")) {
            assertThrows(IOException.class,()->open(path,f,r,e->{if(e.equals(event))throw new IOException("cut");}));
            assertArrayEquals(promise,Files.readAllBytes(path.resolve("grants.gsr")));assertEquals(0,r.usage().leases());
        }
        try(var store=open(path,f,r,e->{})){assertEquals(20L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}assertEquals(0,r.usage().leases());
    }
    @Test void changedPrefixExtraMemberAndMissingOriginalAreNeverRepaired()throws Exception {
        for(String change:List.of("packet","image","extra","selector","original","marker","basis")) {
            Path path=temp.resolve(change);var f=new V53CurrentGenerationFixture(3,1,true);f.provision(path);
            interrupt(path,f,change.equals("image")?"SOURCE_IMAGE_PREFIX_WRITTEN":change.equals("basis")?"BASIS_FORCED":"SOURCE_PACKET_PREFIX_WRITTEN");
            Path source;try(var stream=Files.list(path.resolve("sources"))){source=stream.findFirst().orElseThrow();}
            switch(change) {
                case "packet" -> {Path file=source.resolve("source.gscp");byte[] bytes=Files.readAllBytes(file);bytes[0]^=1;Files.write(file,bytes);}
                case "image" -> {Path file;try(var stream=Files.list(source)){file=stream.filter(p->p.toString().endsWith(".image")).findFirst().orElseThrow();}byte[] bytes=Files.readAllBytes(file);bytes[0]^=1;Files.write(file,bytes);}
                case "extra" -> Files.write(source.resolve("extra"),new byte[]{1});
                case "selector" -> {Path file=path.resolve("selector.gsr");byte[] bytes=Files.readAllBytes(file);bytes[0]^=1;Files.write(file,bytes);}
                case "original" -> Files.delete(path.resolve("generations/a/source.gscp"));
                case "marker" -> {Path file=path.resolve(MembershipCaptureFiles.FILE);byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);}
                case "basis" -> Files.delete(source.resolve("source.gscp"));
            }
            var before=files(path);var r=resources();assertThrows(Exception.class,()->open(path,f,r,e->{}));assertEquals(before,files(path));assertEquals(0,r.usage().leases());
        }
    }
    @Test void legacyModeRefusesNewAuthorityAndUnmarkedPartialCaptureRemainsRejected()throws Exception {
        Path path=temp.resolve("legacy");var f=new V53CurrentGenerationFixture(3,1,false);f.provision(path);interrupt(path,f,"SOURCE_PACKET_PREFIX_WRITTEN");
        var r=resources();assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openReclaiming(path,f.root(),V53DeclarationsTest.node(1),r,f::verify,e->{}));
        Files.delete(path.resolve(MembershipCaptureFiles.FILE));var before=files(path);assertThrows(IllegalArgumentException.class,()->open(path,f,r,e->{}));assertEquals(before,files(path));assertEquals(0,r.usage().leases());
    }
    @Test void higherObservationPreventsReturnButRecoveryPreservesOriginalForcedBasis()throws Exception {
        Path path=temp.resolve("fence");var f=new V53CurrentGenerationFixture(3,1,true);f.provision(path);var ref=new AtomicReference<MembershipGrantJournal>();var r=resources();
        try(var store=open(path,f,r,e->{if(e.equals("BASIS_FORCED"))ref.get().observeCurrent(f.fixture.source.ballot(21));})) {
            ref.set(store);assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.fixture.source.ballot(20)));
        }
        try(var store=open(path,f,r,e->{})){assertEquals(f.accepted,store.originalBasis().orElseThrow().value().get("accepted"));assertEquals(20L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
        assertEquals(0,r.usage().leases());
    }
    @Test void capacityRefusalOccursBeforePromiseOrIntentAndKeepsLiveLeases()throws Exception {
        Path path=temp.resolve("capacity");var f=new V53CurrentGenerationFixture(3,1,false);f.provision(path);var r=resources();
        try(var store=open(path,f,r,e->{})) {
            var extra=new ArrayList<MembershipResources.Lease>();for(int i=0;i<6;i++)extra.add(r.reserve(MembershipResources.Unit.APPLICATION,"held-"+i,1));
            var before=files(path);var usage=r.usage();assertThrows(MembershipOperationException.class,()->store.prepareCurrent(f.fixture.source.ballot(20)));assertEquals(before,files(path));assertEquals(usage,r.usage());extra.forEach(MembershipResources.Lease::close);
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void sourceReplacementAtCutIsDetectedAndCannotBeAcknowledged()throws Exception {
        Path path=temp.resolve("inode");var f=new V53CurrentGenerationFixture(3,1,false);f.provision(path);var r=resources();
        try(var store=open(path,f,r,e->{if(e.equals("SOURCE_PACKET_PREFIX_WRITTEN")) {
            Path dir;try(var stream=Files.list(path.resolve("sources"))){dir=stream.findFirst().orElseThrow();}Path file=dir.resolve("source.gscp"),other=dir.resolve("replacement");
            Files.write(other,Files.readAllBytes(file));Files.move(other,file,StandardCopyOption.REPLACE_EXISTING);
        }})){assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.fixture.source.ballot(20)));}
        assertEquals(0,r.usage().leases());
    }
    @Test void promiseWithoutCaptureIntentNeverInventsAnOriginalResponse()throws Exception {
        for(String point:List.of("PROMISE_BEFORE_WRITE","PROMISE_WRITTEN","PROMISE_FORCED")) {
            Path path=temp.resolve(point);var f=new V53CurrentGenerationFixture(3,1,true);f.provision(path);interrupt(path,f,point);var r=resources();
            assertFalse(Files.exists(path.resolve(MembershipCaptureFiles.FILE)));assertTrue(MembershipBasisSources.children(path.resolve("sources"),6).isEmpty());
            try(var store=open(path,f,r,e->{})) {
                assertTrue(store.originalBasis().isEmpty());
                if(!point.equals("PROMISE_BEFORE_WRITE"))assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.fixture.source.ballot(20)));
                assertEquals(f.accepted,store.prepareCurrent(f.fixture.source.ballot(point.equals("PROMISE_BEFORE_WRITE")?20:21)).value().get("accepted"));
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void activeCapturePinsAllLiveReservationsAndBlocksAnotherGrant()throws Exception {
        Path path=temp.resolve("pin");var f=new V53CurrentGenerationFixture(3,1,true);f.provision(path);var r=resources();
        var field=MembershipResources.class.getDeclaredField("leases");field.setAccessible(true);var before=new ArrayList<Object>();var ref=new AtomicReference<MembershipGrantJournal>();
        try(var store=open(path,f,r,e->{
            if(ref.get()!=null){assertTrue(((Map<?,?>)fieldValue(field,r)).values().containsAll(before));
                if(e.equals("CAPTURE_INTENT_CREATED"))assertThrows(IllegalArgumentException.class,()->ref.get().prepareCurrent(f.fixture.source.ballot(21)));}
        })) {
            ref.set(store);before.addAll(((Map<?,?>)field.get(r)).values());store.prepareCurrent(f.fixture.source.ballot(20));
        }
        assertEquals(0,r.usage().leases());
    }
    private Object fieldValue(java.lang.reflect.Field field,Object object){try{return field.get(object);}catch(IllegalAccessException e){throw new AssertionError(e);}}
    @Test void recoveredSourceCanRetireWithoutLosingItsAboveFloorOwnedTail()throws Exception {
        Path path=temp.resolve("retire");var f=new V53CurrentGenerationFixture(3,1,true);f.provision(path);interrupt(path,f,"SOURCE_IMAGE_PREFIX_WRITTEN");var r=resources();
        try(var store=open(path,f,r,e->{})) {
            String id=(String)store.originalBasis().orElseThrow().value().get("basisId");store.prepareCurrent(f.fixture.source.ballot(21));
            new V53SourceRetirementPlanTest().floor(store,temp.resolve("peers"),f);store.retireSource(id);
            assertEquals(f.accepted,store.currentOwnedTail().orElseThrow().record());assertFalse(Files.exists(path.resolve("sources").resolve(id)));
        }
        try(var store=open(path,f,r,e->{})){assertEquals(f.accepted,store.currentOwnedTail().orElseThrow().record());}assertEquals(0,r.usage().leases());
    }

    @Test void emptyIntentCannotSubstituteTheInstalledPromiseForALostOriginalGrant()throws Exception {
        Path path=temp.resolve("lost-grant");var f=new V53CurrentGenerationFixture(3,0,false);f.provision(path);
        Files.write(path.resolve(MembershipCaptureFiles.FILE),new byte[0]);var before=files(path);var r=resources();
        assertEquals("capture original grant is not newer than installed authority",assertThrows(IllegalArgumentException.class,()->open(path,f,r,e->{})).getMessage());
        assertEquals(before,files(path));assertEquals(0,r.usage().leases());
    }

}
