package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53JournalBackpressureTest {
    @TempDir Path temp;
    final V53CurrentGenerationFixture fixture=new V53CurrentGenerationFixture(3,0,false);
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipGrantJournal open(Path path,int maximum,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipGrantJournal.openMaintenance(path,fixture.root(),V53DeclarationsTest.node(1),resources(),fixture::verify,maximum,cut);
    }
    void provision(Path path)throws Exception {new V53JournalRotationTest().provision(path);}
    int ceiling(Path path)throws Exception{return Math.toIntExact(Files.size(path.resolve("grants.gsr")))+MembershipGrantJournal.RESERVATION-1;}
    void bloat(Path path,int first,int count)throws Exception {
        // Already complete promise-only fixture frames are sealed by the real open.
        var out=new java.io.ByteArrayOutputStream();
        for(int i=first;i<first+count;i++)out.writeBytes(encode("records","PROMISE",Map.of("root",fixture.root().manifestDigest(),
                "view",fixture.admitted.context.authority(),"ballot",fixture.fixture.source.ballot(i),"basisId",UUID.randomUUID().toString())));
        Files.write(path.resolve("grants.gsr"),out.toByteArray(),StandardOpenOption.APPEND);
    }
    @Test void exhaustedGrantCompactsOnceThenPersistsOriginalBasis()throws Exception {
        Path path=temp.resolve("grant/authority");provision(path);int maximum=ceiling(path);int[] rotations={0};
        byte[] basis;
        try(var store=open(path,maximum,e->{if(e.equals("JOURNAL_ROTATION_RENAMED"))rotations[0]++;})) {
            basis=store.prepareCurrent(fixture.fixture.source.ballot(107)).bytes();assertEquals(1,rotations[0]);
            assertArrayEquals(basis,store.prepareCurrent(fixture.fixture.source.ballot(107)).bytes());assertEquals(1,rotations[0]);
            assertTrue(Files.size(path.resolve("grants.gsr"))<=maximum);
        }
        try(var store=open(path,maximum,e->{})){assertArrayEquals(basis,store.originalBasis().orElseThrow().bytes());}
    }
    @Test void enoughCapacityDoesNotRunCompaction()throws Exception {
        Path path=temp.resolve("room/authority");provision(path);int[] rotations={0};
        try(var store=open(path,MembershipGrantJournal.MAXIMUM,e->{if(e.startsWith("JOURNAL_ROTATION"))rotations[0]++;})) {
            store.prepareCurrent(fixture.fixture.source.ballot(107));assertEquals(0,rotations[0]);
        }
    }
    @Test void noReclaimableBytesRefusesWithoutRetryLoopOrNewPromise()throws Exception {
        Path path=temp.resolve("none");fixture.provision(path);
        try(var store=open(path,MembershipGrantJournal.MAXIMUM,e->{})){store.prepareCurrent(fixture.fixture.source.ballot(20));}
        byte[] bytes=Files.readAllBytes(path.resolve("grants.gsr"));int[] events={0};
        try(var store=open(path,ceiling(path),e->{if(e.startsWith("JOURNAL_ROTATION"))events[0]++;})) {
            var error=assertThrows(MembershipOperationException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(21)));
            assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());
            assertEquals(20L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));assertEquals(0,events[0]);
        }
        assertArrayEquals(bytes,Files.readAllBytes(path.resolve("grants.gsr")));
    }
    @Test void occupiedGenerationCannotBeDeletedToMakeJournalRoom()throws Exception {
        Path path=temp.resolve("occupied/authority");Files.createDirectory(path.getParent());V53RetirementWorker.provision(path,3,0);
        for(int i=101;i<=106;i++)new V53JournalRotationTest().incomplete(path,i);
        byte[] before=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,ceiling(path),e->{})) {assertThrows(MembershipOperationException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(107)));}
        assertArrayEquals(before,Files.readAllBytes(path.resolve("grants.gsr")));assertTrue(Files.exists(path.resolve("generations/a/generation.gsr")));
    }
    @Test void interruptedAutomaticRotationDoesNotAttemptNewGrantUntilRecovery()throws Exception {
        Path path=temp.resolve("crash/authority");provision(path);int maximum=ceiling(path);byte[] original=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=open(path,maximum,e->{if(e.equals("JOURNAL_ROTATION_FORCED"))throw new IOException("cut");})) {
            assertThrows(IOException.class,()->store.prepareCurrent(fixture.fixture.source.ballot(107)));
        }
        assertArrayEquals(original,Files.readAllBytes(path.resolve("grants.gsr")));
        try(var store=open(path,maximum,e->{})) {
            assertEquals(106L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));
            store.prepareCurrent(fixture.fixture.source.ballot(107));
        }
    }
    @Test void higherObservationDuringCompactionStillPreventsOldGrant()throws Exception {
        Path path=temp.resolve("fence/authority");provision(path);MembershipGrantJournal[] ref={null};int maximum=ceiling(path);
        try(var store=open(path,maximum,e->{if(e.equals("JOURNAL_ROTATION_FORCED"))ref[0].observeCurrent(fixture.fixture.source.ballot(999));})) {
            ref[0]=store;assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,
                    ()->store.prepareCurrent(fixture.fixture.source.ballot(107))).getMessage());
        }
        try(var store=open(path,maximum,e->{})){assertEquals(106L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
    }
    @Test void selectionAdmissionUsesTheSameBoundedCompaction()throws Exception {
        Path path=temp.resolve("selection");fixture.provision(path);bloat(path,11,80);
        try(var store=open(path,MembershipGrantJournal.MAXIMUM,e->{})){store.prepareCurrent(fixture.fixture.source.ballot(100));}
        var f=new V53GenerationInstallFixture(3,0,0,false);int maximum;Decoded expected;
        try(var store=open(path,MembershipGrantJournal.MAXIMUM,e->{})) {
            var offered=f.offers(store,100);expected=new MembershipSelection.Campaign(offered.getFirst()).select(offered,List.of()).selected();
            maximum=Math.toIntExact(Files.size(path.resolve("grants.gsr")))+expected.bytes().length-1;
        }
        assertTrue(maximum>=MembershipGrantJournal.RESERVATION);int[] rotations={0};
        try(var store=open(path,maximum,e->{if(e.equals("JOURNAL_ROTATION_RENAMED"))rotations[0]++;})) {
            assertArrayEquals(expected.bytes(),store.selectCurrent(f.offers(store,100),List.of()).bytes());assertEquals(1,rotations[0]);
        }
    }
    @Test void certificateFenceAndAdoptionCompactBeforeTheirPromiseWrite()throws Exception {
        for(boolean install:List.of(false,true)) {
            Path path=temp.resolve("adoption-"+install);fixture.provision(path);bloat(path,11,80);
            var f=new V53AdoptionFenceFixture(3,6);var cert=f.reprove(6,1000);
            for(Object row:list(f.remote.capsule.get("items"))) {var item=object(row);if(item.get("certificate")!=null)item.put("certificate",cert.digest());}
            f.owned.addAll(f.remote.source.owned);
            var promise=encode("records","PROMISE",V53ContextFixture.map("root",fixture.root().manifestDigest(),"view",cert.value().get("authority"),"ballot",cert.value().get("ballot"),"basisId",null));
            int maximum=Math.toIntExact(Files.size(path.resolve("grants.gsr")))+promise.length-1;assertTrue(maximum>=MembershipGrantJournal.RESERVATION);int[] rotations={0};
            try(var store=MembershipGrantJournal.openMaintenance(path,fixture.root(),V53DeclarationsTest.node(1),resources(),
                    (r,p,images)->MembershipCapsule.verify(r,p,images,f.owned),maximum,e->{if(e.equals("JOURNAL_ROTATION_RENAMED"))rotations[0]++;})) {
                if(install)store.adoptCurrent(f.remote.packet(),f.remote.source.images,List.of());
                else store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of());
                assertEquals(1000L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));assertEquals(1,rotations[0]);
            }
        }
    }
}
