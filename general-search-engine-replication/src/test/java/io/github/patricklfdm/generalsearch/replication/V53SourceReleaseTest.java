package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SourceReleaseTest {
    @TempDir Path temp;
    final V53CurrentGenerationFixture f=new V53CurrentGenerationFixture(3,0,false);
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,MembershipResources r,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openReclaiming(path,f.root(),V53DeclarationsTest.node(1),r,f::verify,cut);
    }
    String provision(Path path)throws Exception {Files.createDirectory(path.getParent());return V53SourceReleaseWorker.provision(path,3,0);}
    Map<String,String> protectedFiles(Path path,String id)throws Exception {
        var files=new TreeMap<String,String>();try(var all=Files.walk(path)){for(Path file:all.filter(Files::isRegularFile).toList()) {
            String name=path.relativize(file).toString();if(!Set.of("grants.gsr",MembershipSourceRetirementFiles.FILE,MembershipJournalRotation.PENDING).contains(name) && !name.startsWith("sources/"+id+"/"))files.put(name,hash(Files.readAllBytes(file)));
        }}return files;
    }
    void finish(MembershipGrantJournal store,Path path,String id)throws Exception {if(Files.exists(path.resolve("sources").resolve(id)) || Files.exists(path.resolve(MembershipSourceRetirementFiles.FILE)))store.retireSource(id);}
    private Set<Object> liveLeases(MembershipResources resources)throws Exception {
        var field=MembershipResources.class.getDeclaredField("leases");field.setAccessible(true);
        return new HashSet<>(((Map<?,?>)field.get(resources)).values());
    }
    @Test void retiringOneSourceNeverReleasesOrReplacesSurvivingReservations()throws Exception {
        Path path=temp.resolve("continuous/authority");String id=provision(path);var resources=resources();
        try(var store=open(path,resources,e->{})) {
            var before=liveLeases(resources);store.retireSource(id);var after=liveLeases(resources);
            assertTrue(before.containsAll(after),"surviving reservations must retain their original lease objects");
            assertEquals(2,before.size()-after.size(),"release only the retired source and its application image");
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void repeatedRetirementReturnsSourceAndApplicationReservations()throws Exception {
        Path path=temp.resolve("loop/authority");String id=provision(path);var resources=resources();
        try(var store=open(path,resources,e->{})) {
            for(int next=22;next<=28;next++) {
                String latest=(String)store.originalBasis().orElseThrow().value().get("basisId");var before=protectedFiles(path,id);
                store.retireSource(id);assertEquals(before,protectedFiles(path,id));assertEquals(3,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
                assertEquals(4,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));assertFalse(Files.exists(path.resolve("sources").resolve(id)));
                store.prepareCurrent(f.fixture.source.ballot(next));id=latest;
            }
            store.retireSource(id);assertEquals(3,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        assertEquals(0,resources.usage().leases());try(var store=open(path,resources,e->{})){assertEquals(28L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}assertEquals(0,resources.usage().leases());
    }
    @Test void everyBoundaryReopensWithoutLosingProtectedAuthority()throws Exception {
        for(String cut:V53SourceReleaseWorker.CUTS) {
            Path path=temp.resolve(cut+"/authority");String id=provision(path);var before=protectedFiles(path,id);var resources=resources();
            String event=cut.split("@")[0];int expected=cut.contains("@")?2:1;int[] seen={0};
            try(var store=open(path,resources,e->{if(e.equals(event) && ++seen[0]==expected)throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
            assertEquals(0,resources.usage().leases());
            try(var store=open(path,resources,e->{})){finish(store,path,id);assertEquals(21L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
            assertEquals(before,protectedFiles(path,id));assertFalse(Files.exists(path.resolve("sources").resolve(id)));assertFalse(Files.exists(path.resolve(MembershipSourceRetirementFiles.FILE)));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void interruptedRecoveryCanBeInterruptedAgainAfterPartialDeletion()throws Exception {
        Path path=temp.resolve("again/authority");String id=provision(path);var before=protectedFiles(path,id);var resources=resources();
        try(var store=open(path,resources,e->{if(e.equals("SOURCE_RETIREMENT_FILE_DELETED"))throw new IOException("first");})){assertThrows(IOException.class,()->store.retireSource(id));}
        assertThrows(IOException.class,()->open(path,resources,e->{if(e.equals("SOURCE_RETIREMENT_FORCED"))throw new IOException("second");}));assertEquals(0,resources.usage().leases());
        try(var store=open(path,resources,e->{})){finish(store,path,id);}assertEquals(before,protectedFiles(path,id));assertEquals(0,resources.usage().leases());
    }
    @Test void pendingAuthorityBlocksEveryOtherMaintenanceOrGrant()throws Exception {
        Path path=temp.resolve("blocked/authority");String id=provision(path);MembershipGrantJournal[] ref={null};boolean[] checked={false};
        try(var store=open(path,resources(),e->{if(e.equals("SOURCE_RETIREMENT_FORCED")) {
            assertThrows(IllegalArgumentException.class,()->ref[0].prepareCurrent(f.fixture.source.ballot(22)));
            assertThrows(IllegalArgumentException.class,ref[0]::rotateJournal);assertThrows(IllegalArgumentException.class,ref[0]::releaseFloor);
            assertThrows(IllegalArgumentException.class,ref[0]::retireInactive);assertThrows(IllegalArgumentException.class,ref[0]::floorCopyCurrent);checked[0]=true;
        }})){ref[0]=store;store.retireSource(id);}assertTrue(checked[0]);
    }
    @Test void oldModesCannotOpenPendingAuthorityAndWrongResumeCannotReplaceIt()throws Exception {
        Path path=temp.resolve("legacy/authority");String id=provision(path);var resources=resources();
        try(var store=open(path,resources,e->{if(e.equals("SOURCE_RETIREMENT_CREATED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openMaintenance(path,f.root(),V53DeclarationsTest.node(1),resources,f::verify,e->{}));
        try(var store=open(path,resources,e->{})){assertThrows(IllegalArgumentException.class,()->store.retireSource(UUID.randomUUID().toString()));}
        try(var store=open(path,resources,e->{})){finish(store,path,id);}assertEquals(0,resources.usage().leases());
    }
    @Test void corruptionAfterJournalPruningNeverDeletesMoreBytes()throws Exception {
        for(String part:List.of("authority","remaining","selector")) {
            Path path=temp.resolve(part+"/authority");String id=provision(path);
            try(var store=open(path,resources(),e->{if(e.equals("SOURCE_RETIREMENT_FILE_DELETED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
            Path file=path.resolve(part.equals("authority")?MembershipSourceRetirementFiles.FILE:part.equals("selector")?"selector.gsr":"sources/"+id+"/source.gscp");
            byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);
            var before=new V53SourceRetirementPlanTest().inventory(path);var resources=resources();assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{}));assertEquals(before,new V53SourceRetirementPlanTest().inventory(path));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void replacedAuthorityInodeCannotReachJournalPruning()throws Exception {
        Path path=temp.resolve("inode/authority");String id=provision(path);byte[] journal=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,resources(),e->{if(e.equals("SOURCE_RETIREMENT_FORCED")) {
            Path file=path.resolve(MembershipSourceRetirementFiles.FILE),copy=path.getParent().resolve("copy");Files.write(copy,Files.readAllBytes(file));Files.move(copy,file,StandardCopyOption.REPLACE_EXISTING);
        }})){assertThrows(IllegalArgumentException.class,()->store.retireSource(id));}
        assertArrayEquals(journal,Files.readAllBytes(path.resolve("grants.gsr")));assertTrue(Files.exists(path.resolve("sources").resolve(id)));
    }
    @Test void transactionFitsExistingMiscellaneousReservation() {
        assertTrue(MembershipSourceRetirementFiles.MAXIMUM+MembershipJournalRotation.WORST_CASE+2*16384+3*4096<MembershipResources.Unit.MISC.bytes);
    }
    @Test void partialAuthorityRequiresTheStillCompleteOriginalJournalAndSource()throws Exception {
        for(boolean pruned:List.of(false,true)) {
            Path path=temp.resolve("partial-"+pruned+"/authority");String id=provision(path);var resources=resources();
            try(var store=open(path,resources,e->{if(e.equals(pruned?"SOURCE_RETIREMENT_JOURNAL_PRUNED":"SOURCE_RETIREMENT_WRITTEN"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
            Path authority=path.resolve(MembershipSourceRetirementFiles.FILE);byte[] bytes=Files.readAllBytes(authority);Files.write(authority,Arrays.copyOf(bytes,bytes.length-1));
            if(pruned)assertEquals("missing or unbound original source",assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{})).getMessage());
            else try(var store=open(path,resources,e->{})){assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.fixture.source.ballot(22)));finish(store,path,id);}
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void cleanupNeedsNoAdditionalSourceOrImageSlotAtSharedCapacity()throws Exception {
        Path path=temp.resolve("capacity/authority");String id=provision(path);var resources=resources();var external=new ArrayList<MembershipResources.Lease>();
        for(int i=0;i<2;i++){external.add(resources.reserve(MembershipResources.Unit.SOURCE,"external-"+i,1));external.add(resources.reserve(MembershipResources.Unit.APPLICATION,"external-"+i,1));}
        try(var store=open(path,resources,e->{})) {
            assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.SOURCE));assertEquals(7,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            store.retireSource(id);assertEquals(5,resources.usage().counts().get(MembershipResources.Unit.SOURCE));assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }
        assertEquals(4,resources.usage().leases());external.forEach(MembershipResources.Lease::close);assertEquals(0,resources.usage().leases());
    }
    @Test void unresolvedOriginalTailSurvivesActualCleanupAndReopen()throws Exception {
        var tail=new V53CurrentGenerationFixture(3,0,true);Path path=temp.resolve("tail");tail.provision(path);var helper=new V53SourceRetirementPlanTest();String id;
        var resources=resources();
        try(var store=MembershipGrantJournal.openReclaiming(path,tail.root(),V53DeclarationsTest.node(1),resources,tail::verify,e->{})) {
            helper.floor(store,temp.resolve("peers"),tail);id=helper.basis(store,tail,20);helper.basis(store,tail,21);var before=protectedFiles(path,id);
            store.retireSource(id);assertEquals(before,protectedFiles(path,id));assertEquals(tail.accepted,store.currentOwnedTail().orElseThrow().record());
        }
        try(var store=MembershipGrantJournal.openReclaiming(path,tail.root(),V53DeclarationsTest.node(1),resources,tail::verify,e->{})){assertEquals(tail.accepted,store.currentOwnedTail().orElseThrow().record());}assertEquals(0,resources.usage().leases());
    }
    @Test void higherVolatileObservationIsNotLostByTheRetirementRotation()throws Exception {
        Path path=temp.resolve("fence/authority");String id=provision(path);MembershipGrantJournal[] ref={null};
        try(var store=open(path,resources(),e->{if(e.equals("JOURNAL_ROTATION_FORCED"))ref[0].observeCurrent(f.fixture.source.ballot(999));})) {
            ref[0]=store;store.retireSource(id);
            assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.fixture.source.ballot(22))).getMessage());
        }
        try(var store=open(path,resources(),e->{})){assertEquals(21L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
    }
    @Test void wellFramedForeignSelectorCannotResumeDeletion()throws Exception {
        Path path=temp.resolve("foreign/authority");String id=provision(path);
        try(var store=open(path,resources(),e->{if(e.equals("SOURCE_RETIREMENT_JOURNAL_PRUNED"))throw new IOException("cut");})){assertThrows(IOException.class,()->store.retireSource(id));}
        var original=new MembershipSourceRetirementFiles(path).decision().orElseThrow();var record=new TreeMap<>(original.record().value());record.put("selector","00".repeat(32));
        var foreign=new MembershipSourceRetirementFiles.Decision(decode(encode("records","RETIREMENT",record),"records","RETIREMENT"),original.promise(),original.basis(),original.capsule());
        Files.write(path.resolve(MembershipSourceRetirementFiles.FILE),foreign.bytes());var before=new V53SourceRetirementPlanTest().inventory(path);var resources=resources();
        assertEquals("source retirement authority context changed",assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{})).getMessage());
        assertEquals(before,new V53SourceRetirementPlanTest().inventory(path));assertEquals(0,resources.usage().leases());
    }

}
