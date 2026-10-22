package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53JournalRotationTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("JOURNAL_ROTATION_CREATED","JOURNAL_ROTATION_WRITTEN","JOURNAL_ROTATION_FORCED",
            "JOURNAL_ROTATION_RENAMED","JOURNAL_ROTATION_PARENT_FORCED","JOURNAL_ROTATION_BEFORE_RETURN");
    final V53CurrentGenerationFixture fixture=new V53CurrentGenerationFixture(3,0,false);
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openRotating(path,fixture.root(),V53DeclarationsTest.node(1),resources,fixture::verify,cut);
    }
    void incomplete(Path path,int ballot)throws Exception {
        try(var store=open(path,resources(),e->{if(e.equals("PROMISE_FORCED"))throw new java.io.IOException("incomplete");})) {
            assertThrows(java.io.IOException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(ballot)));
        }
    }
    void provision(Path path)throws Exception {
        Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,0);
        try(var store=open(path,resources(),e->{})){store.retireInactive();}
        for(int i=101;i<=106;i++)incomplete(path,i);
    }
    Map<String,byte[]> protectedFiles(Path path)throws Exception {
        var files=new TreeMap<String,byte[]>();
        try(var all=Files.walk(path)){for(Path file:all.filter(Files::isRegularFile).toList()) {
            String name=path.relativize(file).toString();if(!Set.of("grants.gsr",MembershipJournalRotation.PENDING).contains(name))files.put(name,Files.readAllBytes(file));
        }}return files;
    }
    void unchanged(Map<String,byte[]> before,Path path)throws Exception {
        var after=protectedFiles(path);assertEquals(before.keySet(),after.keySet());for(String name:before.keySet())assertArrayEquals(before.get(name),after.get(name),name);
    }
    @Test void compactionPreservesFloorCurrentOriginalBasisAndHighestIncompleteGrant()throws Exception {
        Path path=temp.resolve("complete/authority");provision(path);byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));var files=protectedFiles(path);var resources=resources();
        try(var store=open(path,resources,e->{})) {
            byte[] highest=store.promised().orElseThrow().bytes();String compact=store.rotateJournal();assertTrue(Files.size(path.resolve("grants.gsr"))<before.length);
            assertArrayEquals(highest,store.promised().orElseThrow().bytes());assertEquals(compact,store.rotateJournal());
            assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(106)));
        }
        unchanged(files,path);assertEquals(0,resources.usage().leases());
        try(var store=open(path,resources,e->{})) {
            assertEquals(106L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));store.prepareCurrent(fixture.fixture.source.ballot(107));
            byte[] original=store.originalBasis().orElseThrow().bytes();store.rotateJournal();assertArrayEquals(original,store.prepareCurrent(fixture.fixture.source.ballot(107)).bytes());
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void everyWriteBoundaryReopensWithoutLosingProtectedAuthority()throws Exception {
        for(String point:CUTS) {
            Path path=temp.resolve(point+"/authority");provision(path);var protectedFiles=protectedFiles(path);var resources=resources();
            try(var store=open(path,resources,e->{if(e.equals(point))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::rotateJournal);}
            try(var store=open(path,resources,e->{})){store.rotateJournal();assertEquals(106L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
            unchanged(protectedFiles,path);assertFalse(Files.exists(path.resolve(MembershipJournalRotation.PENDING)));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void recoveryMayBeInterruptedAgainBeforeAtomicReplacement()throws Exception {
        Path path=temp.resolve("repeat/authority");provision(path);byte[] old=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,resources(),e->{if(e.equals("JOURNAL_ROTATION_CREATED"))throw new java.io.IOException("first");})){assertThrows(java.io.IOException.class,store::rotateJournal);}
        assertEquals(0,Files.size(path.resolve(MembershipJournalRotation.PENDING)));
        assertThrows(java.io.IOException.class,()->open(path,resources(),e->{if(e.equals("JOURNAL_ROTATION_FORCED"))throw new java.io.IOException("again");}));
        assertArrayEquals(old,Files.readAllBytes(path.resolve("grants.gsr")));
        try(var store=open(path,resources(),e->{})){store.rotateJournal();}
        assertTrue(Files.size(path.resolve("grants.gsr"))<old.length);
    }
    @Test void changedPendingBytesCannotBecomeTheJournal()throws Exception {
        Path path=temp.resolve("wrong/authority");provision(path);byte[] old=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,resources(),e->{if(e.equals("JOURNAL_ROTATION_WRITTEN"))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::rotateJournal);}
        Path pending=path.resolve(MembershipJournalRotation.PENDING);byte[] bytes=Files.readAllBytes(pending);bytes[bytes.length-1]^=1;Files.write(pending,bytes);
        var resources=resources();assertThrows(IllegalArgumentException.class,()->open(path,resources,e->{}));assertArrayEquals(old,Files.readAllBytes(path.resolve("grants.gsr")));assertEquals(0,resources.usage().leases());
    }
    @Test void inodeAndSelectorReplacementAreRejectedBeforeRename()throws Exception {
        for(String member:List.of(MembershipJournalRotation.PENDING,"selector.gsr")) {
            Path path=temp.resolve(member+"/authority");provision(path);byte[] old=Files.readAllBytes(path.resolve("grants.gsr"));
            try(var store=open(path,resources(),e->{if(e.equals("JOURNAL_ROTATION_FORCED")) {
                Path target=path.resolve(member),other=path.getParent().resolve("replacement");Files.write(other,Files.readAllBytes(target));Files.move(other,target,StandardCopyOption.REPLACE_EXISTING);
            }})){assertThrows(IllegalArgumentException.class,store::rotateJournal);}
            assertArrayEquals(old,Files.readAllBytes(path.resolve("grants.gsr")));
        }
    }
    @Test void higherVolatileObservationStillFencesAfterRotation()throws Exception {
        Path path=temp.resolve("fencing/authority");provision(path);
        try(var store=open(path,resources(),e->{})) {
            store.observeCurrent(fixture.fixture.source.ballot(999));store.rotateJournal();
            assertEquals(106L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));
            assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(107)));
        }
    }
    @Test void pendingGenerationsAndLegacyOpenCannotBypassRotation()throws Exception {
        Path path=temp.resolve("pending/authority");Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,0);
        try(var store=open(path,resources(),e->{})){assertThrows(IllegalArgumentException.class,store::rotateJournal);store.retireInactive();}
        incomplete(path,101);incomplete(path,102);
        try(var store=open(path,resources(),e->{if(e.equals("JOURNAL_ROTATION_CREATED"))throw new java.io.IOException("cut");})){assertThrows(java.io.IOException.class,store::rotateJournal);}
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openRetirement(path,fixture.root(),V53DeclarationsTest.node(1),resources(),fixture::verify,e->{}));
        try(var store=open(path,resources(),e->{})){store.rotateJournal();}
    }
    @Test void allSixOriginalSourcesRemainCountedAndByteIdentical()throws Exception {
        Path path=temp.resolve("six-sources");fixture.provision(path);for(int i=11;i<=16;i++)incomplete(path,i);
        var resources=resources();
        try(var store=open(path,resources,e->{})) {
            for(int i=20;i<=25;i++)store.prepareCurrent(fixture.fixture.source.ballot(i));
            assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertEquals(7,resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            var before=protectedFiles(path);long bytes=Files.size(path.resolve("grants.gsr"));byte[] basis=store.originalBasis().orElseThrow().bytes();
            store.rotateJournal();assertTrue(Files.size(path.resolve("grants.gsr"))<bytes);unchanged(before,path);
            assertArrayEquals(basis,store.prepareCurrent(fixture.fixture.source.ballot(25)).bytes());
            assertEquals(6,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
            assertThrows(MembershipOperationException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(26)));
        }
        assertEquals(0,resources.usage().leases());
        try(var store=open(path,resources,e->{})){assertEquals(25L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
        assertEquals(0,resources.usage().leases());
    }
    @Test void anInterruptedSourceCaptureRetainsItsOriginalPromiseWithoutABasis()throws Exception {
        Path path=temp.resolve("captured-without-basis");fixture.provision(path);
        try(var store=open(path,resources(),e->{if(e.equals("SOURCE_DIRECTORY_FORCED"))throw new java.io.IOException("captured");})) {
            assertThrows(java.io.IOException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(20)));
        }
        incomplete(path,21);var resources=resources();
        try(var store=open(path,resources,e->{})) {
            store.prepareCurrent(fixture.fixture.source.ballot(22));var before=protectedFiles(path);long bytes=Files.size(path.resolve("grants.gsr"));
            store.rotateJournal();unchanged(before,path);assertTrue(Files.size(path.resolve("grants.gsr"))<bytes);
            assertEquals(2,resources.usage().counts().get(MembershipResources.Unit.SOURCE));
        }
        try(var store=open(path,resources,e->{})){assertEquals(22L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
        assertEquals(0,resources.usage().leases());
    }
    @Test void compactBoundsAndProtectedPromiseChecksAreExplicit()throws Exception {
        Path path=temp.resolve("plan/authority");provision(path);byte[] bytes=Files.readAllBytes(path.resolve("grants.gsr"));
        String active=decode(Files.readAllBytes(path.resolve("generations/b/generation.gsr")),"records","GENERATION").value().get("promise").toString();
        Set<String> retained;
        try(var paths=Files.list(path.resolve("sources"))){retained=paths.map(p->p.getFileName().toString()).collect(java.util.stream.Collectors.toSet());}
        assertEquals("rotation protected promise absent",assertThrows(IllegalArgumentException.class,
                ()->MembershipJournalRotation.compact(bytes,Set.of("00".repeat(32)),retained)).getMessage());
        assertEquals("torn rotation journal body",assertThrows(IllegalArgumentException.class,
                ()->MembershipJournalRotation.compact(Arrays.copyOf(bytes,bytes.length-1),Set.of(active),retained)).getMessage());
        assertEquals(565248,MembershipJournalRotation.WORST_CASE);assertTrue(MembershipJournalRotation.WORST_CASE<MembershipJournalRotation.MAXIMUM);
        assertTrue(MembershipJournalRotation.MAXIMUM+65536+2*16384+3*4096<MembershipResources.Unit.MISC.bytes);
    }
}
