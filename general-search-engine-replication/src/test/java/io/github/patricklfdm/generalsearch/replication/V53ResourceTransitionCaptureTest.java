package io.github.patricklfdm.generalsearch.replication;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53ResourceTransitionCaptureTest {
    @TempDir Path temp;
    static Path evidence;
    static final String ROOT="a".repeat(64);
    @BeforeAll static void output()throws Exception {
        evidence=Files.createDirectories(Path.of("target/v53-resource-capture/run-"+UUID.randomUUID()));
        System.out.println("v53ResourceCaptureEvidence="+evidence.toAbsolutePath());
    }
    static MembershipIdentity identity(int i) {
        return new MembershipIdentity(new ReplicationNodeId("node-"+i),new UUID(0,i),new ReplicationEndpoint("127.0.0.1",12000+i));
    }
    @Test void actualBudgetsRetainEveryEventAndLateJoiningRegistration()throws Exception {
        var root=Files.createDirectory(evidence.resolve("owners"));var capture=new V53ResourceTransitionCapture(root,ROOT);
        var old=capture.create(identity(1),0);var events=new ArrayList<Map<String,Object>>();
        try(var lease=old.reserve(Unit.JOURNAL,"journal",20)) {
            events.add(Map.of("node","node-1","event","OPEN"));capture.event(0,events.getLast());
            var joining=capture.create(identity(2),1);
            try(var learner=joining.reserve(Unit.LEARNER,"learner",30)) {
                events.add(Map.of("node","node-2","event","RETAIN","scope","joining-owner"));capture.event(1,events.getLast());
            }
            events.add(Map.of("node","node-2","event","CLOSE"));capture.event(2,events.getLast());
            assertEquals(3,joining.observations().transitions());
        }
        events.add(Map.of("node","node-1","event","CLOSE"));capture.event(3,events.getLast());
        byte[] raw=V53EvidenceArray.encode(events,8192);Files.write(root.resolve("events.json"),raw);capture.save(raw);
        var index=object(parse(Files.readAllBytes(root.resolve(V53ResourceTransitionCapture.DIRECTORY+"/index.json")),16384));
        assertEquals(hash(raw),index.get("eventsSha256"));var owners=list(index.get("owners"));assertEquals(2,owners.size());
        assertEquals(0L,object(owners.get(0)).get("registeredAt"));assertEquals(1L,object(owners.get(1)).get("registeredAt"));
        assertThrows(IllegalArgumentException.class,()->capture.save(raw));
        assertThrows(IllegalArgumentException.class,()->capture.create(identity(3),4));
    }
    @Test void registrationAndEventOmissionsCannotBeSilentlyIgnored()throws Exception {
        var capture=new V53ResourceTransitionCapture(temp,ROOT);var first=capture.create(identity(1),0);
        assertThrows(IllegalArgumentException.class,()->capture.create(identity(1),0));
        assertThrows(IllegalArgumentException.class,()->capture.create(identity(2),1));
        assertThrows(IllegalArgumentException.class,()->capture.event(0,Map.of("node","node-2","event","OPEN")));
        assertThrows(IllegalArgumentException.class,()->capture.event(1,Map.of("node","node-1","event","OPEN")));
        capture.event(0,Map.of("node","node-1","event","OPEN"));
        assertEquals(1,first.observations().transitions());
    }
    @Test void sealedEventsBindAllResourceIndexesWithoutAWholeArrayArgument()throws Exception {
        var root=Files.createDirectory(evidence.resolve("spooled"));
        var capture=new V53ResourceTransitionCapture(root,ROOT,List.of("node-1","node-2"),true);
        var old=capture.create(identity(1),0);var rows=new ArrayList<Map<String,Object>>();
        var events=new V53EvidenceSpool(root.resolve("events.json"),4096,(index,row)->{capture.event(index,row);rows.add(row);});
        try(events) {
            try(var journal=old.reserve(Unit.JOURNAL,"journal",20)) {
                events.add(Map.of("node","node-1","event","OPEN"));var joining=capture.create(identity(2),1);
                try(var learner=joining.reserve(Unit.LEARNER,"learner",30)) {
                    events.add(Map.of("node","node-2","event","RETAIN"));
                }
                events.add(Map.of("node","node-2","event","CLOSE"));
            }
            events.add(Map.of("node","node-1","event","CLOSE"));
            assertThrows(IllegalArgumentException.class,()->capture.save(events));
            assertFalse(Files.exists(root.resolve(V53ResourceTransitionCapture.DIRECTORY+"/index.json")));
        }
        String property="v53.resource.storage.transfers",previous=System.getProperty(property);
        try {System.setProperty(property,"true");capture.save(events);}
        finally {if(previous==null)System.clearProperty(property);else System.setProperty(property,previous);}
        byte[] bytes=Files.readAllBytes(root.resolve("events.json"));assertArrayEquals(V53EvidenceArray.encode(rows,4096),bytes);
        for(String name:List.of(V53ResourceTransitionCapture.DIRECTORY,"storage-transfer-captures","control-close-captures")) {
            var index=object(parse(Files.readAllBytes(root.resolve(name+"/index.json")),16384));
            assertEquals(hash(bytes),index.get("eventsSha256"));assertEquals(2,list(index.get("owners")).size());
        }
        var points=list(parse(Files.readAllBytes(root.resolve(V53ResourceTransitionCapture.DIRECTORY+"/boundaries.json")),16384));
        assertEquals(rows.size(),points.size());
        for(int i=0;i<rows.size();i++) {
            assertEquals((long)i,object(points.get(i)).get("eventIndex"));assertEquals(rows.get(i).get("node"),object(points.get(i)).get("node"));
        }
        assertThrows(IllegalArgumentException.class,()->capture.save(events));
    }
    @Test void failedOrForeignSpoolsCannotProduceAResourceIndex()throws Exception {
        for(boolean failed:List.of(false,true)) {
            var root=Files.createDirectory(evidence.resolve("rejected-"+failed));var capture=new V53ResourceTransitionCapture(root,ROOT);
            capture.create(identity(1),0);
            var events=new V53EvidenceSpool(root.resolve(failed?"events.json":"foreign.json"),4096,(index,row)->{
                capture.event(index,row);if(failed)throw new IllegalArgumentException("incomplete observer");
            });
            if(failed) {
                assertThrows(IllegalArgumentException.class,()->events.add(Map.of("node","node-1","event","OPEN")));
                assertThrows(RuntimeException.class,events::close);
            }else {events.add(Map.of("node","node-1","event","OPEN"));events.close();}
            assertThrows(IllegalArgumentException.class,()->capture.save(events));
            assertFalse(Files.exists(root.resolve(V53ResourceTransitionCapture.DIRECTORY+"/index.json")));
        }
    }
    @Test void lightweightCheckpointsAreExactImmutableAndDoNotAppendChanges() {
        var budget=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,3);
        var start=budget.observationCheckpoint();assertEquals(0,start.sequence());assertTrue(start.complete());
        var lease=budget.reserve(Unit.CONTROL,"message",2);var held=budget.observationCheckpoint();
        for(int i=0;i<100;i++)assertEquals(held,budget.observationCheckpoint());
        lease.reserveControl(4);lease.close();var end=budget.observationCheckpoint();
        assertEquals(3,end.sequence());assertFalse(end.complete());assertEquals(0,end.usage().leases());
        assertEquals(2,held.usage().queued());assertEquals(0,start.usage().queued());
        assertThrows(IllegalArgumentException.class,()->new MembershipResources(512*MIB).observationCheckpoint());
    }
    @Test void longJournalUsesPerChangeEncodingBeyondOneMessageTokenLimit()throws Exception {
        var budget=new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,8192);
        for(int i=0;i<3000;i++)try(var lease=budget.reserve(Unit.CONTROL,"message",8)) {assertEquals(8,budget.usage().queued());}
        var path=evidence.resolve("long.json");String digest=V53ResourceTraceFiles.write(path,budget.observations());
        byte[] raw=Files.readAllBytes(path);assertEquals(hash(raw),digest);assertTrue(raw.length>1024*1024);
        assertEquals(6001,budget.observations().transitions());
        assertThrows(IllegalArgumentException.class,()->parse(raw,V53ResourceTraceFiles.MAXIMUM));
    }
    @Test void unfinishedLifetimeIsRetainedWithoutClaimingClosed()throws Exception {
        var root=Files.createDirectory(evidence.resolve("unclosed"));var capture=new V53ResourceTransitionCapture(root,ROOT);
        var budget=capture.create(identity(1),0);var lease=budget.reserve(Unit.SOURCE,"retained",8);
        var row=Map.<String,Object>of("node","node-1","event","OPEN");capture.event(0,row);
        byte[] events=V53EvidenceArray.encode(List.of(row),8192);Files.write(root.resolve("events.json"),events);capture.save(events);
        assertEquals(1,budget.observations().current().leases());lease.close();
    }
    @Test void originalJournalCloseHasTwoBoundariesAndAllowsExclusiveReopen()throws Exception {
        var raw=Files.createDirectory(evidence.resolve("original-close"));
        var fixture=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);var target=fixture.request.targets().getFirst();
        var capture=new V53ResourceTransitionCapture(raw,fixture.result.root().manifestDigest(),List.of("node-1"));
        var budget=capture.create(target.identity(),0);
        var events=new ArrayList<Map<String,Object>>() {
            @Override public boolean add(Map<String,Object> row){capture.event(size(),row);return super.add(row);}
        };
        try(var journal=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),
                fixture.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,
                event->events.add(Map.of("node","node-1","event",event)))) {
            int before=budget.usage().leases();assertTrue(before>0);
            capture.closeOwner(journal,events);assertEquals(0,budget.usage().leases());
            assertEquals("RESOURCE_OWNER_CLOSE_BEGIN",events.get(events.size()-2).get("event"));
            assertEquals("RESOURCE_OWNER_CLOSE_RETURNED",events.getLast().get("event"));
            assertThrows(Exception.class,journal::activationContext);
            assertThrows(IllegalArgumentException.class,()->capture.closeOwner(journal,events));
        }
        byte[] bytes=V53EvidenceArray.encode(events,1024*1024);Files.write(raw.resolve("events.json"),bytes);capture.save(bytes);
        var index=object(parse(Files.readAllBytes(raw.resolve(V53ResourceTransitionCapture.DIRECTORY+"/index.json")),16384));
        assertEquals("gse-v53-resource-capture-index-v2",index.get("schema"));assertEquals(List.of("node-1"),index.get("closingOwners"));
        try(var reopened=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),fixture.result.root(),
                target.identity(),new MembershipResources(512*MIB),MembershipGrantJournal.MAXIMUM,event->{})) {
            assertEquals(target.identity(),reopened.activationIdentity());
        }
    }
    @Test void alreadyClosedJournalCannotMasqueradeAsOriginalClose()throws Exception {
        var raw=Files.createDirectory(evidence.resolve("second-close"));
        var fixture=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);var target=fixture.request.targets().getFirst();
        var capture=new V53ResourceTransitionCapture(raw,fixture.result.root().manifestDigest(),List.of("node-1"));
        var budget=capture.create(target.identity(),0);var events=new ArrayList<Map<String,Object>>();
        var journal=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),fixture.result.root(),
                target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{});
        journal.close();assertThrows(Exception.class,()->capture.closeOwner(journal,events));assertTrue(events.isEmpty());
    }
    @Test void closeOwnerDeclarationCannotHideDuplicatesOrForeignNodes()throws Exception {
        for(var nodes:List.of(List.of("node-1","node-1"),List.of("node-2","node-1"),List.of("foreign")))
            assertThrows(IllegalArgumentException.class,()->new V53ResourceTransitionCapture(temp,ROOT,nodes));
    }
}
