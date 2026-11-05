package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53ProbeExportOwnershipTest {
    @TempDir Path temp;
    static String name(String role){return role+"-"+"a".repeat(64)+"-"+UUID.randomUUID();}
    @Test void disabledObservationPreservesOriginalObjectWithoutDescriptorCalls() {
        var pool=new MembershipResources(512*MIB);var calls=new AtomicInteger();
        var raw=V53DirectExportOwnershipTest.export(()->{throw new AssertionError("disabled descriptor");},calls::incrementAndGet);
        assertSame(raw,pool.observeProbeExport(raw));raw.close();assertEquals(1,calls.get());
    }
    @Test void originalSingleAndNestedGroupsKeepAllActualHandlesAndRepeatedCloseCalls() {
        for(boolean nested:List.of(false,true)) {
            var pool=V53SessionExportOwnershipTest.budget();var primary=pool.reserve(Unit.CONTROL,name(nested?"joining-intent":"prefix-export"),20);
            var child=nested?pool.reserve(Unit.CONTROL,name("prefix-export"),20):null;var calls=new AtomicInteger();
            var handles=nested?List.of(primary,child):List.of(primary);
            var raw=V53DirectExportOwnershipTest.export(()->{assertFalse(Thread.holdsLock(pool));return handles;},()->{
                assertFalse(Thread.holdsLock(pool));calls.incrementAndGet();if(child!=null)child.close();primary.close();
            });
            var observed=pool.observeProbeExport(raw);assertEquals(handles,observed.closeReservations());
            observed.close();observed.close();assertEquals(2,calls.get());assertEquals(0,pool.usage().leases());
            var capture=pool.controlCloseObservations();assertFalse(capture.failed());
            assertEquals(List.of("PROBE_BORROW_ACQUIRED","PROBE_BORROW_CLOSE_BEGIN","PROBE_BORROW_RETURNED"),capture.rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
            assertEquals(nested?1:0,capture.rows().getFirst().children().size());
        }
    }
    @Test void aRevokedChildRemainsPartOfTheOriginalProbe() {
        var pool=V53SessionExportOwnershipTest.budget();var parent=pool.reserve(Unit.CONTROL,name("joining-intent"),20);
        var child=pool.reserve(Unit.CONTROL,name("prefix-export"),20);child.close();
        var raw=V53DirectExportOwnershipTest.export(()->List.of(parent,child),()->{child.close();parent.close();});
        pool.observeProbeExport(raw).close();assertFalse(pool.controlCloseObservations().failed());assertEquals(1,pool.controlCloseObservations().rows().getFirst().children().size());
    }
    @Test void failedCleanupAndLaterRetryCannotBackfillTheFirstReturn() {
        var pool=V53SessionExportOwnershipTest.budget();var lease=pool.reserve(Unit.CONTROL,name("prefix-export"),20);
        var calls=new AtomicInteger();var failure=new IllegalStateException("failed close");
        var observed=pool.observeProbeExport(V53DirectExportOwnershipTest.export(()->List.of(lease),()->{
            lease.close();if(calls.incrementAndGet()==1)throw failure;
        }));
        assertSame(failure,assertThrows(IllegalStateException.class,observed::close));observed.close();
        assertEquals(2,calls.get());assertEquals(0,pool.usage().leases());assertEquals(2,pool.controlCloseObservations().rows().size());
    }
    @Test void tryWithResourcesKeepsOriginalPrimaryAndSuppressedExceptions() {
        var pool=V53SessionExportOwnershipTest.budget();var lease=pool.reserve(Unit.CONTROL,name("prefix-export"),20);
        var body=new IllegalStateException("body");var cleanup=new IllegalArgumentException("cleanup");
        var actual=assertThrows(IllegalStateException.class,()->{
            try(var observed=pool.observeProbeExport(V53DirectExportOwnershipTest.export(()->List.of(lease),()->{lease.close();throw cleanup;}))){throw body;}
        });
        assertSame(body,actual);assertArrayEquals(new Throwable[]{cleanup},actual.getSuppressed());
    }
    @Test void invalidAndForeignGroupsOnlyFailTheObservation() {
        for(String fault:List.of("role","foreign","empty","duplicate","intent-alone","child-order")) {
            var pool=V53SessionExportOwnershipTest.budget();var other=V53SessionExportOwnershipTest.budget();
            var primary=(fault.equals("foreign")?other:pool).reserve(Unit.CONTROL,name(fault.equals("role")?"record-export":fault.equals("intent-alone")?"joining-intent":"prefix-export"),20);
            var secondary=fault.equals("child-order")?pool.reserve(Unit.CONTROL,name("joining-intent"),20):null;
            var raw=V53DirectExportOwnershipTest.export(()->switch(fault){case "empty"->List.of();case "duplicate"->List.of(primary,primary);
                case "child-order"->List.of(primary,secondary);default->List.of(primary);},()->{primary.close();if(secondary!=null)secondary.close();});
            assertSame(raw,pool.observeProbeExport(raw));raw.close();assertTrue(pool.controlCloseObservations().failed());
            assertEquals(0,pool.usage().leases());assertEquals(0,other.usage().leases());
        }
    }
    @Test void normalReturnMustReleaseEveryOwnedChild() {
        var pool=V53SessionExportOwnershipTest.budget();var primary=pool.reserve(Unit.CONTROL,name("joining-intent"),20);
        var child=pool.reserve(Unit.CONTROL,name("prefix-export"),20);
        pool.observeProbeExport(V53DirectExportOwnershipTest.export(()->List.of(primary,child),primary::close)).close();
        assertTrue(pool.controlCloseObservations().failed());assertEquals(2,pool.controlCloseObservations().rows().size());child.close();
    }
    @Test void truncationDoesNotPreventActualCleanup() {
        var pool=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,4096,1,true);var lease=pool.reserve(Unit.CONTROL,name("prefix-export"),20);
        pool.observeProbeExport(V53DirectExportOwnershipTest.export(()->List.of(lease),lease::close)).close();
        assertTrue(pool.controlCloseObservations().truncated());assertEquals(0,pool.usage().leases());
    }
    @Test void actualPrefixProbeClosesItsOriginalGenerationBorrow()throws Exception {capture(false);}
    @Test void actualExpiredPrefixProbeDoesNotReviveItsOriginalBorrow()throws Exception {capture(true);}

    void capture(boolean expired)throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;
        Path parent=Path.of("target/v53-probe-export-ownership");Files.createDirectories(parent);
        Path raw=Files.createDirectory(parent.resolve("run-"+UUID.randomUUID()));MembershipResources pool;
        try(var local=helper.new Local(true)) {
            pool=local.a;var context=local.source.activationContext();
            byte[] selector=Files.readAllBytes(local.path.resolve("selector.gsr"));var selected=decode(selector,"records","SELECTOR");
            byte[] generation=Files.readAllBytes(local.path.resolve("generations/"+selected.value().get("generation")+"/generation.gsr"));
            Files.write(raw.resolve("selector.gsr"),selector,StandardOpenOption.CREATE_NEW);Files.write(raw.resolve("generation.gsr"),generation,StandardOpenOption.CREATE_NEW);
            var baseline=pool.usage();long before=pool.observationCheckpoint().sequence(),through;
            try(var export=pool.observeProbeExport(local.source.exportPrefix(MembershipContext.cutDigest(context.cut),local.reader.discoveryState(local.b).ballot(),
                    context.authority(),pool,local.clock::get,0,BUDGET))) {
                assertFalse(export.references().isEmpty());through=pool.observationCheckpoint().sequence();
                if(expired){local.clock.set(BUDGET);assertThrows(IllegalArgumentException.class,export::references);}
            }
            long after=pool.observationCheckpoint().sequence();assertEquals(baseline,pool.usage());
            assertEquals(3,pool.controlCloseObservations().rows().stream().filter(row->row.event().startsWith("PROBE_BORROW_")).count());
            Files.write(raw.resolve("case.json"),canonical(Map.of("schema","gse-v53-probe-export-component-v1","node","node-1",
                    "mode",expired?"expiry":"close","before",before,"through",through,"after",after,"completeNativeHistory",false),4096),StandardOpenOption.CREATE_NEW);
        }
        V53ResourceTraceFiles.write(raw.resolve("resources.json"),pool.observations());
        V53ResourceTraceFiles.writeCloses(raw.resolve("closes.json"),pool.controlCloseObservations());
        System.out.println("v53ProbeExportEvidence="+raw.toAbsolutePath());
    }
}
