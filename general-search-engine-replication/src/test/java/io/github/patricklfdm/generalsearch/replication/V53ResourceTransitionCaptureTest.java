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
}
