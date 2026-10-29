package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53StorageOwnershipTransferTest {
    @Test void everyFullStorageCategoryTransfersWithoutDoubleChargingOrReleasingAnyByte() {
        var resources=new MembershipResources(1024*MIB);var requests=new LinkedHashMap<MembershipResources.Lease,String>();
        for(Unit unit:List.of(Unit.GENERATION,Unit.SOURCE,Unit.LEARNER,Unit.JOURNAL,Unit.CATALOG,Unit.MISC,Unit.APPLICATION))
            for(int n=0;n<unit.count;n++)requests.put(resources.reserve(unit,"old-"+n,unit.bytes),"new-"+n);
        var before=resources.usage();var successors=resources.transferStorage(requests);assertEquals(before,resources.usage());
        requests.keySet().forEach(MembershipResources.Lease::close);assertEquals(before,resources.usage());
        assertThrows(IllegalArgumentException.class,()->resources.reserve(Unit.GENERATION,"third",1));
        assertThrows(IllegalArgumentException.class,()->resources.reserve(Unit.APPLICATION,"eighth",1));
        assertThrows(IllegalArgumentException.class,()->resources.transferStorage(requests));assertEquals(before,resources.usage());
        successors.values().forEach(MembershipResources.Lease::close);successors.values().forEach(MembershipResources.Lease::close);
        assertEquals(0,resources.usage().leases());assertEquals(0,resources.usage().metadata());assertEquals(0,resources.usage().staging());
        try(var next=resources.reserve(Unit.JOURNAL,"new",Unit.JOURNAL.bytes)){assertEquals(Unit.JOURNAL.bytes,resources.usage().metadata());}
    }
    @Test void wholeGroupPreflightRefusesForeignReleasedDuplicateAndOccupiedTargetsAtomically() {
        var resources=new MembershipResources(1024);var other=new MembershipResources(1024);
        try(var a=resources.reserve(Unit.SOURCE,"a",10);var b=resources.reserve(Unit.SOURCE,"b",20);
                var occupied=resources.reserve(Unit.SOURCE,"occupied",30);var foreign=other.reserve(Unit.SOURCE,"a",40)) {
            var before=resources.usage();var foreignBefore=other.usage();
            for(var request:List.of(Map.of(a,"x",foreign,"y"),Map.of(a,"x",b,"x"),Map.of(a,"x",b,"occupied"),Map.of(a,"x",b,""))) {
                assertThrows(IllegalArgumentException.class,()->resources.transferStorage(request));assertEquals(before,resources.usage());assertEquals(foreignBefore,other.usage());
            }
            var gone=resources.reserve(Unit.SOURCE,"gone",1);gone.close();
            assertThrows(IllegalArgumentException.class,()->resources.transferStorage(Map.of(a,"new",gone,"gone")));assertEquals(before,resources.usage());
            // Exact swapping changes labels, not category or extent, and is one transaction.
            var swap=resources.transferStorage(Map.of(a,"b",b,"a"));a.close();b.close();assertEquals(before,resources.usage());
            swap.get(a).reserveStorage(11);assertEquals(before.staging()+1,resources.usage().staging());
            assertThrows(IllegalArgumentException.class,()->a.reserveStorage(12));swap.values().forEach(MembershipResources.Lease::close);
            assertEquals(30,resources.usage().staging());
        }
    }
    @Test void inFlightGenerationClaimsAndRequestResourcesCannotBeTransferred() {
        var resources=new MembershipResources(1024);
        try(var learner=resources.reserve(Unit.LEARNER,"source",10);var generation=resources.reserve(Unit.GENERATION,"other",10);
                var claim=learner.prepareGeneration("next");var control=resources.reserve(Unit.CONTROL,"rpc",1);
                var waiter=resources.reserve(Unit.WAITER,"client",0)) {
            var before=resources.usage();
            for(var request:List.of(Map.of(learner,"learner"),Map.of(generation,"next"),Map.of(control,"rpc2"),Map.of(waiter,"client2"))) {
                assertThrows(IllegalArgumentException.class,()->resources.transferStorage(request));assertEquals(before,resources.usage());
            }
            claim.commit();var held=resources.usage();var next=resources.transferStorage(Map.of(learner,"next"));learner.close();assertEquals(held,resources.usage());next.values().forEach(MembershipResources.Lease::close);
        }
        assertEquals(0,resources.usage().leases());
    }
    @Test void transferAndConcurrentCloseCannotUnchargeTheSuccessfulSuccessor()throws Exception {
        for(int n=0;n<32;n++) {
            var resources=new MembershipResources(100);var old=resources.reserve(Unit.APPLICATION,"image",100);
            Map<MembershipResources.Lease,MembershipResources.Lease> next;
            try(var pool=Executors.newVirtualThreadPerTaskExecutor()) {
                var barrier=new CyclicBarrier(2);
                var transfer=pool.submit(()->{barrier.await();try{return resources.transferStorage(Map.of(old,"image"));}catch(IllegalArgumentException closed){return Map.<MembershipResources.Lease,MembershipResources.Lease>of();}});
                var close=pool.submit(()->{barrier.await();old.close();return true;});
                next=transfer.get(20,TimeUnit.SECONDS);assertTrue(close.get(20,TimeUnit.SECONDS));
            }
            assertEquals(next.isEmpty()?0:100,resources.usage().staging());assertEquals(next.size(),resources.usage().leases());
            next.values().forEach(MembershipResources.Lease::close);assertEquals(0,resources.usage().leases());
        }
    }
    @Test void completionHeadroomAndSharedStagingRemainEnforcedAfterTransfer() {
        var resources=new MembershipResources(HEADROOM+100,200,100);
        var source=resources.reserve(Unit.SOURCE,"source",100);var image=resources.reserve(Unit.APPLICATION,"image",100);
        var journal=resources.reserve(Unit.JOURNAL,"journal",Unit.JOURNAL.bytes);
        var next=resources.transferStorage(Map.of(source,"source",image,"image",journal,"journal"));
        source.close();image.close();journal.close();
        assertThrows(IllegalArgumentException.class,()->resources.reserve(Unit.SOURCE,"extra",1));
        assertThrows(IllegalArgumentException.class,()->next.get(image).reserveStorage(101));
        try(var catalog=resources.reserve(Unit.CATALOG,"catalog",Unit.CATALOG.bytes);var misc=resources.reserve(Unit.MISC,"misc",Unit.MISC.bytes)) {
            assertEquals(HEADROOM+100,resources.usage().metadata());
        }
        next.values().forEach(MembershipResources.Lease::close);assertEquals(0,resources.usage().metadata());assertEquals(0,resources.usage().staging());
    }
}
