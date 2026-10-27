package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53FutureRetentionSourceTest {
    @TempDir Path temp;
    static V53BootstrapPublicationTest.Fixture pending(Path home,Path raw)throws Exception {
        var f=V53FutureRetentionTest.ready(home,raw);var t=f.request.targets().getFirst();
        try(var owner=f.open(t,"record-future")) {
            owner.retainFutureDispatch(f.request.targets().get(1).identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),t.materialization())));
        }
        f.snapshot("pending-future");return f;
    }
    @Test void newGrantPreservesExactFutureProofAndRefusesIncompleteSelectionBeforeWriting()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-source/native-"+UUID.randomUUID()));
        var f=pending(Files.createDirectory(temp.resolve("native")),raw);var self=f.request.targets().getFirst();
        var ballot=Map.<String,Object>of("counter",3L,"proposer","node-1","incarnation",self.identity().storageId().toString());
        byte[] active=Files.readAllBytes(self.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE));
        try {
            var sources=new ArrayList<MembershipSelection.Source>();byte[] packet;String basis;
            try(var owner=f.open(self,"future-source")) {
                owner.prepareCurrent(ballot);var source=owner.originalSource();var frozen=MembershipPeerRetentionSource.read(source);
                assertArrayEquals(active,frozen.futureBytes());assertEquals(1,frozen.future().revision);
                assertEquals(source.accepted.digest(),frozen.future().record("accept.gsr").digest());
                assertEquals(2L,object(frozen.future().record("promise.gsr").value().get("ballot")).get("counter"));
                assertEquals(3L,object(frozen.promise().value().get("ballot")).get("counter"));
                assertTrue(source.capsule.packet.objectNames().contains(hash(active)));
                assertEquals(0L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
                packet=source.capsule.packet.bytes();basis=source.basis.digest();sources.add(source);
                byte[] copy=frozen.futureBytes();copy[0]^=1;assertArrayEquals(active,frozen.futureBytes());
                var inventory=V53ReplayFilesTest.files(self.replicaDirectory());
                assertEquals(basis,owner.prepareCurrent(ballot).digest());assertEquals(inventory,V53ReplayFilesTest.files(self.replicaDirectory()));
            }
            f.snapshot("captured-future");
            for(var t:f.request.targets().subList(1,3))try(var owner=f.open(t,"other-source")) {
                owner.prepareCurrent(ballot);sources.add(owner.originalSource());assertNull(MembershipPeerRetentionSource.read(owner.originalSource()).future());
            }
            // Legacy owners without the imported-proof transaction still reject.
            // Native installation/continuation is exercised in its dedicated gate.
            for(var t:f.request.targets().subList(0,2))try(var owner=f.open(t,"selection-guard")) {
                var before=V53ReplayFilesTest.files(t.replicaDirectory());
                assertEquals("selected future retention propagation required",assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.requireSelectable(sources.getFirst())).getMessage());
                assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));
            }
            try(var owner=f.open(self,"original-source-reopen")) {
                assertEquals(basis,owner.originalSource().basis.digest());assertArrayEquals(packet,owner.originalSource().capsule.packet.bytes());
                assertArrayEquals(active,MembershipPeerRetentionSource.read(owner.originalSource()).futureBytes());
                assertTrue(owner.futureRetentionState().pending());
            }
            f.snapshot("reopened-future");
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
    /** Synthetic BASIS ownership is used only to test malformed included objects,
     * never as a real election or future-target receipt. */
    static MembershipSelection.Source conditional(MembershipSelection.Source original,MembershipSourcePacket packet,Map<String,byte[]> images) {
        var cap=original.capsule.materialization(packet,images,List.of());var fields=new TreeMap<>(original.basis.value());
        fields.put("capsule",packet.capsule().digest());fields.put("inventory",packet.inventoryDigest());var basis=decode(encode("records","BASIS",fields),"records","BASIS");
        var owned=new HashSet<MembershipContext.Owned>();String parent=MembershipContext.cutDigest(cap.context.cut);
        owned.add(new MembershipContext.Owned(original.owner.nodeId().value(),original.owner.storageId(),basis.digest(),parent));
        owned.add(new MembershipContext.Owned(original.owner.nodeId().value(),original.owner.storageId(),original.accepted.digest(),parent));
        return MembershipSelection.Source.verify(cap,basis,Map.of("voter",original.owner.nodeId().value(),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest()),original.owner,owned);
    }
    @Test void missingConflictingAndForeignProofsDoNotBecomeSourceObligations()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-source/guards-"+UUID.randomUUID()));
        var f=pending(Files.createDirectory(temp.resolve("guards")),raw);var self=f.request.targets().getFirst();
        try(var owner=f.open(self,"source-guards")) {
            owner.prepareCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",self.identity().storageId().toString()));
            var source=owner.originalSource();var frozen=MembershipPeerRetentionSource.read(source);var packet=source.capsule.packet;
            var images=new TreeMap<String,byte[]>();for(String h:packet.images().keySet())images.put(h,Files.readAllBytes(self.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
            var objects=new TreeMap<String,byte[]>();for(String h:packet.objectNames())objects.put(h,packet.objectBytes(h));
            objects.remove(hash(frozen.futureBytes()));
            assertEquals("retention source future proof missing",assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.read(conditional(source,V53PeerRetentionSourceTest.objects(packet,objects),images))).getMessage());
            assertEquals("selected future retention propagation required",assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.included(packet.envelope(),source.basis,self.identity(),MembershipPeerRetentionSource.wrapper(frozen))).getMessage());
            var duplicate=MembershipPeerRetentionSource.freeze(packet,frozen.promise(),self.identity(),frozen.localBytes());
            assertEquals("retention source duplicate original state",assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.read(conditional(source,duplicate,images))).getMessage());
            var foreign=f.request.targets().get(1);byte[] peerLedger=Files.readAllBytes(foreign.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
            assertEquals("future retention foreign owner",assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.freeze(packet,frozen.promise(),foreign.identity(),peerLedger,frozen.futureBytes())).getMessage());
            byte[] changed=frozen.futureBytes();changed[changed.length-1]^=1;
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.freeze(packet,frozen.promise(),self.identity(),frozen.localBytes(),changed));
            assertEquals(1,owner.futureRetentionState().revision);
        }finally{V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
    }
}
