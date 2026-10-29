package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53StorageReplacementTest {
    @Test void replacementIsAtomicAndOldCloseCannotUnchargeNativeClaims() {
        var resources=new MembershipResources(1024*MIB);var old=new LinkedHashSet<MembershipResources.Lease>();
        old.add(resources.reserve(Unit.GENERATION,"first",100));old.add(resources.reserve(Unit.GENERATION,"second",200));old.add(resources.reserve(Unit.APPLICATION,"old-image",64));
        var before=resources.usage();var targets=List.of(new StorageReservation(Unit.GENERATION,"a",32),new StorageReservation(Unit.JOURNAL,"journal",32*MIB),new StorageReservation(Unit.MISC,"misc",2*MIB),new StorageReservation(Unit.APPLICATION,"image",64));
        var prepared=resources.prepareCompleteReplacement(old,targets);assertEquals(before,resources.usage());
        try(var batch=prepared.commit()) {
            var after=resources.usage();old.forEach(MembershipResources.Lease::close);assertEquals(after,resources.usage());
            assertThrows(Exception.class,batch::complete);for(var target:targets)batch.claim(target.unit(),target.owner(),target.bytes());batch.complete();
            assertThrows(Exception.class,()->batch.claim(Unit.GENERATION,"a",32));assertThrows(Exception.class,prepared::commit);
            assertEquals(after,resources.usage());
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void preflightRejectsCapacityDuplicateAndRequestCategoriesWithoutRevocation() {
        var resources=new MembershipResources(HEADROOM,1024,1024);
        try(var old=resources.reserve(Unit.APPLICATION,"original",10)) {
            var before=resources.usage();
            for(var targets:List.of(List.of(new StorageReservation(Unit.APPLICATION,"too-big",1025)),
                    List.of(new StorageReservation(Unit.GENERATION,"a",32*MIB)),
                    List.of(new StorageReservation(Unit.CONTROL,"work",1)),
                    List.of(new StorageReservation(Unit.APPLICATION,"same",1),new StorageReservation(Unit.APPLICATION,"same",1)))) {
                assertThrows(Exception.class,()->resources.prepareCompleteReplacement(Set.of(old),targets));assertEquals(before,resources.usage());
            }
            old.reserveStorage(11);assertEquals(11,resources.usage().staging());
        }
    }
    @Test void commitRejectsChangedExtentAndInterveningWorkOrGenerationClaims() {
        var resources=new MembershipResources(1024);
        try(var old=resources.reserve(Unit.LEARNER,"original",10)) {
            var targets=List.of(new StorageReservation(Unit.GENERATION,"a",10));var plan=resources.prepareCompleteReplacement(Set.of(old),targets);
            old.reserveStorage(11);var before=resources.usage();assertThrows(Exception.class,plan::commit);assertEquals(before,resources.usage());
            var fresh=resources.prepareCompleteReplacement(Set.of(old),targets);
            try(var work=resources.reserve(Unit.WAITER,"work",0)){var active=resources.usage();assertThrows(Exception.class,fresh::commit);assertEquals(active,resources.usage());}
            try(var claim=old.prepareGeneration("pending")){var active=resources.usage();assertThrows(Exception.class,fresh::commit);assertEquals(active,resources.usage());}
            try(var batch=fresh.commit()){batch.claim(Unit.GENERATION,"a",10);batch.complete();}
        }
        assertEquals(0,resources.usage().leases());
    }
}
