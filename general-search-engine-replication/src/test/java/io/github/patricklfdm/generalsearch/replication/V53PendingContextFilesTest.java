package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Private file CAS only. Two actually forced phases share one verified backing source.
 * The supplied guard is conditional: these tests do not authorize an owner transition,
 * source retirement, a new round, a publication ACK, or public READY. */
class V53PendingContextFilesTest {
    @TempDir static Path seedRoot;
    @TempDir Path temp;
    static MembershipRoot root;
    static MembershipIdentity owner;
    static MembershipPendingContext.Context first,second;
    static byte[] rootRecord,firstBytes,secondBytes;
    static final String ACTIVE=MembershipPendingContextFiles.FILE,NEXT=MembershipPendingContextFiles.NEXT;
    static final long LIMIT=MembershipPendingContextFiles.MAXIMUM_METADATA;
    static final List<String> CUTS=List.of("CONTEXT_CANDIDATE_CREATED","CONTEXT_PREFIX_WRITTEN",
            "CONTEXT_CANDIDATE_WRITTEN","CONTEXT_CANDIDATE_FORCED","CONTEXT_CANDIDATE_PARENT_FORCED",
            "CONTEXT_RENAMED","CONTEXT_PARENT_FORCED");
    static final MembershipGenerationFiles.Guard GUARD=()->{};
    static final MembershipBallotAllocator.Cut NO_CUT=e->{};

    @BeforeAll static void actualPhasesAndOneBackingSource()throws Exception {
        var f=new V53RoundStorageTest.Fixture(seedRoot.resolve("owners"));
        byte[] payload;
        try(var encoder=f.f.initial.application.app.encoder()) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(
                    new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(307,"context-files"))));
        }
        var entry=f.entry("DATA",payload);MembershipPendingAccept.Vote accepted;
        try(var store=f.f.open(1)) {
            store.acceptCurrent(entry,payload);
            accepted=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(1).resolve(MembershipPendingAccept.FILE)));
        }
        assertNull(accepted.proof());assertNull(accepted.certificate());
        var phased=V53StagedApplicationTest.certify(f,entry,payload,Set.copyOf(V53StagedApplicationTest.NODES));
        var certified=MembershipPendingAccept.decode(Files.readAllBytes(f.f.node(1).resolve(MembershipPendingAccept.FILE)));
        assertNotNull(certified.certificate());assertArrayEquals(accepted.accept().bytes(),certified.accept().bytes());
        var originals=new TreeMap<String,byte[]>();
        Path generation=f.f.node(1).resolve("generations").resolve((String)accepted.selector().value().get("generation"));
        try(var files=Files.list(generation)) {
            for(Path file:files.toList())originals.put(file.getFileName().toString(),Files.readAllBytes(file));
        }
        var seed=new V53StagedApplicationTest.Seed(f,entry,payload,phased);
        var images=V53StagedApplicationTest.images(seed);
        MembershipSelection.Source backing;Decoded promise;
        try(var store=f.f.open(1)) {
            store.prepareCurrent(V53StagedApplicationTest.nextBallot(seed));
            backing=store.originalSource();promise=store.promised().orElseThrow();
        }
        root=f.f.initial.application.f.f.f.root();owner=V53DeclarationsTest.node(1);
        rootRecord=Files.readAllBytes(f.f.node(1).resolve("root.gsr"));
        MembershipCurrentGeneration.Verifier verifier=(r,p,i)->MembershipCapsule.verify(r,p,i,f.f.observations);
        first=MembershipPendingContext.create(root,owner,accepted.selector(),originals,accepted,promise,backing,images,verifier);
        second=MembershipPendingContext.create(root,owner,certified.selector(),originals,certified,promise,backing,images,verifier);
        firstBytes=MembershipPendingContext.encode(first);secondBytes=MembershipPendingContext.encode(second);
        assertFalse(Arrays.equals(firstBytes,secondBytes));
        assertArrayEquals(accepted.bytes(),MembershipPendingContext.reconstruct(first,root,owner,promise,backing,images,verifier).vote().bytes());
        assertArrayEquals(certified.bytes(),MembershipPendingContext.reconstruct(second,root,owner,promise,backing,images,verifier).vote().bytes());
        assertEquals(0,f.f.resources.usage().leases());
    }

    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    static MembershipResources.Lease journal(MembershipResources resources) {
        return resources.reserve(MembershipResources.Unit.JOURNAL,"context-test-owner",MembershipResources.Unit.JOURNAL.bytes);
    }
    static MembershipPendingContextFiles open(Path directory,MembershipResources resources)throws IOException {
        return new MembershipPendingContextFiles(directory,root,owner,resources,LIMIT);
    }
    Path directory(String name)throws IOException {
        Path result=Files.createDirectory(temp.resolve(name));Files.writeString(result.resolve("owner-sentinel"),"unchanged");return result;
    }
    static Map<String,String> inventory(Path directory)throws IOException {
        var result=new TreeMap<String,String>();try(var files=Files.list(directory)) {
            for(Path file:files.toList()) {
                assertTrue(Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS),"unexpected owner member: "+file);
                result.put(file.getFileName().toString(),hash(Files.readAllBytes(file)));
            }
        }return result;
    }
    static long contextBytes(Path directory)throws IOException {
        long result=0;for(String name:List.of(ACTIVE,NEXT))if(Files.exists(directory.resolve(name)))result+=Files.size(directory.resolve(name));
        return result;
    }
    static void onlyContextAndSentinel(Path directory)throws IOException {
        assertTrue(Set.of(ACTIVE,NEXT,"owner-sentinel").containsAll(inventory(directory).keySet()));
        assertEquals("unchanged",Files.readString(directory.resolve("owner-sentinel")));
        assertTrue(contextBytes(directory)<=2L*MembershipPendingContext.MAXIMUM);
    }
    static void borrowedOnly(MembershipResources resources) {
        assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),resources.usage().counts());
        assertEquals(MembershipResources.Unit.JOURNAL.bytes,resources.usage().metadata());
        assertEquals(0,resources.usage().staging());assertEquals(0,resources.usage().queued());
    }
    static void initialize(Path directory,MembershipResources resources)throws IOException {
        try(var store=open(directory,resources)){assertArrayEquals(firstBytes,store.install(first,null,GUARD,NO_CUT));}
    }
    static void poison(MembershipPendingContextFiles store) {
        assertThrows(IllegalArgumentException.class,store::check);
        assertThrows(IllegalArgumentException.class,store::active);
        assertThrows(IllegalArgumentException.class,store::pending);
    }
    static void replaceInode(Path path)throws IOException {
        Path replacement=path.resolveSibling(path.getFileName()+".replacement");Files.write(replacement,Files.readAllBytes(path));
        Files.move(replacement,path,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
    }

    @Test void everyInitialAndReplacementCutResumesTheExactRequestWithoutAdditionalLeases()throws Exception {
        for(boolean replacement:List.of(false,true))for(String point:CUTS) {
            Path directory=directory((replacement?"replacement-":"initial-")+point);var resources=resources();
            var expected=replacement?second:first;byte[] expectedBytes=replacement?secondBytes:firstBytes;
            byte[] prior=replacement?firstBytes:null;boolean[] hit={false};
            try(var lease=journal(resources)) {
                if(replacement)initialize(directory,resources);
                try(var store=open(directory,resources)) {
                    assertThrows(IOException.class,()->store.install(expected,prior,GUARD,event->{
                        assertTrue(event.startsWith("CONTEXT_"));borrowedOnly(resources);onlyContextAndSentinel(directory);
                        if(!Set.of("CONTEXT_RENAMED","CONTEXT_PARENT_FORCED").contains(event)) {
                            if(replacement)assertArrayEquals(firstBytes,Files.readAllBytes(directory.resolve(ACTIVE)));
                            else assertFalse(Files.exists(directory.resolve(ACTIVE)));
                        }
                        if(event.equals(point)){hit[0]=true;throw new IOException("first context cut");}
                    }));assertTrue(hit[0],point);poison(store);
                }
                borrowedOnly(resources);onlyContextAndSentinel(directory);
                // A second interruption exercises resuming partial bytes and resealing a renamed active.
                String secondCut=Files.exists(directory.resolve(NEXT))?"CONTEXT_CANDIDATE_FORCED":"CONTEXT_ACTIVE_FORCED";
                boolean[] secondHit={false};
                try(var store=open(directory,resources)) {
                    assertEquals(contextBytes(directory),store.bytes());
                    long peak=Files.exists(directory.resolve(NEXT))?(replacement?firstBytes.length:0L)+expectedBytes.length:expectedBytes.length;
                    assertEquals(peak,store.bytes()+store.completionAllowance(expected));
                    assertThrows(IOException.class,()->store.install(expected,prior,GUARD,event->{
                        if(event.equals(secondCut)){secondHit[0]=true;throw new IOException("second context cut");}
                    }));assertTrue(secondHit[0],point);poison(store);
                }
                try(var store=open(directory,resources)) {
                    assertArrayEquals(expectedBytes,store.install(expected,prior,GUARD,NO_CUT));store.check();
                    assertArrayEquals(expectedBytes,store.activeBytes().orElseThrow());assertFalse(store.pending());
                    assertEquals(expectedBytes.length,store.bytes());assertEquals(0,store.completionAllowance(expected));
                }
                assertFalse(Files.exists(directory.resolve(NEXT)));onlyContextAndSentinel(directory);borrowedOnly(resources);
            }
            assertEquals(0,resources.usage().leases());assertEquals(0,resources.usage().metadata());
        }
    }

    @Test void exactReplayOnlyResealsAndAllReturnedBytesAreDefensive()throws Exception {
        Path directory=directory("replay");var resources=resources();var events=new ArrayList<String>();
        try(var lease=journal(resources);var store=open(directory,resources)) {
            assertTrue(store.active().isEmpty());assertEquals(firstBytes.length,store.completionAllowance(first));
            byte[] installed=store.install(first,null,GUARD,events::add);installed[0]^=1;
            assertEquals(CUTS,events);events.clear();var before=inventory(directory);
            byte[] exposed=store.activeBytes().orElseThrow();exposed[0]^=1;
            assertArrayEquals(firstBytes,MembershipPendingContext.encode(store.active().orElseThrow()));
            assertArrayEquals(firstBytes,store.install(first,null,GUARD,events::add));
            assertEquals(List.of("CONTEXT_ACTIVE_FORCED","CONTEXT_ACTIVE_PARENT_FORCED"),events);
            assertEquals(before,inventory(directory));assertArrayEquals(firstBytes,store.activeBytes().orElseThrow());
            store.close();assertThrows(IllegalArgumentException.class,store::check);borrowedOnly(resources);
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void wrongPriorAndConflictingCandidateRefuseWithoutChangingTheOriginalBytes()throws Exception {
        var resources=resources();
        try(var lease=journal(resources)) {
            for(int variant=0;variant<3;variant++) {
                Path directory=directory("prior-"+variant);if(variant<2)initialize(directory,resources);
                byte[] wrongPrior=variant==0?null:secondBytes;
                var before=inventory(directory);
                try(var store=open(directory,resources)) {
                    assertThrows(IllegalArgumentException.class,()->store.install(second,wrongPrior,GUARD,e->fail("wrong prior mutated")));
                    assertEquals(before,inventory(directory));poison(store);
                }
            }
            for(String point:List.of("CONTEXT_PREFIX_WRITTEN","CONTEXT_CANDIDATE_FORCED")) {
                Path directory=directory(point);initialize(directory,resources);
                try(var store=open(directory,resources)) {
                    assertThrows(IOException.class,()->store.install(second,firstBytes,GUARD,e->{if(e.equals(point))throw new IOException("candidate");}));
                }
                var before=inventory(directory);
                try(var store=open(directory,resources)) {
                    assertThrows(IllegalArgumentException.class,()->store.completionAllowance(first));
                    assertThrows(IllegalArgumentException.class,()->store.install(first,firstBytes,GUARD,e->fail("conflicting candidate mutated")));
                    assertEquals(before,inventory(directory));poison(store);
                }
                try(var store=open(directory,resources)){assertArrayEquals(secondBytes,store.install(second,firstBytes,GUARD,NO_CUT));}
                borrowedOnly(resources);
            }
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void corruptActiveCannotBeRepairedByACompleteCandidateAndMalformedCandidatesAreReadOnlyFailures()throws Exception {
        var resources=resources();
        try(var lease=journal(resources)) {
            for(String kind:List.of("active","complete-candidate","prefix-header","prefix-length","oversize")) {
                Path directory=directory(kind);initialize(directory,resources);
                byte[] corrupt=secondBytes.clone();corrupt[16]^=1;
                switch(kind) {
                    case "active" -> {Files.write(directory.resolve(ACTIVE),corrupt);Files.write(directory.resolve(NEXT),secondBytes);}
                    case "complete-candidate" -> Files.write(directory.resolve(NEXT),corrupt);
                    case "prefix-header" -> {corrupt=Arrays.copyOf(secondBytes,12);corrupt[0]^=1;Files.write(directory.resolve(NEXT),corrupt);}
                    case "prefix-length" -> {corrupt=Arrays.copyOf(secondBytes,16);Arrays.fill(corrupt,12,16,(byte)0xff);Files.write(directory.resolve(NEXT),corrupt);}
                    case "oversize" -> Files.write(directory.resolve(NEXT),new byte[MembershipPendingContext.MAXIMUM+1]);
                    default -> fail("unknown mutation");
                }
                var before=inventory(directory);
                if(kind.equals("oversize")) {
                    var failure=assertThrows(ReplicationException.class,()->open(directory,resources));
                    assertEquals(ReplicationException.Reason.CAPACITY_EXCEEDED,failure.reason());
                } else assertThrows(IllegalArgumentException.class,()->open(directory,resources));
                assertEquals(before,inventory(directory));borrowedOnly(resources);
            }
            Path prefix=directory("untrusted-body-prefix");initialize(prefix,resources);
            byte[] damaged=Arrays.copyOf(secondBytes,secondBytes.length/2);damaged[damaged.length-1]^=1;Files.write(prefix.resolve(NEXT),damaged);
            var before=inventory(prefix);
            try(var store=open(prefix,resources)) {
                assertTrue(store.pending());assertThrows(IllegalArgumentException.class,()->store.install(second,firstBytes,GUARD,NO_CUT));
                assertEquals(before,inventory(prefix));poison(store);
            }
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void changedRootNodeAndStorageCannotOpenOrInstallAnotherOwnersContext()throws Exception {
        Path directory=directory("identity");var resources=resources();
        try(var lease=journal(resources)) {
            initialize(directory,resources);var before=inventory(directory);
            var wrongRoot=new MembershipRoot(root.groupId(),root.historyId(),"fe".repeat(32));
            var wrongStorage=new MembershipIdentity(owner.nodeId(),new UUID(71,72),owner.endpoint());
            assertThrows(IllegalArgumentException.class,()->new MembershipPendingContextFiles(directory,wrongRoot,owner,resources,LIMIT));
            assertThrows(IllegalArgumentException.class,()->new MembershipPendingContextFiles(directory,root,V53DeclarationsTest.node(2),resources,LIMIT));
            assertThrows(IllegalArgumentException.class,()->new MembershipPendingContextFiles(directory,root,wrongStorage,resources,LIMIT));
            assertEquals(before,inventory(directory));borrowedOnly(resources);
            Path empty=directory("foreign-request");var untouched=inventory(empty);
            try(var store=new MembershipPendingContextFiles(empty,wrongRoot,owner,resources,LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->store.install(first,null,GUARD,e->fail("foreign context mutated")));
                assertEquals(untouched,inventory(empty));poison(store);
            }
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void changedInodesPresenceAndOwnerDirectoryAreDetectedEvenWhenBytesMatch()throws Exception {
        var resources=resources();
        try(var lease=journal(resources)) {
            for(String point:List.of("CONTEXT_PREFIX_WRITTEN","CONTEXT_RENAMED")) {
                Path directory=directory(point);initialize(directory,resources);boolean[] changed={false};
                try(var store=open(directory,resources)) {
                    assertThrows(IllegalArgumentException.class,()->store.install(second,firstBytes,GUARD,e->{
                        if(e.equals(point)){replaceInode(directory.resolve(point.equals("CONTEXT_RENAMED")?ACTIVE:NEXT));changed[0]=true;}
                    }));assertTrue(changed[0]);poison(store);
                }
                // Reopening must revalidate the caller's exact request; matching bytes do not let
                // the old component continue after its inode witness was invalidated.
                try(var store=open(directory,resources)){assertArrayEquals(secondBytes,store.install(second,firstBytes,GUARD,NO_CUT));}
            }
            Path active=directory("active-inode");initialize(active,resources);
            try(var store=open(active,resources)){replaceInode(active.resolve(ACTIVE));assertThrows(IllegalArgumentException.class,store::check);poison(store);}
            Path presence=directory("presence");initialize(presence,resources);
            try(var store=open(presence,resources)) {
                Files.write(presence.resolve(NEXT),new byte[0]);assertThrows(IllegalArgumentException.class,store::check);poison(store);
            }
            Path directory=directory("directory-inode");initialize(directory,resources);
            try(var store=open(directory,resources)) {
                Files.move(directory,temp.resolve("displaced-owner"));Files.createDirectory(directory);
                assertThrows(IllegalArgumentException.class,store::check);poison(store);
            }
            borrowedOnly(resources);
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void failedCallerGuardPoisonsTheAttemptButExactRenameRecoveryStillChecksTheGuard()throws Exception {
        var resources=resources();
        try(var lease=journal(resources)) {
            Path untouched=directory("guard-before");var before=inventory(untouched);
            try(var store=open(untouched,resources)) {
                assertThrows(IOException.class,()->store.install(first,null,()->{throw new IOException("owner fenced");},e->fail("fenced owner mutated")));
                assertEquals(before,inventory(untouched));poison(store);
            }
            for(String point:List.of("CONTEXT_CANDIDATE_FORCED","CONTEXT_RENAMED")) {
                Path directory=directory(point);initialize(directory,resources);var fenced=new AtomicBoolean();
                MembershipGenerationFiles.Guard guard=()->{if(fenced.get())throw new IOException("owner fenced after cut");};
                try(var store=open(directory,resources)) {
                    assertThrows(IOException.class,()->store.install(second,firstBytes,guard,e->{if(e.equals(point))fenced.set(true);}));
                    assertTrue(fenced.get());poison(store);
                }
                var after=inventory(directory);
                try(var store=open(directory,resources)) {
                    assertThrows(IOException.class,()->store.install(second,firstBytes,guard,e->fail("still-fenced recovery mutated")));
                    assertEquals(after,inventory(directory));poison(store);
                }
                fenced.set(false);
                try(var store=open(directory,resources)){assertArrayEquals(secondBytes,store.install(second,firstBytes,guard,NO_CUT));}
            }
            borrowedOnly(resources);
        }
        assertEquals(0,resources.usage().leases());
    }

    @Test void sharedJournalAndPeakAllowanceIncludeTheActiveFileAndSurvivingPrefix()throws Exception {
        var resources=resources();Path absent=directory("missing-lease");var before=inventory(absent);
        assertThrows(IllegalArgumentException.class,()->open(absent,resources));assertEquals(before,inventory(absent));
        try(var lease=journal(resources)) {
            assertThrows(IllegalArgumentException.class,()->resources.reserve(MembershipResources.Unit.JOURNAL,"second-owner",1));
            assertThrows(IllegalArgumentException.class,()->new MembershipPendingContextFiles(absent,root,owner,resources,LIMIT+1));
            try(var store=new MembershipPendingContextFiles(absent,root,owner,resources,firstBytes.length-1L)) {
                assertThrows(IllegalArgumentException.class,()->store.install(first,null,GUARD,e->fail("capacity must fail before writing")));
                assertEquals(before,inventory(absent));poison(store);
            }
            Path directory=directory("bounded");initialize(directory,resources);var original=inventory(directory);
            long peak=(long)firstBytes.length+secondBytes.length;
            try(var store=new MembershipPendingContextFiles(directory,root,owner,resources,peak-1)) {
                assertEquals(firstBytes.length,store.bytes());assertEquals(secondBytes.length,store.completionAllowance(second));
                assertThrows(IllegalArgumentException.class,()->store.install(second,firstBytes,GUARD,e->fail("peak budget omitted active")));
                assertEquals(original,inventory(directory));poison(store);
            }
            try(var store=new MembershipPendingContextFiles(directory,root,owner,resources,peak)) {
                assertThrows(IOException.class,()->store.install(second,firstBytes,GUARD,e->{if(e.equals("CONTEXT_PREFIX_WRITTEN"))throw new IOException("prefix");}));
            }
            long retained=contextBytes(directory);assertTrue(retained>firstBytes.length && retained<peak);
            assertThrows(IllegalArgumentException.class,()->new MembershipPendingContextFiles(directory,root,owner,resources,retained-1));
            try(var store=new MembershipPendingContextFiles(directory,root,owner,resources,peak)) {
                assertEquals(retained,store.bytes());assertEquals(peak,store.bytes()+store.completionAllowance(second));
                assertArrayEquals(secondBytes,store.install(second,firstBytes,GUARD,NO_CUT));
                assertEquals(secondBytes.length,store.bytes());assertEquals(0,store.completionAllowance(second));
                borrowedOnly(resources);
            }
            borrowedOnly(resources);onlyContextAndSentinel(directory);
        }
        assertEquals(0,resources.usage().leases());assertEquals(0,resources.usage().metadata());assertEquals(0,resources.usage().staging());
    }

    @Test void releasingTheBorrowedJournalFencesAnOpenComponentWithoutDeletingAnyBytes()throws Exception {
        Path directory=directory("released");var resources=resources();var lease=journal(resources);
        try(var store=open(directory,resources)) {
            store.install(first,null,GUARD,NO_CUT);var before=inventory(directory);lease.close();
            assertThrows(IllegalArgumentException.class,store::check);poison(store);assertEquals(before,inventory(directory));
        }finally{lease.close();}
        assertEquals(0,resources.usage().leases());
    }

    @Test void freshProcessesResumeHaltAndKillAtEveryWriteAndReplayCut()throws Exception {
        V53PendingContextFilesProcess.qualify(Path.of("target/v53-pending-context-process").resolve("run-"+UUID.randomUUID()),
                rootRecord,firstBytes,secondBytes);
    }
}
