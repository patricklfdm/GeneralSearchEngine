package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual old DATA votes, native recovery and the next fresh barrier stay together. */
class V53CarriedDataDriverTest {
    @TempDir Path temp;
    private void run(String phase)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        var slots=new V53CarriedSlotDriverTest();slots.temp=temp;
        try(var n=helper.new Network(3,ReplicationBounds.defaults(),f->V53CarriedSlotDriverTest.prepare(f,phase,true))) {
            byte[] original=Files.readAllBytes(n.f.raw.resolve("entry-1.gsr"));
            byte[] payload=Files.readAllBytes(n.f.raw.resolve("payload-1.bin"));
            assertEquals("DATA",decode(original,"records","ENTRY").value().get("kind"));
            long started=System.nanoTime();n.activate();slots.complete(n,started);
            assertArrayEquals(original,Files.readAllBytes(n.f.raw.resolve("entry-1.gsr")));
            assertArrayEquals(payload,Files.readAllBytes(n.f.raw.resolve("payload-1.bin")));
            for(int index:n.voters) {
                var target=n.f.request.targets().get(index);var owner=n.owners.get(index);
                var copy=owner.floorCopyCurrent();var context=copy.capsule.context;
                assertEquals(2L,context.cut.get("index"));assertEquals(1L,context.catalog.get("applicationSequence"));
                assertEquals(1L,context.catalog.get("lastDataIndex"));
                var image=MembershipApplicationImage.read(builder().configuration(),target.materialization(),
                        copy.fileBytes(copy.capsule.terminal().application()+".image"),temp.resolve("inspect-data-"+index));
                assertEquals(List.of(new Doc(303,"admitted-original")),image.documents());
            }
            assertEquals(0L,n.owners.get(2).activationContext().catalog.get("applicationSequence"));
        }
    }
    @Test void acceptedDataReplaysOnceBeforeFreshBarrier()throws Exception {run("ACCEPT");}
    @Test void provenDataReplaysOnceBeforeFreshBarrier()throws Exception {run("PROOF");}
    @Test void certifiedDataReplaysOnceBeforeFreshBarrier()throws Exception {run("CERTIFICATE");}
    @Test void appliedDataReplaysOnceBeforeFreshBarrier()throws Exception {run("APPLIED");}
}
