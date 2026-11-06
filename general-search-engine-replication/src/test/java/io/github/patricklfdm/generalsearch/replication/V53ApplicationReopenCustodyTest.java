package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Real retained application bytes must already have custody at peer-ledger reseal. */
class V53ApplicationReopenCustodyTest {
    @TempDir Path temp;
    static final class Stop extends IOException {}
    static MembershipResources resources() {
        return new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM);
    }
    static void charged(MembershipResources resources,long bytes) {
        var state=new HashMap<String,MembershipResourceObservations.Charge>();var snapshot=resources.observations();
        assertFalse(snapshot.failed());assertFalse(snapshot.truncated());
        for(var change:snapshot.changes()) {
            for(var old:change.removed())state.remove(old.unit()+":"+old.owner());
            for(var value:change.added())state.put(value.unit()+":"+value.owner(),value);
        }
        var charge=state.get("APPLICATION:applied-end");assertNotNull(charge,"retained image missing at peer-ledger reseal");
        assertEquals("",charge.claimSource());assertTrue(charge.bytes()>=bytes);
    }
    @Test void retainedImagePrecedesPeerResealAndEveryFailedOpenReleasesItsCustody()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("evidence"));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("group")),raw,3,false);
        f.ownedHistory=true;f.nativeApplication=true;
        for(var target:f.request.targets())try(var owner=f.open(target,"initialize-retention")) {
            owner.initializePeerRetention();owner.initializeFutureRetention();
        }
        f.campaign(1);
        f.observer=(target,operation,event)->{if(operation.equals("apply-1") && event.equals("APPLY_ACK_DIRECTORY_FORCED"))throw new Stop();};
        assertThrows(Stop.class,()->f.publish(1,false));f.observer=(target,operation,event)->{};
        var target=f.request.targets().getFirst();Path directory=target.replicaDirectory();
        Path image=directory.resolve("applied-end/application.image");assertTrue(Files.size(image)>0);
        var original=V53ReplayFilesTest.files(directory);
        var points=List.of("RETENTION_RECOVERY_ACTIVE_FORCED","RETENTION_RECOVERY_PARENT_FORCED");
        for(String stop:List.of(points.get(0),points.get(1),"none")) {
            var resources=resources();var seen=new ArrayList<String>();
            MembershipBallotAllocator.Cut cut=event->{if(points.contains(event)) {
                charged(resources,Files.size(image));seen.add(event);if(event.equals(stop))throw new Stop();
            }};
            try {
                if(stop.equals("none")) {
                    try(var owner=MembershipGrantJournal.openRetainingFuturePeers(directory,target.materialization().directory(),
                            f.result.root(),target.identity(),resources,MembershipGrantJournal.MAXIMUM,cut)) {
                        assertTrue(owner.currentCertificate().isPresent());charged(resources,Files.size(image));
                    }
                    assertEquals(points,seen);
                }else {
                    assertThrows(Stop.class,()->MembershipGrantJournal.openRetainingFuturePeers(directory,target.materialization().directory(),
                            f.result.root(),target.identity(),resources,MembershipGrantJournal.MAXIMUM,cut));
                    assertEquals(points.subList(0,points.indexOf(stop)+1),seen);
                }
            }finally{assertEquals(0,resources.usage().leases());}
            assertEquals(original,V53ReplayFilesTest.files(directory));
        }
        // Invalid application inventory must reject before either peer reseal;
        // the failing constructor must release the journal and generation owners.
        Files.writeString(directory.resolve("applied-end/foreign.gsr"),"invalid");
        var damaged=V53ReplayFilesTest.files(directory);var resources=resources();var seen=new ArrayList<String>();
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openRetainingFuturePeers(directory,target.materialization().directory(),
                f.result.root(),target.identity(),resources,MembershipGrantJournal.MAXIMUM,event->{if(points.contains(event))seen.add(event);}));
        assertTrue(seen.isEmpty());assertEquals(0,resources.usage().leases());assertEquals(damaged,V53ReplayFilesTest.files(directory));
    }
}
