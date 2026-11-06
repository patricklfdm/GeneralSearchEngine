package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53JoiningOwnerCloseTest {
    @TempDir Path temp;
    private V53BootstrapPublicationTest.Fixture fixture()throws Exception {
        return new V53BootstrapPublicationTest.Fixture(Files.createDirectories(temp.resolve("owners")),Files.createDirectories(temp.resolve("raw")),3,false);
    }
    private MembershipGrantJournal open(V53BootstrapPublicationTest.Fixture f,MembershipResources budget)throws Exception {
        var target=f.request.targets().getFirst();
        return MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),
                f.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{});
    }
    @Test void actualJournalHasOneOpenBeginAndSuccessfulReturnAcrossExplicitAndScopeClose()throws Exception {
        var f=fixture();var budget=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,1024);
        var events=new ArrayList<String>();var sequences=new ArrayList<Long>();
        try(var journal=open(f,budget);var observed=new V53JoiningOwnerClose(journal,event->{
            events.add(event);sequences.add(budget.observationCheckpoint().sequence());
        })) {
            assertTrue(budget.usage().leases()>0);observed.close();assertEquals(0,budget.usage().leases());
            observed.close();
        }
        assertEquals(List.of(V53JoiningOwnerClose.OPEN,V53JoiningOwnerClose.BEGIN,V53JoiningOwnerClose.RETURNED),events);
        assertEquals(sequences.get(0),sequences.get(1));assertTrue(sequences.get(1)<sequences.get(2));
        for(var row:budget.observations().changes().subList(sequences.get(1).intValue()+1,sequences.get(2).intValue()+1))
            assertEquals("RELEASE",row.event());
        try(var reopened=open(f,budget);var observed=new V53JoiningOwnerClose(reopened,events::add)) {
            assertTrue(budget.usage().leases()>0);
        }
        assertEquals(6,events.size());assertEquals(0,budget.usage().leases());
    }
    @Test void nullConditionalOwnerCannotInventALifetime()throws Exception {
        var events=new ArrayList<String>();try(var observed=new V53JoiningOwnerClose(null,events::add)){observed.close();}
        assertTrue(events.isEmpty());
    }
    @Test void fiveActualReopensRetainTheirOwnResourceCloseIntervals()throws Exception {
        var f=fixture();var budget=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,1024);
        var events=new ArrayList<Map<String,Object>>();var boundaries=new ArrayList<Map<String,Object>>();
        for(String scope:List.of("initial-owner","retaining-owner","repeated-basis-owner","continuation-owner","stable-cold-owner")) {
            try(var journal=open(f,budget);var observed=new V53JoiningOwnerClose(journal,event->{
                var checkpoint=budget.observationCheckpoint();assertTrue(checkpoint.complete());
                boundaries.add(Map.of("eventIndex",events.size(),"node","node-1","sequence",checkpoint.sequence(),
                        "usage",V53ResourceTraceFiles.usage(checkpoint.usage())));
                events.add(Map.of("node","node-1","scope",scope,"event",event));
            })) { assertNotNull(journal.activationContext()); }
            assertEquals(0,budget.usage().leases());
        }
        var output=Files.createDirectories(Path.of("target/v53-joining-close/run-"+UUID.randomUUID()));
        Files.write(output.resolve("events.json"),V53EvidenceArray.encode(events,1024*1024));
        Files.write(output.resolve("boundaries.json"),V53EvidenceArray.encode(boundaries,1024*1024));
        V53ResourceTraceFiles.write(output.resolve("node-1.json"),budget.observations());
        System.out.println("v53JoiningCloseComponentEvidence="+output.toAbsolutePath());
    }
    @Test void closedOwnerCannotBeRegisteredOrReportedAsSuccessfulClose()throws Exception {
        var f=fixture();var budget=new MembershipResources(512*MIB);var events=new ArrayList<String>();
        try(var journal=open(f,budget)) {
            var observed=new V53JoiningOwnerClose(journal,events::add);journal.close();
            assertThrows(Exception.class,observed::close);assertEquals(List.of(V53JoiningOwnerClose.OPEN),events);
            observed.close();assertEquals(1,events.size());
            assertThrows(Exception.class,()->new V53JoiningOwnerClose(journal,events::add));assertEquals(1,events.size());
        }
    }
    @Test void failedObservationCannotProduceReturnOrRetryItsClose()throws Exception {
        var f=fixture();var budget=new MembershipResources(512*MIB);var events=new ArrayList<String>();
        try(var journal=open(f,budget)) {
            var observed=new V53JoiningOwnerClose(journal,event->{events.add(event);if(event.equals(V53JoiningOwnerClose.BEGIN))throw new IOException("observation failure");});
            assertEquals("observation failure",assertThrows(IOException.class,observed::close).getMessage());
            observed.close();assertEquals(List.of(V53JoiningOwnerClose.OPEN,V53JoiningOwnerClose.BEGIN),events);
            assertNotNull(journal.activationContext());assertTrue(budget.usage().leases()>0);
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void disabledTraceAddsNoMarkersAndEnabledTraceBindsOriginalScope()throws Exception {
        var f=fixture();var budget=new MembershipResources(512*MIB);var events=new ArrayList<Map<String,Object>>();
        String key="v53.resource.joined.close",previous=System.getProperty(key);
        try {
            System.clearProperty(key);var trace=new V53JoiningTrace("node-1",events,new ArrayList<>());
            try(var journal=open(f,budget);var observed=trace.ownerClose("initial-owner",journal)){}
            assertTrue(events.isEmpty());System.setProperty(key,"true");
            try(var journal=open(f,budget);var observed=trace.ownerClose("retaining-owner",journal)) {
                var foreign=new V53JoiningTrace("node-6",events,new ArrayList<>());
                assertThrows(IllegalArgumentException.class,()->foreign.ownerClose("foreign-owner",journal));
            }
            assertEquals(3,events.size());assertTrue(events.stream().allMatch(v->v.get("scope").equals("retaining-owner") && v.get("node").equals("node-1")));
        }finally{if(previous==null)System.clearProperty(key);else System.setProperty(key,previous);}
    }
}
