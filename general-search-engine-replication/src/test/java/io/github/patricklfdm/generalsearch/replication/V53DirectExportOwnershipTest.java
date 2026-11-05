package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53DirectExportOwnershipTest {
    static MembershipResources budget(){return V53SessionExportOwnershipTest.budget();}
    static MembershipTransferExport export(LeaseView owned,Runnable close) {
        return new MembershipTransferExport() {
            public MembershipContext context(){return null;}
            public MembershipIdentity identity(){return null;}
            public Map<String,Object> ballot(){return Map.of();}
            public List<MembershipResources.Lease> closeReservations(){return owned.get();}
            public Map<String,MembershipSourceExport.Content> references(){return Map.of();}
            public byte[] read(String digest,long offset,int maximum){return new byte[]{1};}
            public void close(){close.run();}
        };
    }
    interface LeaseView {List<MembershipResources.Lease> get();}
    static String name(String phase){return (phase.equals("MAINTENANCE")?"prefix-export-":"source-export-")+"a".repeat(64)+"-"+UUID.randomUUID();}
    @Test void disabledObservationReturnsTheActualExporterWithoutInspectingIt() {
        var b=new MembershipResources(512*MIB);var calls=new AtomicInteger();
        var original=export(()->{throw new AssertionError("disabled observer queried exporter");},calls::incrementAndGet);
        assertSame(original,b.observeDirectExport(original,"ACTIVATION"));original.close();assertEquals(1,calls.get());
    }
    @Test void allThreeScopesKeepOriginalHandlesAndRepeatedCloseCalls() {
        for(String phase:List.of("ACTIVATION","SELECTED","MAINTENANCE")) {
            var b=budget();var lease=b.reserve(Unit.CONTROL,name(phase),20);var calls=new AtomicInteger();
            var original=export(()->List.of(lease),()->{calls.incrementAndGet();lease.close();});
            var observed=b.observeDirectExport(original,phase);
            assertEquals(assertDoesNotThrow(original::references),assertDoesNotThrow(observed::references));assertArrayEquals(new byte[]{1},assertDoesNotThrow(()->observed.read("",0,1)));
            observed.close();observed.close();assertEquals(2,calls.get());assertEquals(0,b.usage().leases());
            var trace=b.controlCloseObservations();assertFalse(trace.failed());assertFalse(trace.truncated());
            assertEquals(List.of(phase+"_BORROW_ACQUIRED",phase+"_BORROW_CLOSE_BEGIN",phase+"_BORROW_RETURNED"),trace.rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
            assertEquals(List.of(0L,0L,0L),trace.rows().stream().map(MembershipControlCloseObservations.Row::call).toList());
        }
    }
    @Test void earlyOwnerRevocationDoesNotInventAnObservationFailure() {
        for(boolean before:List.of(false,true)) {
            var b=budget();var lease=b.reserve(Unit.CONTROL,name("ACTIVATION"),20);
            if(before)lease.close();var observed=b.observeDirectExport(export(()->List.of(lease),lease::close),"ACTIVATION");
            if(!before)lease.close();observed.close();assertFalse(b.controlCloseObservations().failed());assertEquals(3,b.controlCloseObservations().rows().size());
        }
    }
    @Test void failedCloseCannotBecomeNormalReturnAfterZeroUsageOrRetry() {
        var b=budget();var lease=b.reserve(Unit.CONTROL,name("ACTIVATION"),20);var calls=new AtomicInteger();var failure=new IllegalStateException("original cleanup failed");
        var observed=b.observeDirectExport(export(()->List.of(lease),()->{lease.close();if(calls.incrementAndGet()==1)throw failure;}),"ACTIVATION");
        assertSame(failure,assertThrows(IllegalStateException.class,observed::close));observed.close();
        assertEquals(0,b.usage().leases());assertEquals(2,calls.get());assertEquals(2,b.controlCloseObservations().rows().size());
        assertTrue(b.controlCloseObservations().rows().stream().noneMatch(row->row.event().endsWith("RETURNED")));
    }
    @Test void tryWithResourcesKeepsTheOriginalExceptionAndSuppression() {
        var b=budget();var lease=b.reserve(Unit.CONTROL,name("MAINTENANCE"),20);
        var body=new IllegalStateException("body");var cleanup=new IllegalArgumentException("cleanup");
        var actual=assertThrows(IllegalStateException.class,()->{
            try(var resource=b.observeDirectExport(export(()->List.of(lease),()->{lease.close();throw cleanup;}),"MAINTENANCE")){throw body;}
        });
        assertSame(body,actual);assertArrayEquals(new Throwable[]{cleanup},actual.getSuppressed());assertEquals(0,b.usage().leases());
    }
    @Test void foreignOrMisclassifiedHandlesOnlyFailObservation() {
        for(String mode:List.of("foreign","role","empty")) {
            var b=budget();var other=budget();var lease=(mode.equals("foreign")?other:b).reserve(Unit.CONTROL,name("ACTIVATION"),20);
            var original=export(()->mode.equals("empty")?List.of():List.of(lease),lease::close);
            assertSame(original,b.observeDirectExport(original,mode.equals("role")?"MAINTENANCE":"ACTIVATION"));
            assertTrue(b.controlCloseObservations().failed());original.close();assertEquals(0,b.usage().leases());assertEquals(0,other.usage().leases());
        }
    }
    @Test void exporterCallbackRunsWithoutHoldingTheAccountingMonitor()throws Exception {
        var b=budget();var lease=b.reserve(Unit.CONTROL,name("ACTIVATION"),20);var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        var observed=b.observeDirectExport(export(()->List.of(lease),()->{
            entered.countDown();try{assertTrue(release.await(10,TimeUnit.SECONDS));}catch(InterruptedException e){throw new AssertionError(e);}lease.close();
        }),"ACTIVATION");
        try(var pool=Executors.newFixedThreadPool(2)) {
            var closing=pool.submit(observed::close);
            try {
                assertTrue(entered.await(10,TimeUnit.SECONDS));
                assertEquals(2,pool.submit(()->{try(var unrelated=b.reserve(Unit.CONTROL,"unrelated",10)){return b.usage().leases();}}).get(5,TimeUnit.SECONDS));
            }finally{release.countDown();}
            closing.get(10,TimeUnit.SECONDS);
        }
        assertEquals(0,b.usage().leases());assertFalse(b.controlCloseObservations().failed());
    }
    @Test void truncationNeverPreventsTheOriginalRelease() {
        var b=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,4096,1,true);var lease=b.reserve(Unit.CONTROL,name("ACTIVATION"),20);
        b.observeDirectExport(export(()->List.of(lease),lease::close),"ACTIVATION").close();
        assertEquals(0,b.usage().leases());assertTrue(b.controlCloseObservations().truncated());
    }
}
