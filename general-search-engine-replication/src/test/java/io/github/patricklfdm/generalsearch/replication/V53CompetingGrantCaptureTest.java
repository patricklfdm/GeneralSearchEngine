package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Two actual writer grants from different proposer identities. This focused
 * exercise is not an autonomous election or a complete competition history. */
class V53CompetingGrantCaptureTest {
    @TempDir Path temp;

    @Test void keepsEveryGrantLinkedToTheOriginalTimelineAndPreservesTheLiveLock()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-competing-grant-capture/run-"+UUID.randomUUID()));
        var fixture=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);fixture.ownedHistory=true;
        for(var target:fixture.request.targets())try(var owner=fixture.open(target,"initialize")) {
            owner.initializePeerRetention();owner.initializeFutureRetention();
        }
        fixture.snapshot("before-network");
        var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var captures=new V53CompetingGrantCapture(raw,events);
        fixture.observer=(target,operation,event)->captures.at(target.identity().nodeId().value(),target.replicaDirectory(),event);
        var target=fixture.request.targets().getFirst();Map<String,Object> first=null;
        try(var owner=fixture.open(target,"prepare")) {
            for(int i=0;i<2;i++) {
                var proposer=fixture.request.targets().get(i).identity();
                owner.prepareCurrent(Map.of("counter",2L+i,"proposer",proposer.nodeId().value(),"incarnation",proposer.storageId().toString()));
                new V53MembershipOwnershipTest().probe(target.replicaDirectory().resolve("replica.lock"));
                var observed=V53GrantCapture.inventory(raw.resolve("grant-captures/capture-0001/replica"));
                if(first==null)first=observed;else assertEquals(first,observed);
            }
        }
        // A later original event bounds the second capture timestamp, too.
        V53CompetingNodeQualification.observe(events,Map.of("node","node-2","event","NODE_OPEN"));
        captures.save();Files.write(raw.resolve("events.json"),canonical(events,16*1024*1024),StandardOpenOption.CREATE_NEW);
        var links=(List<?>)parse(Files.readAllBytes(raw.resolve(V53CompetingGrantCapture.FILE)),1024*1024);
        assertEquals(2,links.size());assertEquals(2,events.stream().filter(v->v.get("event").equals("GRANT_BEFORE_RETURN")).count());
        assertTrue(events.stream().noneMatch(v->v.get("event").equals(V53GrantCapture.EVENT)));
        for(var value:links) {
            var row=object(value);int at=(int)number(row.get("returnEvent")),after=(int)number(row.get("capturedAfterEvent"));
            assertEquals("GRANT_BEFORE_RETURN",events.get(at).get("event"));assertEquals(row.get("node"),events.get(at).get("node"));
            assertTrue(after>=at);assertTrue(number(row.get("nanoTime"))>=number(events.get(after).get("nanoTime")));
            assertTrue(number(row.get("nanoTime"))<=number(events.get(after+1).get("nanoTime")));
        }
        assertThrows(FileAlreadyExistsException.class,captures::save);
        System.out.println("v53CompetingGrantCaptureEvidence="+raw.toAbsolutePath());
    }

    @Test void failedCopyRetainsTheReturnAndNeverInventsACompletedMarker()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var capture=new V53CompetingGrantCapture(temp,events);
        assertThrows(Exception.class,()->capture.at("node-1",temp.resolve("missing"),"GRANT_BEFORE_RETURN"));
        capture.save();assertEquals(1,events.size());
        assertEquals(List.of(),parse(Files.readAllBytes(temp.resolve(V53CompetingGrantCapture.FILE)),1024*1024));
        assertThrows(FileAlreadyExistsException.class,()->new V53CompetingGrantCapture(temp,events));
    }
}
