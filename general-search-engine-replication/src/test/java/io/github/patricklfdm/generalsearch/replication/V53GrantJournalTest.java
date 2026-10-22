package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

class V53GrantJournalTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("PROMISE_BEFORE_WRITE","PROMISE_WRITTEN","PROMISE_FORCED",
            "BASIS_BEFORE_WRITE","BASIS_WRITTEN","BASIS_FORCED","GRANT_BEFORE_RETURN");
    Path create(String name,int size) throws Exception {
        Path path=temp.resolve(name);V53BallotAllocatorWorker.provision(path,size);AdmissionPaths.write(path.resolve(MembershipGrantJournal.FILE),new byte[0]);return path;
    }
    MembershipRoot root(int size) {return V53BallotAllocatorWorker.root(new V53ContextFixture(size,"REPLACE"));}
    MembershipGrantJournal open(Path path,int size) throws Exception {return MembershipGrantJournal.open(path,root(size),V53DeclarationsTest.node(1));}
    MembershipGrantJournal open(Path path,MembershipBallotAllocator.Cut cut) throws Exception {
        return MembershipGrantJournal.open(path,root(3),V53DeclarationsTest.node(1),MembershipGrantJournal.MAXIMUM,cut);
    }
    MembershipCapsule source(int size,int through) {return new V53CapsuleFixture(size,"REPLACE",through).verify();}
    Map<String,Object> ballot(long n) {return new V53ContextFixture(3,"REPLACE").ballot(n);}
    byte[] bytes(Path path) throws Exception {return Files.readAllBytes(path.resolve(MembershipGrantJournal.FILE));}

    @Test void originalBasisSurvivesProgressDuplicateAndReopenForEveryInitialSize() throws Exception {
        for(int size:List.of(3,4,5)) {
            Path path=create("size"+size,size);var first=source(size,0);var progressed=source(size,1);Decoded original;byte[] before;
            try(var store=open(path,size)) {
                original=store.prepare(first,ballot(20),null);before=bytes(path);
                assertArrayEquals(original.bytes(),store.prepare(progressed,ballot(20),null).bytes());assertArrayEquals(before,bytes(path));
            }
            try(var store=open(path,size)) {
                assertArrayEquals(original.bytes(),store.prepare(progressed,ballot(20),null).bytes());assertArrayEquals(before,bytes(path));
                assertEquals(21,store.reserveCounter());var next=store.prepare(progressed,ballot(21),null);
                assertNotEquals(original.value().get("basisId"),next.value().get("basisId"));assertEquals(1L,object(next.value().get("cut")).get("index"));
            }
        }
    }
    @Test void interruptionAtEveryForceBoundaryNeverResamplesAnIncompleteOriginalGrant() throws Exception {
        var source=source(3,0);
        for(String point:CUTS) {
            Path path=create(point,3);
            try(var store=open(path,event->{if(event.equals(point))throw new IOException("injected "+point);})) {
                assertThrows(IOException.class,()->store.prepare(source,ballot(20),null));assertThrows(IllegalArgumentException.class,store::originalBasis);
            }
            try(var store=open(path,3)) {
                if(List.of("PROMISE_WRITTEN","PROMISE_FORCED","BASIS_BEFORE_WRITE").contains(point)) {
                    byte[] before=bytes(path);assertThrows(IllegalArgumentException.class,()->store.prepare(source,ballot(20),null));assertArrayEquals(before,bytes(path));
                } else assertNotNull(store.prepare(source,ballot(20),null));
                assertNotNull(store.prepare(source,ballot(21),null));
            }
        }
    }
    @Test void observationFencesWhileTheWriterIsBlockedWithoutWaitingForItsMonitor() throws Exception {
        Path path=create("concurrent",3);var source=source(3,0);var written=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var store=open(path,event->{if(event.equals("PROMISE_WRITTEN")) {
            written.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new IOException("test coordination timeout");}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
        }});var executor=Executors.newSingleThreadExecutor()) {
            Future<?> writer=executor.submit(()->{try{store.prepare(source,ballot(20),null);}catch(IOException error){throw new RuntimeException(error);}});
            try {
                assertTrue(written.await(10,TimeUnit.SECONDS));store.observe(source.context,ballot(21));
            } finally {release.countDown();}
            assertTrue(assertThrows(ExecutionException.class,()->writer.get(10,TimeUnit.SECONDS)).getCause().getMessage().contains("higher ballot"));
        }
        try(var store=open(path,3)) {assertEquals(20L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));assertTrue(store.originalBasis().isEmpty());}
    }
    @Test void higherObservationAtEveryBoundaryPreventsTheOldGrantReturn() throws Exception {
        var source=source(3,0);
        for(String point:CUTS) {
            Path path=create("fence-"+point,3);var holder=new MembershipGrantJournal[1];
            try(var store=open(path,event->{if(event.equals(point))holder[0].observe(source.context,ballot(21));})) {
                holder[0]=store;var error=assertThrows(IllegalArgumentException.class,()->store.prepare(source,ballot(20),null));assertTrue(error.getMessage().contains("higher ballot"));
            }
        }
    }
    @Test void rootWideOrderIncludesProposerAndRejectsStaleLowerRequests() throws Exception {
        Path path=create("order",3);var source=source(3,0);var second=new TreeMap<>(ballot(20));second.put("proposer","node-2");second.put("incarnation",member(2).get("storage"));
        try(var store=open(path,3)) {
            var original=store.prepare(source,ballot(20),null);var integer=new TreeMap<>(ballot(20));integer.put("counter",20);
            assertArrayEquals(original.bytes(),store.prepare(source,integer,null).bytes());
            store.prepare(source,second,null);byte[] before=bytes(path);
            assertThrows(IllegalArgumentException.class,()->store.prepare(source,ballot(20),null));assertArrayEquals(before,bytes(path));
            assertEquals(21,store.reserveCounter());
        }
    }
    @Test void exactConfigurationAndPermanentEligibilityAreRequired() throws Exception {
        Path path=create("view",3);var initial=source(3,0);var later=source(3,7);
        try(var store=open(path,3)) {
            store.prepare(initial,ballot(20),null);byte[] before=bytes(path);
            assertThrows(IllegalArgumentException.class,()->store.prepare(later,ballot(20),null));assertArrayEquals(before,bytes(path));
            var bad=new TreeMap<>(ballot(21));bad.put("incarnation",new UUID(9,9).toString());
            assertThrows(IllegalArgumentException.class,()->store.observe(initial.context,bad));assertArrayEquals(before,bytes(path));
        }
        Path removed=create("removed",3);Files.write(removed.resolve("node.gsr"),encode("records","NODE",map("root",root(3).manifestDigest(),"identity",member(3))));
        Files.write(removed.resolve("allocator.gsr"),encode("records","ALLOCATOR",map("root",root(3).manifestDigest(),"node","node-3","counter",0L)));
        try(var store=MembershipGrantJournal.open(removed,root(3),V53DeclarationsTest.node(3))) {
            assertThrows(IllegalArgumentException.class,()->store.prepare(later,ballot(21),null));assertEquals(0,bytes(removed).length);
        }
    }
    @Test void headroomRefusesBeforePromiseAndKeepsExistingDuplicateAvailable() throws Exception {
        Path path=create("capacity",3);var source=source(3,0);
        try(var store=MembershipGrantJournal.open(path,root(3),V53DeclarationsTest.node(1),MembershipGrantJournal.RESERVATION,event->{})) {
            var original=store.prepare(source,ballot(20),null);byte[] before=bytes(path);
            assertArrayEquals(original.bytes(),store.prepare(source,ballot(20),null).bytes());
            var error=assertThrows(MembershipOperationException.class,()->store.prepare(source,ballot(21),null));
            assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,error.outcome());
            assertArrayEquals(before,bytes(path));assertThrows(IllegalArgumentException.class,()->store.prepare(source,ballot(20),null));
        }
    }
    @Test void frozenTailReferencesRemainExactAndCannotBeSilentlyReplaced() throws Exception {
        Path path=create("tail",3);var f=new V53SelectionFixture(3,"REPLACE",0);var source=f.source("node-1",20,"pending-payload",3);
        try(var store=open(path,3)) {
            String accepted=source.accepted.digest();var original=store.prepare(source.capsule,ballot(20),accepted);
            assertEquals(accepted,original.value().get("accepted"));assertArrayEquals(original.bytes(),store.prepare(source.capsule,ballot(20),null).bytes());
            byte[] before=bytes(path);assertThrows(IllegalArgumentException.class,()->store.prepare(source.capsule,ballot(21),"00".repeat(32)));assertArrayEquals(before,bytes(path));
        }
    }
    @Test void invalidJournalNeverTruncatesOrRepairsAndFailedOpenReleasesTheLock() throws Exception {
        Path path=create("invalid",3);var source=source(3,0);byte[] p,b;
        try(var store=open(path,3)) {b=store.prepare(source,ballot(20),null).bytes();p=store.promised().orElseThrow().bytes();}
        byte[] valid=bytes(path);var wrong=object(mutable(decode(b,"records","BASIS").value()));wrong.put("voter","node-2");
        var corrupt=valid.clone();corrupt[corrupt.length-1]^=1;
        for(byte[] bad:List.of(Arrays.copyOf(valid,valid.length-1),new byte[]{1},corrupt,b,concat(valid,b),concat(valid,p),concat(p,encode("records","BASIS",wrong)))) {
            Files.write(path.resolve(MembershipGrantJournal.FILE),bad);assertThrows(Exception.class,()->open(path,3));assertArrayEquals(bad,bytes(path));
            Files.write(path.resolve(MembershipGrantJournal.FILE),valid);try(var store=open(path,3)){assertArrayEquals(b,store.originalBasis().orElseThrow().bytes());}
        }
        Files.delete(path.resolve(MembershipGrantJournal.FILE));assertThrows(Exception.class,()->open(path,3));assertFalse(Files.exists(path.resolve(MembershipGrantJournal.FILE)));
    }
    static byte[] concat(byte[] a,byte[] b) {byte[] out=Arrays.copyOf(a,a.length+b.length);System.arraycopy(b,0,out,a.length,b.length);return out;}
    @Test void singleOwnerInodeAndCloseRulesApplyToTheCombinedStore() throws Exception {
        Path path=create("owner",3);var source=source(3,0);var store=open(path,3);
        try {
            assertThrows(Exception.class,()->open(path,3));assertThrows(Exception.class,()->MembershipBallotAllocator.open(path,root(3),V53DeclarationsTest.node(1)));
            Files.move(path.resolve(MembershipGrantJournal.FILE),temp.resolve("previous"));Files.write(path.resolve(MembershipGrantJournal.FILE),new byte[0]);
            assertThrows(Exception.class,()->store.prepare(source,ballot(20),null));assertEquals(0,bytes(path).length);
        } finally {store.close();store.close();}
        assertThrows(IllegalArgumentException.class,store::promised);
    }
}
