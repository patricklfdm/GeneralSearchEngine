package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53ResourceObservationsTest {
    static Path evidence;
    @BeforeAll static void output()throws Exception {
        evidence=Files.createDirectories(Path.of("target/v53-resource-observations/run-"+UUID.randomUUID()));
        System.out.println("v53ResourceObservationEvidence="+evidence.toAbsolutePath());
    }
    static MembershipResources budget(long staging){return new MembershipResources(METADATA_LIMIT,staging,QUEUE_LIMIT,4096);}
    static MembershipResources.StorageReservation reservation(Unit unit,String owner,long bytes){return new MembershipResources.StorageReservation(unit,owner,bytes);}
    static Map<String,Object> usage(Usage value) {
        var counts=new TreeMap<String,Object>();value.counts().forEach((unit,count)->counts.put(unit.name(),count));
        return Map.of("metadata",value.metadata(),"staging",value.staging(),"queued",value.queued(),"leases",value.leases(),"counts",counts);
    }
    static Map<String,Object> charge(MembershipResourceObservations.Charge value) {
        return Map.of("unit",value.unit().name(),"owner",value.owner(),"bytes",value.bytes(),"claimSource",value.claimSource());
    }
    static MembershipResourceObservations.Snapshot save(String name,MembershipResources budget)throws Exception {
        var value=budget.observations();var changes=new ArrayList<Map<String,Object>>();
        for(var row:value.changes())changes.add(Map.of("sequence",row.sequence(),"event",row.event(),"removed",row.removed().stream().map(V53ResourceObservationsTest::charge).toList(),
                "added",row.added().stream().map(V53ResourceObservationsTest::charge).toList(),"usage",usage(row.usage())));
        Files.write(evidence.resolve(name+".json"),MembershipFormat.canonical(Map.of("schema","gse-v53-resource-transitions-v1",
                "metadataLimit",value.metadataLimit(),"stagingLimit",value.stagingLimit(),"queueLimit",value.queueLimit(),
                "transitions",value.transitions(),"truncated",value.truncated(),"failed",value.failed(),"changes",changes,"current",usage(value.current())),8*1024*1024));
        return value;
    }
    static List<String> events(MembershipResources budget){return budget.observations().changes().stream().map(MembershipResourceObservations.Change::event).toList();}
    static void closed(MembershipResources budget) {
        var value=budget.observations();assertFalse(value.truncated());assertFalse(value.failed());assertEquals(value.transitions(),value.changes().size());
        assertEquals(0,value.current().leases());assertEquals(value.current(),value.changes().getLast().usage());
        for(int i=0;i<value.changes().size();i++)assertEquals(i,value.changes().get(i).sequence());
    }
    @Test void scalarReservationsGrowAndReleaseWithoutHidingTransientPeaks()throws Exception {
        var budget=budget(512*MIB);
        try(var source=budget.reserve(Unit.SOURCE,"source",20);var image=budget.reserve(Unit.APPLICATION,"image",8);
            var control=budget.reserve(Unit.CONTROL,"message",4);var misc=budget.reserve(Unit.MISC,"misc",2);
            var waiter=budget.reserve(Unit.WAITER,"waiter",0)) {
            source.reserveStorage(30);image.reserveApplicationMaximum();control.reserveControl(8);misc.reserveMisc(4);
            assertEquals(30+64*MIB,budget.usage().staging());assertEquals(34,budget.usage().metadata());
            var before=budget.observations();assertThrows(IllegalArgumentException.class,()->control.reserveControl(QUEUE_LIMIT));
            assertEquals(before,budget.observations());
        }
        closed(budget);assertTrue(events(budget).containsAll(List.of("RESERVE","STORAGE_GROW","APPLICATION_MAXIMUM","CONTROL_GROW","MISC_GROW","RELEASE")));
        save("scalar",budget);
    }
    @Test void pendingClaimsCountSlotsWithoutChargingLearnerBytesTwice()throws Exception {
        var budget=budget(512*MIB);
        try(var learner=budget.reserve(Unit.LEARNER,"learner",9)) {
            try(var claim=learner.prepareGeneration("cancelled")){assertEquals(2,budget.usage().leases());assertEquals(9,budget.usage().staging());}
            try(var claim=learner.prepareGeneration("generation")){claim.commit();}
            assertEquals(1,budget.usage().leases());assertEquals(0,budget.usage().staging());assertEquals(9,budget.usage().metadata());
        }
        try(var learner=budget.reserve(Unit.LEARNER,"learner",11)) {
            try(var claim=learner.prepareSource("cancelled")){assertEquals(2,budget.usage().leases());}
            try(var claim=learner.prepareSource("source")){claim.commit();}
            assertEquals(11,budget.usage().staging());assertEquals(Map.of(Unit.SOURCE,1),budget.usage().counts());
        }
        var learner=budget.reserve(Unit.LEARNER,"closed-with-claim",7);learner.prepareSource("orphan");learner.close();learner.close();
        closed(budget);assertTrue(events(budget).containsAll(List.of("GENERATION_CLAIM","GENERATION_CANCEL","GENERATION_COMMIT","SOURCE_CLAIM","SOURCE_CANCEL","SOURCE_COMMIT")));
        save("claims",budget);
    }
    @Test void failedGroupExpansionRetainsIntermediateHighWaterAndExactRollback()throws Exception {
        var budget=budget(100);
        try(var source=budget.reserve(Unit.SOURCE,"source",20);var image=budget.reserve(Unit.APPLICATION,"image",10)) {
            var initial=budget.usage();
            assertThrows(IllegalArgumentException.class,()->budget.extendSources(Map.of(source,30L),
                    List.of(reservation(Unit.APPLICATION,"temporary",60),reservation(Unit.SOURCE,"too-large",20))));
            assertEquals(initial,budget.usage());assertEquals("EXTEND_ROLLBACK",events(budget).getLast());
            assertEquals(100,budget.observations().changes().stream().mapToLong(v->v.usage().staging()).max().orElseThrow());
            var leases=budget.extendSources(Map.of(source,25L),List.of(reservation(Unit.SOURCE,"extra",5)));
            leases.forEach(MembershipResources.Lease::close);
        }
        closed(budget);save("rollback",budget);
    }
    @Test void completionHandoffAndGenerationReloadNeverExposeReleasedOriginalCharges()throws Exception {
        var budget=budget(512*MIB);var misc=budget.reserve(Unit.MISC,"current-authority",2*MIB);
        var publication=budget.reserve(Unit.APPLICATION,"publication",64*MIB);
        var additions=List.of(reservation(Unit.GENERATION,"generation-a",16),reservation(Unit.APPLICATION,"generation-a:image",8));
        var issued=budget.extendGeneration(Map.of(),additions,publication,additions.getLast());
        assertEquals(64*MIB,budget.usage().staging());publication.close();
        try(var reload=budget.prepareGenerationReload(Set.of(misc,issued.get(0),issued.get(1)))) {
            var metadata=reload.claim(Unit.GENERATION,"generation-a",10);var authority=reload.claim(Unit.MISC,"current-authority",MIB);
            var image=reload.claim(Unit.APPLICATION,"generation-a:image",4);
            assertEquals(64*MIB,budget.usage().staging());reload.commit();assertEquals(4,budget.usage().staging());
            misc.close();issued.forEach(MembershipResources.Lease::close);metadata.close();authority.close();image.close();
        }
        closed(budget);assertTrue(events(budget).contains("GENERATION_RELOAD"));save("reload",budget);
    }
    @Test void completeStorageTransferAndReplacementAreSingleObservedSwitches()throws Exception {
        var budget=budget(512*MIB);var source=budget.reserve(Unit.SOURCE,"source",20);var image=budget.reserve(Unit.APPLICATION,"image",30);
        var successors=budget.transferCompleteStorage(Map.of(source,"next-source",image,"next-image"));
        source.close();image.close();assertEquals(2,budget.usage().leases());
        var requested=List.of(reservation(Unit.GENERATION,"generation-a",10),reservation(Unit.MISC,"current-authority",20),reservation(Unit.APPLICATION,"generation-a:image",30));
        var prepared=budget.prepareCompleteReplacement(Set.copyOf(successors.values()),requested);var before=events(budget).size();
        try(var batch=prepared.commit()) {
            assertEquals(before+1,events(budget).size());assertEquals("REPLACE",events(budget).getLast());
            for(var row:requested)batch.claim(row.unit(),row.owner(),row.bytes());batch.complete();
            successors.values().forEach(MembershipResources.Lease::close);assertEquals(3,budget.usage().leases());
        }
        closed(budget);save("replacement",budget);
    }
    @Test void observationOverflowIsStickyAndCannotChangeCapacityOrRelease()throws Exception {
        var budget=new MembershipResources(METADATA_LIMIT,100,QUEUE_LIMIT,2);
        try(var one=budget.reserve(Unit.APPLICATION,"one",20);var two=budget.reserve(Unit.APPLICATION,"two",30)) {
            assertEquals(50,budget.usage().staging());assertTrue(budget.observations().truncated());
        }
        var snapshot=save("overflow",budget);assertEquals(2,snapshot.changes().size());assertEquals(5,snapshot.transitions());assertEquals(0,snapshot.current().leases());
        assertThrows(UnsupportedOperationException.class,()->snapshot.changes().clear());
        assertThrows(UnsupportedOperationException.class,()->snapshot.changes().get(1).added().clear());
        var disabled=new MembershipResources(100);assertThrows(IllegalArgumentException.class,disabled::observations);
        assertThrows(IllegalArgumentException.class,()->new MembershipResources(METADATA_LIMIT,100,QUEUE_LIMIT,-1));
    }
    @Test void diagnosticFailureCannotEnterRollbackAfterAtomicOwnershipSwitch()throws Exception {
        var budget=budget(100);var lease=budget.reserve(Unit.SOURCE,"source",20);
        // Corrupt only the opt-in diagnostic's private prior map, after admission.
        // A failing observation must not roll back an already committed handoff.
        var field=MembershipResources.class.getDeclaredField("observations");field.setAccessible(true);
        var journal=field.get(budget);var prior=MembershipResourceObservations.class.getDeclaredField("prior");prior.setAccessible(true);prior.set(journal,null);
        var next=budget.transferStorage(Map.of(lease,"successor")).get(lease);lease.close();
        assertEquals(20,budget.usage().staging());assertTrue(budget.observations().failed());next.close();
        assertEquals(0,budget.usage().leases());save("failed-observation",budget);
    }
    @Test void concurrentReservationsRemainOneOrderedResourceHistory()throws Exception {
        var budget=budget(512*MIB);
        try(var executor=Executors.newFixedThreadPool(4)) {
            var tasks=new ArrayList<Future<?>>();
            for(int worker=0;worker<4;worker++){int id=worker;tasks.add(executor.submit(()->{
                for(int i=0;i<12;i++)try(var lease=budget.reserve(Unit.CONTROL,id+"-"+i,4)){lease.reserveControl(8);}
            }));}
            for(var task:tasks)task.get(30,TimeUnit.SECONDS);
        }
        closed(budget);assertEquals(145,budget.observations().transitions());save("concurrent",budget);
    }
}
