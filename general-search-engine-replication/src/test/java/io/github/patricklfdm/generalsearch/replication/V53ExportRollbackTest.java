package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53ExportRollbackTest {
    @TempDir Path temp;
    static String name(String role){return role+"-"+"a".repeat(64)+"-"+UUID.randomUUID();}
    @Test void disabledObservationDoesNotInspectNestedExportOrAffectRelease() {
        var pool=new MembershipResources(512*MIB);var metadata=pool.reserve(Unit.CONTROL,name("joining-intent"),20);
        var child=V53DirectExportOwnershipTest.export(()->{throw new AssertionError("disabled observation inspected descriptor");},()->{});
        assertEquals(-1,metadata.observeExportRollbackBegin(child));metadata.close();metadata.observeExportRollbackReturned(-1);
        assertEquals(0,pool.usage().leases());
    }
    @Test void fiveMetadataRolesKeepActualFailedCleanupIntervals() {
        for(String role:List.of("joining-retention-export","joining-intent","joining-preparation-export","joining-completion-export","joining-checkpoint-export")) {
            var pool=V53SessionExportOwnershipTest.budget();var metadata=pool.reserve(Unit.CONTROL,name(role),20);
            long call=metadata.observeExportRollbackBegin(null);metadata.close();metadata.observeExportRollbackReturned(call);
            var observed=pool.controlCloseObservations();assertFalse(observed.failed());assertFalse(observed.truncated());
            assertEquals(List.of("EXPORT_ROLLBACK_BEGIN","EXPORT_ROLLBACK_RETURNED"),observed.rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
            assertEquals(call,observed.rows().getLast().call());assertEquals(0,pool.usage().leases());
        }
    }
    @Test void liveAndAlreadyRevokedChildrenKeepTheSameOriginalHandle() {
        for(boolean revoked:List.of(false,true)) {
            var pool=V53SessionExportOwnershipTest.budget();var metadata=pool.reserve(Unit.CONTROL,name("joining-intent"),20);
            String childName=name("prefix-export");var child=pool.reserve(Unit.CONTROL,childName,20);if(revoked)child.close();
            var export=V53DirectExportOwnershipTest.export(()->{assertFalse(Thread.holdsLock(pool));return List.of(child);},child::close);
            long call=metadata.observeExportRollbackBegin(export);export.close();metadata.close();metadata.observeExportRollbackReturned(call);
            assertFalse(pool.controlCloseObservations().failed());assertEquals(List.of(childName),pool.controlCloseObservations().rows().getFirst().children());
        }
    }
    @Test void foreignAndIncorrectGroupsFailObservationWithoutReplacingCleanup() {
        for(String mode:List.of("foreign","metadata-role","child-role","extra-child","unexpected-child")) {
            var pool=V53SessionExportOwnershipTest.budget();var other=V53SessionExportOwnershipTest.budget();
            var metadata=pool.reserve(Unit.CONTROL,name(mode.equals("metadata-role")?"source-export":mode.equals("unexpected-child")?"joining-completion-export":"joining-intent"),20);
            var child=(mode.equals("foreign")?other:pool).reserve(Unit.CONTROL,name(mode.equals("child-role")?"record-export":"prefix-export"),20);
            var export=V53DirectExportOwnershipTest.export(()->mode.equals("extra-child")?List.of(child,child):List.of(child),child::close);
            assertEquals(-1,metadata.observeExportRollbackBegin(export));export.close();metadata.close();
            assertTrue(pool.controlCloseObservations().failed());assertEquals(0,pool.usage().leases());assertEquals(0,other.usage().leases());
        }
    }
    @Test void failedCleanupAndFinalZeroCannotInventSuccessfulReturn() {
        var pool=V53SessionExportOwnershipTest.budget();var metadata=pool.reserve(Unit.CONTROL,name("joining-intent"),20);
        var child=pool.reserve(Unit.CONTROL,name("prefix-export"),20);var failure=new IllegalStateException("cleanup failed");
        var export=V53DirectExportOwnershipTest.export(()->List.of(child),()->{child.close();throw failure;});
        metadata.observeExportRollbackBegin(export);assertSame(failure,assertThrows(IllegalStateException.class,export::close));metadata.close();
        assertEquals(0,pool.usage().leases());assertEquals(1,pool.controlCloseObservations().rows().size());
    }
    @Test void missingReleaseAndTruncationAreNeverSuccessfulEvidence() {
        var pool=V53SessionExportOwnershipTest.budget();var metadata=pool.reserve(Unit.CONTROL,name("joining-intent"),20);
        long call=metadata.observeExportRollbackBegin(null);metadata.observeExportRollbackReturned(call);metadata.close();
        assertTrue(pool.controlCloseObservations().failed());
        var bounded=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,4096,1,true);
        var lease=bounded.reserve(Unit.CONTROL,name("joining-intent"),20);long cut=lease.observeExportRollbackBegin(null);
        lease.close();lease.observeExportRollbackReturned(cut);assertTrue(bounded.controlCloseObservations().truncated());assertEquals(0,bounded.usage().leases());
    }
    @Test void retentionCapacityFailureRollsBackOnlyItsNewMetadata()throws Exception {capture("retention-capacity");}
    @Test void retentionExpiryPreservesItsRevokedNestedBorrowInRollback()throws Exception {capture("retention-expiry");}
    @Test void preparationGuardFailurePreservesTheOriginalExceptionAndPublication()throws Exception {capture("preparation-guard");}

    void capture(String kind)throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;
        Path parent=Path.of("target/v53-export-constructor-rollback");Files.createDirectories(parent);
        Path raw=Files.createDirectory(parent.resolve("run-"+UUID.randomUUID()));MembershipResources pool;
        try(var local=helper.new Local(true)) {
            pool=local.a;var context=local.source.activationContext();boolean preparation=kind.equals("preparation-guard");
            var request=MembershipActivation.frame("CHUNK",context,local.reader.activationIdentity(),local.source.activationIdentity(),
                    local.reader.discoveryState(local.b).ballot(),UUID.randomUUID(),1,Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,
                    "digest",preparation?MembershipJoiningPreparation.reference(context,local.reader.activationIdentity()):local.reference(),"bytes",""));
            var held=new ArrayList<MembershipPrefixExport>();
            try {
                if(kind.equals("retention-capacity"))for(int i=0;i<6;i++)held.add(local.source.exportPrefix(MembershipContext.cutDigest(context.cut),
                        local.reader.discoveryState(local.b).ballot(),context.authority(),pool,local.clock::get,0,BUDGET));
                var allowed=new AtomicLong(Long.MAX_VALUE);var failure=new IOException("revoked preparation after reservation");
                try(var publication=new MembershipJoiningPreparation(local.source,pool,V53JoiningPreparationTest.hint(local),()->{
                    if(pool.usage().queued()>allowed.get())throw failure;
                },local.clock::get,0,BUDGET)) {
                    var baseline=pool.usage();allowed.set(baseline.queued());long before=pool.observationCheckpoint().sequence();Throwable thrown;
                    if(preparation)thrown=assertThrows(IOException.class,()->publication.open(local.reader.activationIdentity(),request));
                    else {
                        var reads=new AtomicInteger();
                        thrown=assertThrows(IllegalArgumentException.class,()->new MembershipJoiningRetentionExport(local.source,local.reader.activationIdentity(),request,pool,
                                kind.equals("retention-expiry")?()->reads.incrementAndGet()<=2?0:10:local.clock::get,0,kind.equals("retention-expiry")?10:BUDGET));
                    }
                    long after=pool.observationCheckpoint().sequence();assertEquals(baseline,pool.usage());if(preparation)assertSame(failure,thrown);
                    var markers=pool.controlCloseObservations().rows().stream().filter(row->row.event().startsWith("EXPORT_ROLLBACK_")).toList();
                    assertEquals(2,markers.size());assertEquals(kind.equals("retention-expiry")?1:0,markers.getFirst().children().size());
                    assertEquals("EXPORT_ROLLBACK_RETURNED",markers.getLast().event());
                    Files.write(raw.resolve("case.json"),canonical(Map.of("schema","gse-v53-export-rollback-component-v1","node","node-1","case",kind,
                            "request",Base64.getEncoder().encodeToString(request.bytes()),"before",before,"after",after,
                            "failureType",thrown.getClass().getSimpleName(),"failureMessage",thrown.getMessage(),"completeNativeHistory",false),16384),StandardOpenOption.CREATE_NEW);
                }
            }finally{for(var export:held)export.close();}
        }
        assertEquals(0,pool.usage().leases());V53ResourceTraceFiles.write(raw.resolve("resources.json"),pool.observations());
        V53ResourceTraceFiles.writeCloses(raw.resolve("closes.json"),pool.controlCloseObservations());
        System.out.println("v53ExportRollbackEvidence="+raw.toAbsolutePath());
    }
}
