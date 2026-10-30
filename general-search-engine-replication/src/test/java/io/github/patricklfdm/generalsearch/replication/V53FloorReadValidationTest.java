package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original native floor bytes remain mandatory across calls and mutation cuts. */
class V53FloorReadValidationTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture(String name,boolean publish)throws Exception {
        var helper=new V53PeerRetentionFilesTest();helper.temp=temp;var f=helper.fixture(name);f.nativeApplication=true;
        for(var target:f.request.targets())try(var owner=f.open(target,"initialize-ledgers")) {
            owner.initializePeerRetention();owner.initializeLearnerRetention();owner.initializeFutureRetention();
        }
        f.campaign(1);if(publish)f.publish(1,false);return f;
    }
    List<MembershipFloor.Copy> copies(V53BootstrapPublicationTest.Fixture f)throws Exception {
        var copies=new ArrayList<MembershipFloor.Copy>();
        for(var target:f.request.targets().subList(0,2))try(var owner=f.open(target,"floor-original")){copies.add(owner.floorCopyCurrent());}
        return copies;
    }
    @Test void eachNativeReadRequiresOriginalBytesAndInodesAfterEarlierSuccessOrFailure()throws Exception {
        var f=fixture("read",true);var originals=copies(f);var target=f.request.targets().getFirst();
        Path directory=target.replicaDirectory();
        try(var owner=f.open(target,"read-validation")) {
            byte[] floor=owner.establishFloor(originals).bytes();
            var usage=f.resources.usage();
            var members=new ArrayList<Path>(List.of(directory.resolve("grants.gsr"),directory.resolve("floor-copies/floor.gsr")));
            for(var original:originals)for(String name:List.of("generation.gsr","source.gscp",original.capsule.terminal().application()+".image"))
                members.add(directory.resolve("floor-copies").resolve(original.generation.digest()).resolve(name));
            for(Path member:members) {
                assertArrayEquals(floor,owner.governingFloor().orElseThrow().bytes());
                byte[] good=Files.readAllBytes(member),bad=good.clone();bad[bad.length-1]^=1;
                try {
                    Files.write(member,bad);assertThrows(Exception.class,owner::governingFloor,member.toString());
                    assertArrayEquals(bad,Files.readAllBytes(member),"read-only validation cannot repair the original");
                }finally{Files.write(member,good);}
                assertArrayEquals(floor,owner.governingFloor().orElseThrow().bytes());
                assertEquals(usage,f.resources.usage());
            }
            Path member=members.getLast(),saved=temp.resolve("saved-original");
            Files.move(member,saved);Files.copy(saved,member);
            try{assertThrows(IllegalArgumentException.class,owner::governingFloor);}
            finally{Files.delete(member);Files.move(saved,member);}
            assertArrayEquals(floor,owner.governingFloor().orElseThrow().bytes());
            owner.observeCurrent(Map.of("counter",999L,"proposer",target.identity().nodeId().value(),"incarnation",target.identity().storageId().toString()));
            assertThrows(IllegalArgumentException.class,()->owner.checkActivationBallot(originals.getFirst().capsule.context.authority(),f.ballot));
            // Reading historical authority does not erase the higher observed fence.
            assertArrayEquals(floor,owner.governingFloor().orElseThrow().bytes());
            assertThrows(IllegalArgumentException.class,()->owner.checkActivationBallot(originals.getFirst().capsule.context.authority(),f.ballot));
            assertEquals(usage,f.resources.usage());
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void completedReadCannotSuppressJournalChecksAfterReleaseForceCallback()throws Exception {
        var f=fixture("release",false);var originals=copies(f);var target=f.request.targets().getFirst();
        var events=new ArrayList<String>();Path journal=target.replicaDirectory().resolve("grants.gsr");
        try(var owner=f.open(target,"release-validation")) {
            owner.establishFloor(originals);owner.governingFloor().orElseThrow();
            byte[] good=Files.readAllBytes(journal),bad=good.clone();bad[bad.length-1]^=1;
            f.observer=(member,operation,event)->{
                if(member.equals(target) && operation.equals("release-validation")) {
                    events.add(event);if(event.equals("FLOOR_RELEASE_PARENT_FORCED"))Files.write(journal,bad);
                }
            };
            try {
                assertEquals(ReplicationException.Reason.CONFLICTING_HISTORY,
                        assertThrows(ReplicationException.class,owner::releaseFloor).reason());
                assertTrue(events.contains("FLOOR_RELEASE_PARENT_FORCED"));assertFalse(events.contains("FLOOR_RELEASE_RELINQUISHED"));
                assertArrayEquals(bad,Files.readAllBytes(journal));
                assertTrue(Files.exists(target.replicaDirectory().resolve("floor-copies/floor.gsr")));
            }finally{Files.write(journal,good);}
            assertThrows(IllegalArgumentException.class,owner::governingFloor,"restoring bytes must not revive the failed writer");
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
