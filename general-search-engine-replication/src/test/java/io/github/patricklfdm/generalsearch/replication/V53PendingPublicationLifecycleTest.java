package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53PendingPublicationLifecycleTest {
    @TempDir Path temp;
    @Test void dataTargetIdentifiesTheNewTypedImageWhilePublishedStateRemainsOld()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-pending-publication/data-"+UUID.randomUUID()));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("data")),raw,3,true);
        f.ownedHistory=true;f.nativeApplication=true;
        try {
            f.campaign(1);f.publish(1,false);
            f.observer=(target,operation,event)->{if(operation.equals("apply-2"))throw new V53NativeApplicationTest.Stop();};
            assertThrows(V53NativeApplicationTest.Stop.class,()->f.publish(2,true));f.observer=(target,operation,event)->{};f.observations.clear();
            f.snapshot("certified-data");var t=f.request.targets().getFirst();
            try(var owner=f.open(t,"pending-data")) {
                var applied=owner.applyCurrent(builder().configuration(),t.materialization());var pending=owner.pendingPublication(applied);
                assertEquals(2L,pending.target().cut().get("index"));assertEquals(1L,pending.parent().cut().get("index"));
                assertNotEquals(pending.parent().application(),pending.target().application());
                assertEquals(hash(applied.plan().application.image()),pending.target().application());
                var state=MembershipApplicationImage.read(builder().configuration(),t.materialization(),applied.plan().application.image(),raw.resolve("typed-target"));
                assertTrue(state.documents().contains(new Doc(303,"admitted-original")));
                assertEquals(f.result.applicationSequence()+1,state.sequence());
                V53PendingPublicationTest.save(pending,raw.resolve("node-1-target"));
                assertEquals(pending.parent(),owner.floorCopyCurrent().capsule.terminal());
            }
            f.snapshot("applied-data");
        }finally{V53NativeApplicationTest.save(f);}
    }
    @Test void realPublicationRevokesPendingHandleOnlyAfterCompleteCheckpointQuorum()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-pending-publication/published-"+UUID.randomUUID()));
        var f=V53PendingPublicationTest.certified(Files.createDirectory(temp.resolve("published")),raw,3,false);
        try {
            var acknowledgements=new ArrayList<Decoded>();var owned=new HashSet<MembershipContext.Owned>();
            for(var t:f.request.targets())try(var owner=f.open(t,"apply-for-publication")) {
                var applied=owner.applyCurrent(builder().configuration(),t.materialization());
                acknowledgements.add(applied.endorsement().acknowledgement());owned.add(applied.endorsement().owned());
            }
            var t=f.request.targets().getFirst();
            try(var owner=f.open(t,"publish-real-target")) {
                var applied=owner.applyCurrent(builder().configuration(),t.materialization());var pending=owner.pendingPublication(applied);
                var target=pending.target();
                assertThrows(IllegalArgumentException.class,()->owner.publishCurrent(applied,List.of(acknowledgements.getFirst()),owned,List.of()));
                assertEquals(target,pending.target());
                owner.publishCurrent(applied,acknowledgements,owned,List.of());
                assertEquals(target,owner.floorCopyCurrent().capsule.terminal());
                assertThrows(IllegalArgumentException.class,pending::target);
                assertThrows(IllegalArgumentException.class,()->owner.pendingPublication(applied));
            }
            f.snapshot("published-target");
        }finally{V53NativeApplicationTest.save(f);}
    }
}
