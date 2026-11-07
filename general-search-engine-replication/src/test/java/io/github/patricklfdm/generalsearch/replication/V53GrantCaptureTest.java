package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Small actual writer exercise, not the complete joining history. */
class V53GrantCaptureTest {
    @TempDir Path temp;
    @Test void retainsCompleteOriginalGrantsWithoutReleasingTheLiveWriterLock()throws Exception {
        capture(false);
    }
    @Test void segmentedBackupGrantsPreserveOriginalBytesAndTheLiveWriterLock()throws Exception {
        capture(true);
    }
    private void capture(boolean backup)throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-grant-capture/run-"+UUID.randomUUID()));
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,3,backup);
        f.ownedHistory=true;
        var target=f.request.targets().getFirst();
        try(var owner=f.open(target,"initialize")) {
            owner.initializePeerRetention();owner.initializeLearnerRetention();owner.initializeFutureRetention();
        }
        var events=new ArrayList<Map<String,Object>>();var capture=backup?
                new V53GrantCapture(raw,events,f.request.source(),V53WireArchive.Layout.SEGMENTED_BACKUP):new V53GrantCapture(raw,events);
        f.observer=(member,operation,event)->{
            events.add(Map.of("node",member.identity().nodeId().value(),"scope","test-owner","event",event));
            capture.at(member.identity().nodeId().value(),"test-owner",member.replicaDirectory(),event);
        };
        try(var owner=f.open(target,"prepare")) {
            Map<String,Object> first=null;
            for(long counter:List.of(2L,3L)) {
                var ballot=Map.<String,Object>of("counter",counter,"proposer",target.identity().nodeId().value(),
                        "incarnation",target.identity().storageId().toString());
                var basis=owner.prepareCurrent(ballot);
                var row=events.getLast();assertEquals(V53GrantCapture.EVENT,row.get("event"));
                Path copied=raw.resolve((String)row.get("capture"));
                byte[] metadata=Files.readAllBytes(copied.resolve("capture.json"));
                var value=object(parse(metadata,1024*1024));assertEquals(hash(metadata),row.get("sha256"));
                assertEquals(basis.digest(),value.get("basisSha256"));
                assertEquals(V53GrantCapture.inventory(target.replicaDirectory()),V53GrantCapture.inventory(copied.resolve("replica")));
                // A fresh FileChannel for a live lock inode could silently release
                // the process lock on POSIX. Probe from a separate JVM after reads.
                new V53MembershipOwnershipTest().probe(target.replicaDirectory().resolve("replica.lock"));
                if(first==null)first=V53GrantCapture.inventory(copied.resolve("replica"));
                else assertEquals(first,V53GrantCapture.inventory(raw.resolve("grant-captures/capture-0001/replica")));
            }
        }
        Files.write(raw.resolve("events.json"),canonical(events,8*1024*1024),StandardOpenOption.CREATE_NEW);
        assertThrows(FileAlreadyExistsException.class,()->new V53GrantCapture(raw,new ArrayList<>()));
        System.out.println("v53GrantCaptureEvidence="+raw.toAbsolutePath());
        System.out.println("v53GrantCaptureSource="+f.request.source());
    }
    @Test void ignoresUnrelatedCutsAndRefusesIncompleteOrUnownedCaptures()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var capture=new V53GrantCapture(temp,events);
        capture.at("node-1","test-owner",temp.resolve("absent"),"PROMISE_WRITTEN");
        assertTrue(events.isEmpty());assertThrows(Exception.class,()->capture.at("node-1","test-owner",temp.resolve("absent"),"GRANT_BEFORE_RETURN"));
        assertThrows(IllegalArgumentException.class,()->V53GrantCapture.journal(new byte[0]));
        assertThrows(IllegalArgumentException.class,()->V53GrantCapture.journal(new byte[47]));
        var trace=new V53JoiningTrace("node-4",events,new ArrayList<>());trace.retainGrants(capture,temp.resolve("absent"));
        assertThrows(IllegalStateException.class,()->trace.retainGrants(capture,temp));
        assertThrows(Exception.class,()->trace.cut("retaining-owner").at("GRANT_BEFORE_RETURN"));
        assertFalse(events.stream().anyMatch(e->V53GrantCapture.EVENT.equals(e.get("event"))));
    }
}
