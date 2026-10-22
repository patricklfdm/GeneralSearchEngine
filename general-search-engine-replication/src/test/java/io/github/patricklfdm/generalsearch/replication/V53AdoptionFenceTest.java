package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53AdoptionFenceTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("ADOPTION_VALIDATED","PROMISE_BEFORE_WRITE","PROMISE_WRITTEN","PROMISE_FORCED","ADOPTION_BEFORE_RETURN");
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    @Test void membershipCertificateForcesItsOriginalAuthorityWithoutGrantOrPrefix() throws Exception {
        for(int size:List.of(3,4,5))for(int through:List.of(6,7)) {
            var f=new V53AdoptionFenceFixture(size,through);Path path=temp.resolve(size+"-"+through);f.provision(path);
            byte[] selector=Files.readAllBytes(path.resolve("selector.gsr"));String retained;Decoded fence;
            try(var store=f.open(path,resources(),e->{})) {
                retained=(String)store.originalBasis().orElseThrow().value().get("basisId");
                fence=store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of());
                assertNull(fence.value().get("basisId"));assertEquals(24L+through,object(fence.value().get("ballot")).get("counter"));
                var cert=MembershipCapsule.verify(f.remote.source.root,f.remote.packet(),f.remote.source.images,f.owned).membershipCertificateFence().orElseThrow();
                assertEquals(cert.value().get("authority"),fence.value().get("view"));
                assertTrue(store.originalBasis().isEmpty());assertTrue(store.originalSelection().isEmpty());
                byte[] journal=Files.readAllBytes(path.resolve("grants.gsr"));
                assertArrayEquals(fence.bytes(),store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()).bytes());
                assertArrayEquals(journal,Files.readAllBytes(path.resolve("grants.gsr")));
                assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(24+through)));
            }
            try(var store=f.open(path,resources(),e->{})) {
                assertArrayEquals(fence.bytes(),store.promised().orElseThrow().bytes());assertTrue(store.originalBasis().isEmpty());
                assertThrows(IllegalArgumentException.class,()->store.prepareCurrent(f.initial.fixture.source.ballot(20)));
            }
            assertArrayEquals(selector,Files.readAllBytes(path.resolve("selector.gsr")));
            assertTrue(Files.exists(path.resolve("sources").resolve(retained).resolve("source.gscp")));
        }
    }
    @Test void everyInterruptedFenceRetainsOldPrefixAndRequiresNoResampledBasis() throws Exception {
        for(String cut:CUTS) {
            var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve(cut);f.provision(path);var resources=resources();
            byte[] selector=Files.readAllBytes(path.resolve("selector.gsr"));
            try(var store=f.open(path,resources,e->{if(e.equals(cut))throw new IOException("cut");})) {
                assertThrows(IOException.class,()->store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()));
            }
            assertEquals(0,resources.usage().leases());
            try(var store=f.open(path,resources,e->{})) {
                assertNull(store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()).value().get("basisId"));
                assertTrue(store.originalBasis().isEmpty());
            }
            assertArrayEquals(selector,Files.readAllBytes(path.resolve("selector.gsr")));assertEquals(0,resources.usage().leases());
        }
    }
    @Test void unusedHigherCertificateCannotRaiseTheFence() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);f.reprove(1,999);f.owned.addAll(f.remote.source.owned);
        Path path=temp.resolve("extra");f.provision(path);
        try(var store=f.open(path,resources(),e->{})) {
            var fence=store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of());
            assertEquals(31L,object(fence.value().get("ballot")).get("counter"));
        }
    }
    @Test void unauthenticatedCertificateCannotFenceOrWriteAnyLocalAuthority() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("unowned");f.provision(path);
        f.owned.removeIf(o->f.remote.objects.containsKey(o.record()) &&
                java.nio.ByteBuffer.wrap(f.remote.objects.get(o.record())).getShort(8)==8);
        byte[] journal=Files.readAllBytes(path.resolve("grants.gsr"));
        try(var store=f.open(path,resources(),e->{})) {
            assertThrows(IllegalArgumentException.class,()->store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()));
            assertEquals(20L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));
            assertArrayEquals(journal,Files.readAllBytes(path.resolve("grants.gsr")));
        }
    }
    @Test void higherObservedBallotFencesEveryWriteOrReturnBoundary() throws Exception {
        for(String cut:CUTS) {
            var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("higher-"+cut);f.provision(path);MembershipGrantJournal[] ref=new MembershipGrantJournal[1];
            try(var store=f.open(path,resources(),event->{if(event.equals(cut))ref[0].observeCurrent(f.initial.fixture.source.ballot(50));})) {
                ref[0]=store;assertThrows(IllegalArgumentException.class,()->store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()));
            }
            try(var store=f.open(path,resources(),e->{})){assertNotNull(store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()));}
        }
    }
    @Test void rangeCheckpointAloneIsNotACertificateDerivedFence() throws Exception {
        var f=new V53AdoptionFenceFixture(3,1);Path path=temp.resolve("range");f.provision(path);
        try(var store=f.open(path,resources(),e->{})) {
            assertEquals("no authenticated membership certificate fence",assertThrows(IllegalArgumentException.class,
                    ()->store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of())).getMessage());
        }
    }
    @Test void higherExistingPromiseIsNeverLoweredOrRelabelled() throws Exception {
        var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("already-higher");f.provision(path);
        try(var store=f.open(path,resources(),e->{})) {
            var basis=store.prepareCurrent(f.initial.fixture.source.ballot(50));var promise=store.promised().orElseThrow();
            byte[] journal=Files.readAllBytes(path.resolve("grants.gsr"));
            assertArrayEquals(promise.bytes(),store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of()).bytes());
            assertArrayEquals(basis.bytes(),store.originalBasis().orElseThrow().bytes());assertArrayEquals(journal,Files.readAllBytes(path.resolve("grants.gsr")));
        }
    }
    @Test void tornFenceOrInventedBasisRefusesOpenWithoutRepair() throws Exception {
        for(boolean torn:List.of(false,true)) {
            var f=new V53AdoptionFenceFixture(3,7);Path path=temp.resolve("bad-"+torn);f.provision(path);Decoded original;
            try(var store=f.open(path,resources(),e->{})) {
                original=store.originalBasis().orElseThrow();store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of());
            }
            Path journal=path.resolve("grants.gsr");byte[] bytes=Files.readAllBytes(journal);
            if(torn)Files.write(journal,Arrays.copyOf(bytes,bytes.length-1));
            else Files.write(journal,original.bytes(),StandardOpenOption.APPEND);
            byte[] bad=Files.readAllBytes(journal);assertThrows(IllegalArgumentException.class,()->f.open(path,resources(),e->{}));
            assertArrayEquals(bad,Files.readAllBytes(journal));
        }
    }
    @Test void adoptionFenceCannotNameAnOriginalSourceDirectory() throws Exception {
        var f=new V53AdoptionFenceFixture(3,6);Path path=temp.resolve("adoption-source");f.provision(path);String original;Decoded fence;
        try(var store=f.open(path,resources(),e->{})) {
            original=(String)store.originalBasis().orElseThrow().value().get("basisId");
            fence=store.fenceMembershipPrefix(f.remote.packet(),f.remote.source.images,List.of());
        }
        Path wrong=path.resolve("sources").resolve("adoption:"+fence.digest());Files.createDirectory(wrong);
        try(var files=Files.list(path.resolve("sources").resolve(original))) {
            for(Path file:files.toList())Files.copy(file,wrong.resolve(file.getFileName()));
        }
        var resources=resources();var error=assertThrows(IllegalArgumentException.class,()->f.open(path,resources,e->{}));
        assertEquals("retained source requires original basis identity",error.getMessage());assertEquals(0,resources.usage().leases());
        assertTrue(Files.exists(wrong.resolve("source.gscp")));
    }
}
