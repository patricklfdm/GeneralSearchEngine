package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53NativeApplicationTest {
    @TempDir Path temp;
    static final class Stop extends IOException {}
    static V53BootstrapPublicationTest.Fixture certified(Path home,Path raw)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(home,raw,3,false);f.ownedHistory=true;f.nativeApplication=true;f.campaign(1);
        f.observer=(target,operation,event)->{if(operation.equals("apply-1"))throw new Stop();};
        assertThrows(Stop.class,()->f.publish(1,false));f.observer=(target,operation,event)->{};f.observations.clear();return f;
    }
    static void save(V53BootstrapPublicationTest.Fixture f)throws Exception {
        Files.write(f.raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
    }
    @Test void nativeReopenAppliesAndPublishesAllStableSizesAndSourceKinds()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-native-application/histories-"+UUID.randomUUID()));
        System.out.println("v53NativeApplicationEvidence="+root.toAbsolutePath());
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            String name="size-"+size+"-"+(backup?"backup":"empty");
            var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),Files.createDirectory(root.resolve(name)),size,backup);
            f.ownedHistory=true;f.nativeApplication=true;
            try {
                f.campaign(1);f.publish(1,false);f.observations.clear();f.publish(2,true);f.observations.clear();f.campaign(2);f.publish(3,false);
                for(var row:f.calls)if(((String)row.get("operation")).startsWith("apply-")) {
                    var events=list(row.get("events"));assertTrue(events.indexOf("CERTIFICATE_ACTIVE_PARENT_FORCED")<events.indexOf("NATIVE_CERTIFICATE_RETAINED"));
                    assertTrue(events.indexOf("NATIVE_CERTIFICATE_RETAINED")<events.indexOf("APPLY_BEFORE_RETURN"));
                }
                Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","nativeApplication",true,"publications",3L),16384));
            }finally{save(f);}
        }
    }
    @Test void noCallerObservationsAreNeededButUncertifiedOrUnownedInputsStillReject()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-native-application/guards-"+UUID.randomUUID()));
        var f=certified(Files.createDirectory(temp.resolve("guard")),raw);var t=f.request.targets().getFirst();
        try {
            var before=V53ReplayFilesTest.files(t.replicaDirectory());
            try(var owner=f.open(t,"reject-unobserved")) {
                assertThrows(IllegalArgumentException.class,()->owner.applyCurrent(builder().configuration(),t.materialization(),Set.of()));
            }
            assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));f.ownedHistory=false;
            try(var owner=f.open(t,"reject-unowned")) {
                assertThrows(IllegalArgumentException.class,()->owner.applyCurrent(builder().configuration(),t.materialization()));
            }
            assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));f.ownedHistory=true;
            var original=Files.readAllBytes(t.replicaDirectory().resolve(MembershipPendingAccept.FILE));
            var vote=MembershipPendingAccept.decode(original);
            Files.write(t.replicaDirectory().resolve(MembershipPendingAccept.FILE),vote.withCertificate(null).bytes());
            try(var owner=f.open(t,"reject-proof-only")) {
                assertThrows(IllegalArgumentException.class,()->owner.applyCurrent(builder().configuration(),t.materialization()));
            }
            assertFalse(Files.exists(t.replicaDirectory().resolve(MembershipAppliedEndFiles.DIRECTORY)));
            Files.write(t.replicaDirectory().resolve(MembershipPendingAccept.FILE),original);
            try(var owner=f.open(t,"apply-native")) {
                var result=owner.applyCurrent(builder().configuration(),t.materialization());
                assertEquals(1L,object(result.plan().catalog.value().get("cut")).get("index"));
                assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
                assertEquals(vote.certificate().digest(),owner.currentCertificate().orElseThrow().digest());
                assertThrows(IllegalArgumentException.class,()->result.plan().complete(List.of(result.endorsement().acknowledgement()),Set.of(result.endorsement().owned())));
            }
        }finally{save(f);}
    }
    @Test void fenceDuringNativeCertificateOrApplicationRecoveryPreventsAck()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-native-application/fencing-"+UUID.randomUUID()));
        var f=certified(Files.createDirectory(temp.resolve("fence")),raw);var t=f.request.targets().getFirst();int n=0;
        f.snapshot("certified");
        try {
            for(String point:List.of("CERTIFICATE_ACTIVE_FORCED","CERTIFICATE_ACTIVE_PARENT_FORCED","NATIVE_CERTIFICATE_RETAINED","REPLAY_APPLICATION_FINISHED","APPLY_BEFORE_RETURN")) {
                Files.move(t.replicaDirectory(),temp.resolve("previous-"+n++));V53JournalApplicationTest.copy(raw.resolve("certified/node-1"),t.replicaDirectory());
                MembershipGrantJournal[] active={null};
                f.observer=(target,operation,event)->{if(event.equals(point) && active[0]!=null)active[0].observeCurrent(Map.of("counter",9L,"proposer","node-1","incarnation",t.identity().storageId().toString()));};
                try(var owner=f.open(t,"fence-"+point)) {
                    active[0]=owner;assertThrows(IllegalArgumentException.class,()->owner.applyCurrent(builder().configuration(),t.materialization()));
                }
                f.observer=(target,operation,event)->{};
                try(var owner=f.open(t,"recover-"+point)) {
                    assertEquals(1L,object(owner.applyCurrent(builder().configuration(),t.materialization()).plan().catalog.value().get("cut")).get("index"));
                    assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
                }
            }
        }finally{save(f);}
    }
}
