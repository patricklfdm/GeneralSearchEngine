package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.map;

class V53BallotAllocatorTest {
    @TempDir Path temp;
    Path create(String name,int size) throws Exception { Path path=temp.resolve(name); V53BallotAllocatorWorker.provision(path,size); return path; }
    MembershipRoot root(int size) { return V53BallotAllocatorWorker.root(new V53ContextFixture(size,"REPLACE")); }
    MembershipBallotAllocator open(Path path,int size) throws Exception { return MembershipBallotAllocator.open(path,root(size),V53DeclarationsTest.node(1)); }
    byte[] allocator(int size,long counter) { return encode("records","ALLOCATOR",map("counter",counter,"node","node-1","root",root(size).manifestDigest())); }
    Map<String,String> inventory(Path path) throws IOException {
        var result=new TreeMap<String,String>();
        try(var stream=Files.list(path)) { for(Path file:stream.toList()) result.put(file.getFileName().toString(),hash(Files.readAllBytes(file))); }
        return result;
    }
    @Test void countersSurviveReopenAndJumpBeyondObservedBoundsForAllInitialSizes() throws Exception {
        for(int size:List.of(3,4,5)) {
            Path path=create("size-"+size,size);
            try(var store=open(path,size)) { assertEquals(0,store.counter()); assertEquals(1,store.reserve(0)); assertEquals(41,store.reserve(40)); }
            try(var store=open(path,size)) { assertEquals(41,store.counter()); assertEquals(42,store.reserve(1)); }
            assertEquals(42,number(decode(Files.readAllBytes(path.resolve("allocator.gsr")),"records","ALLOCATOR").value().get("counter")));
            assertEquals(5,inventory(path).size());
        }
    }
    @Test void exclusiveOwnerAndClosedHandleCannotAllocate() throws Exception {
        Path path=create("owner",3);var store=open(path,3);var before=inventory(path);
        assertThrows(RuntimeException.class,()->open(path,3));assertEquals(before,inventory(path));
        store.close();store.close();assertThrows(IllegalArgumentException.class,()->store.reserve(0));
        try(var next=open(path,3)) {assertEquals(1,next.reserve(0));}
    }
    @Test void incompleteOrForeignAuthorityNeverCreatesOrRepairsFiles() throws Exception {
        for(String kind:List.of("missing-root","missing-counter","missing-lock","legacy","foreign-node","unknown","oversized","genesis")) {
            Path path=create(kind,3);
            switch(kind) {
                case "missing-root" -> Files.delete(path.resolve("root.gsr"));
                case "missing-counter" -> Files.delete(path.resolve("allocator.gsr"));
                case "missing-lock" -> Files.delete(path.resolve("replica.lock"));
                case "legacy" -> {byte[] bytes=Files.readAllBytes(path.resolve("root.gsr"));ByteBuffer.wrap(bytes).putShort(6,(short)2);Files.write(path.resolve("root.gsr"),bytes);}
                case "foreign-node" -> Files.write(path.resolve("node.gsr"),encode("records","NODE",map("root",root(3).manifestDigest(),"identity",V53ContextFixture.member(2))));
                case "unknown" -> Files.write(path.resolve("manifest.gsr"),new byte[]{1});
                case "oversized" -> Files.write(path.resolve("allocator.gsr"),new byte[4097]);
                case "genesis" -> {byte[] bytes=Files.readAllBytes(path.resolve("genesis.gsr"));bytes[bytes.length-1]^=1;Files.write(path.resolve("genesis.gsr"),bytes);}
            }
            var before=inventory(path);assertThrows(Exception.class,()->open(path,3),kind);assertEquals(before,inventory(path));
        }
        Path absent=temp.resolve("absent");assertThrows(Exception.class,()->open(absent,3));assertFalse(Files.exists(absent));
    }
    @Test void fullRootAndNodeIdentityArePinnedBeforeAnyWrite() throws Exception {
        Path path=create("identity",3);var before=inventory(path);var expected=root(3);
        var wrong=new MembershipRoot(expected.groupId(),new UUID(22,33),expected.manifestDigest());
        assertThrows(IllegalArgumentException.class,()->MembershipBallotAllocator.open(path,wrong,V53DeclarationsTest.node(1)));
        assertThrows(IllegalArgumentException.class,()->MembershipBallotAllocator.open(path,expected,V53DeclarationsTest.node(2)));
        assertEquals(before,inventory(path));
    }
    @Test void linkedPathsAndReplacedOwnerInodesFailClosed() throws Exception {
        Path path=create("paths",3);Path alias=temp.resolve("alias");Files.createSymbolicLink(alias,path);
        var before=inventory(path);assertThrows(Exception.class,()->open(alias,3));assertEquals(before,inventory(path));
        Files.createLink(temp.resolve("counter-alias"),path.resolve("allocator.gsr"));
        assertThrows(Exception.class,()->open(path,3));Files.delete(temp.resolve("counter-alias"));
        try(var store=open(path,3)) {
            Files.move(path.resolve("replica.lock"),temp.resolve("old-lock"));Files.createFile(path.resolve("replica.lock"));
            assertThrows(Exception.class,()->store.reserve(0));assertFalse(Files.exists(path.resolve("allocator.pending.gsr")));
            assertThrows(IllegalArgumentException.class,()->store.reserve(0));
        }
    }
    @Test void completePendingReservationIsBurnedAndInvalidPendingIsRetained() throws Exception {
        Path path=create("pending",3);Files.write(path.resolve("allocator.pending.gsr"),allocator(3,50));
        try(var store=open(path,3)) {assertEquals(50,store.counter());assertEquals(51,store.reserve(0));}
        for(byte[] bad:List.of(new byte[0],new byte[]{1,2},allocator(3,51),allocator(4,52))) {
            Files.write(path.resolve("allocator.pending.gsr"),bad);var before=inventory(path);
            assertThrows(Exception.class,()->open(path,3));assertEquals(before,inventory(path));
        }
    }
    @Test void failureAtEachPersistenceBoundaryPoisonsHandleAndPreservesRestartDecision() throws Exception {
        var points=List.of("ALLOCATOR_BEFORE_WRITE","ALLOCATOR_CREATED","ALLOCATOR_WRITTEN","ALLOCATOR_FORCED",
                "ALLOCATOR_RENAMED","ALLOCATOR_DIRECTORY_FORCED","ALLOCATOR_BEFORE_RETURN");
        for(String point:points) {
            Path path=create(point,3);var observed=new ArrayList<String>();
            try(var store=MembershipBallotAllocator.open(path,root(3),V53DeclarationsTest.node(1),event->{
                observed.add(event);if(event.equals(point))throw new IOException("injected "+point);
            })) {
                assertThrows(IOException.class,()->store.reserve(9));assertEquals(point,observed.getLast());
                assertThrows(IllegalArgumentException.class,()->store.reserve(0));
            }
            if(point.equals("ALLOCATOR_CREATED")) {var before=inventory(path);assertThrows(Exception.class,()->open(path,3));assertEquals(before,inventory(path));}
            else try(var store=open(path,3)) {assertEquals(point.equals("ALLOCATOR_BEFORE_WRITE")?0:10,store.counter());assertEquals(point.equals("ALLOCATOR_BEFORE_WRITE")?1:11,store.reserve(0));}
        }
    }
    @Test void exhaustionAndInvalidObservationLeaveBytesUnchanged() throws Exception {
        Path path=create("limit",3);
        try(var store=open(path,3)) {
            assertEquals(MembershipBallotAllocator.MAX,store.reserve(MembershipBallotAllocator.MAX-1));var before=inventory(path);
            var error=assertThrows(MembershipOperationException.class,()->store.reserve(0));
            assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,error.reason());
            assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,error.outcome());
            assertThrows(IllegalArgumentException.class,()->store.reserve(Long.MAX_VALUE));assertEquals(before,inventory(path));
        }
        try(var store=open(path,3)) {assertEquals(MembershipBallotAllocator.MAX,store.counter());}
    }
    @Test void interruptedRecoveryReleasesOwnerAndNeverReusesCompletePendingCounter() throws Exception {
        for(String point:List.of("RECOVERY_PENDING_FORCED","RECOVERY_RENAMED","RECOVERY_DIRECTORY_FORCED")) {
            Path path=create(point,3);Files.write(path.resolve("allocator.pending.gsr"),allocator(3,7));
            assertThrows(IOException.class,()->MembershipBallotAllocator.open(path,root(3),V53DeclarationsTest.node(1),event->{
                if(event.equals(point))throw new IOException("injected recovery failure");
            }));
            try(var store=open(path,3)) {assertEquals(7,store.counter());assertEquals(8,store.reserve(0));}
        }
    }
    @Test void successfulReturnFollowsBothFileAndDirectoryForces() throws Exception {
        Path path=create("order",3);var events=new ArrayList<String>();
        try(var store=MembershipBallotAllocator.open(path,root(3),V53DeclarationsTest.node(1),events::add)) {assertEquals(1,store.reserve(0));}
        assertEquals(List.of("ALLOCATOR_BEFORE_WRITE","ALLOCATOR_CREATED","ALLOCATOR_WRITTEN","ALLOCATOR_FORCED",
                "ALLOCATOR_RENAMED","ALLOCATOR_DIRECTORY_FORCED","ALLOCATOR_BEFORE_RETURN"),events);
    }
}
