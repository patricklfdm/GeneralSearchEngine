package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53PeerRetentionSourceTest {
    @TempDir Path temp;
    private Path evidence;
    V53BootstrapPublicationTest.Fixture fixture(String name)throws Exception {
        if(evidence==null){evidence=Files.createDirectories(Path.of("target/v53-peer-retention-source/run-"+UUID.randomUUID()));System.out.println("v53PeerRetentionSourceEvidence="+evidence.toAbsolutePath());}
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),Files.createDirectory(evidence.resolve(name)),3,false);
        f.ownedHistory=true;
        for(var target:f.request.targets())try(var owner=f.open(target,"initialize")){owner.initializePeerRetention();}
        return f;
    }
    @Test void originalGrantIsImmutableAcrossUpdatesReopeningAndFreshElections()throws Exception {
        var f=fixture("immutable");var self=f.request.targets().getFirst();
        f.campaign(1);byte[] original;String basis;
        try(var owner=f.open(self,"update-after-capture")) {
            var source=owner.originalSource();original=source.capsule.packet.bytes();basis=source.basis.digest();
            var frozen=MembershipPeerRetentionSource.read(source);assertEquals(0,frozen.state().revision());
            assertEquals(1,owner.reconcilePeerRetention(List.of()).revision());
            assertEquals(basis,owner.prepareCurrent(f.ballot).digest());
            assertArrayEquals(original,owner.originalSource().capsule.packet.bytes());
            assertEquals(0,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());
            byte[] returned=frozen.localBytes();returned[0]^=1;
            assertNotEquals(returned[0],frozen.localBytes()[0]);
        }
        try(var owner=f.open(self,"reopen-original")) {
            assertEquals(1,owner.peerRetentionState().revision());assertEquals(basis,owner.originalSource().basis.digest());
            assertArrayEquals(original,owner.originalSource().capsule.packet.bytes());
            assertEquals(0,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());
        }
        f.campaign(2);
        try(var owner=f.open(self,"fresh-source")){assertEquals(1,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());}
        f.publish(1,false);
        try(var owner=f.open(self,"compacted")) {
            // Certified application compaction prunes obsolete capture metadata;
            // the immutable retained BASIS and native active ledger survive.
            var packet=owner.floorCopyCurrent().capsule.packet;
            assertTrue(packet.objectNames().stream().noneMatch(h->isRetention(packet.objectBytes(h))));
            assertEquals(1,owner.peerRetentionState().revision());
            assertEquals(1,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());
        }
        Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","events",f.calls),4*1024*1024));
        assertEquals(0,f.resources.usage().leases());
    }
    static boolean isRetention(byte[] bytes){return bytes.length>=4 && java.nio.ByteBuffer.wrap(bytes).getInt()==MembershipPeerRetentionSource.MAGIC;}
    /** Conditional malformed-source fixture only. Synthetic BASIS ownership here
     * is never used as evidence of a real remote grant or new voting authority. */
    static MembershipSelection.Source conditional(MembershipSelection.Source original,MembershipSourcePacket packet,Map<String,byte[]> images) {
        var cap=original.capsule.materialization(packet,images,List.of());
        var fields=new TreeMap<>(original.basis.value());fields.put("capsule",packet.capsule().digest());fields.put("inventory",packet.inventoryDigest());
        var basis=decode(encode("records","BASIS",fields),"records","BASIS");
        var owned=new MembershipContext.Owned(original.owner.nodeId().value(),original.owner.storageId(),basis.digest(),MembershipContext.cutDigest(cap.context.cut));
        return MembershipSelection.Source.verify(cap,basis,Map.of("voter",original.owner.nodeId().value(),"basisId",basis.value().get("basisId"),"basisDigest",basis.digest()),original.owner,Set.of(owned));
    }
    static MembershipSourcePacket objects(MembershipSourcePacket original,Map<String,byte[]> objects) {
        var cap=new TreeMap<>(original.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,original.images()));
    }
    @Test void conditionalMalformedOriginalsCannotSubstituteForTheCapture()throws Exception {
        var f=fixture("malformed");var self=f.request.targets().getFirst();
        try(var owner=f.open(self,"malformed-source")) {
            var source=owner.beginActivation();var packet=source.capsule.packet;var images=new TreeMap<String,byte[]>();
            for(String h:packet.images().keySet())images.put(h,Files.readAllBytes(self.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
            var members=new TreeMap<String,byte[]>();for(String h:packet.objectNames())members.put(h,packet.objectBytes(h));
            String capture=members.keySet().stream().filter(h->isRetention(members.get(h))).findFirst().orElseThrow();
            members.remove(capture);var missing=conditional(source,objects(packet,members),images);
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.read(missing));
            byte[] opaque=java.nio.ByteBuffer.allocate(16).putInt(MembershipPeerRetentionSource.MAGIC).array();members.put(hash(opaque),opaque);
            members.put(capture,packet.objectBytes(capture));
            assertEquals(0,MembershipPeerRetentionSource.read(conditional(source,objects(packet,members),images)).state().revision());
            owner.reconcilePeerRetention(List.of());
            byte[] later=Files.readAllBytes(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
            var duplicate=conditional(source,MembershipPeerRetentionSource.freeze(packet,owner.promised().orElseThrow(),self.identity(),later),images);
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.read(duplicate));
            var fields=new TreeMap<>(owner.promised().orElseThrow().value());fields.put("basisId",UUID.randomUUID().toString());
            var other=decode(encode("records","PROMISE",fields),"records","PROMISE");members.remove(capture);members.remove(hash(opaque));
            var wrong=conditional(source,MembershipPeerRetentionSource.freeze(objects(packet,members),other,self.identity(),later),images);
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.read(wrong));
            var foreign=f.request.targets().get(1);
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionSource.freeze(packet,other,foreign.identity(),later));
            byte[] damaged=packet.bytes();damaged[damaged.length-1]^=1;
            assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(damaged));
        }
    }
    @Test void incompletePromiseCannotFreezeAnUpdatedLocalLedger()throws Exception {
        var f=fixture("incomplete-promise");var self=f.request.targets().getFirst();
        var ballot=Map.<String,Object>of("counter",2L,"proposer",self.identity().nodeId().value(),"incarnation",self.identity().storageId().toString());
        f.observer=(t,operation,event)->{if(operation.equals("interrupt") && event.equals("PROMISE_FORCED"))throw new java.io.IOException("cut before capture");};
        try(var owner=f.open(self,"interrupt")){assertThrows(java.io.IOException.class,()->owner.prepareCurrent(ballot));}
        try(var owner=f.open(self,"incomplete")) {
            assertTrue(owner.originalBasis().isEmpty());
            var before=V53ReplayFilesTest.files(self.replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->owner.reconcilePeerRetention(List.of()));
            assertEquals(before,V53ReplayFilesTest.files(self.replicaDirectory()));
            var next=new TreeMap<>(ballot);next.put("counter",3L);owner.prepareCurrent(next);
            assertEquals(0,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());
        }
    }
    @Test void protectedContextKeepsItsOriginalEnvelopeThroughInterruptedRecapture()throws Exception {
        var walk=new V53CoveredContextTest();walk.temp=temp;walk.ownedHistory=true;walk.retainingPeers=true;walk.precedingSlots=2;
        var original=walk.original(3,false,"CERTIFICATE");var f=original.f();var self=f.request.targets().getFirst();
        byte[] before=Files.readAllBytes(self.replicaDirectory().resolve(MembershipPendingContextFiles.FILE));
        f.observer=(t,operation,event)->{if(operation.equals("context-recapture") && event.equals("SOURCE_PACKET_PREFIX_WRITTEN"))throw new java.io.IOException("cut context capture");};
        var ballot=Map.<String,Object>of("counter",4L,"proposer",self.identity().nodeId().value(),"incarnation",self.identity().storageId().toString());
        try(var owner=f.open(self,"context-recapture")){assertThrows(java.io.IOException.class,()->owner.prepareCurrent(ballot));}
        try(var owner=f.open(self,"context-recover")) {
            assertEquals(0,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());
            assertEquals(4L,object(owner.originalSource().basis.value().get("ballot")).get("counter"));
            assertNotNull(owner.retainPendingContext());assertEquals(owner.originalBasis().orElseThrow().digest(),owner.prepareCurrent(ballot).digest());
        }
        assertFalse(Arrays.equals(before,Files.readAllBytes(self.replicaDirectory().resolve(MembershipPendingContextFiles.FILE))));
        try(var owner=f.open(self,"context-reopened")){assertEquals(0,MembershipPeerRetentionSource.read(owner.originalSource()).state().revision());assertNotNull(owner.retainPendingContext());}
        assertEquals(0,f.resources.usage().leases());V53CoveredPhasedVoteTest.save(f);
    }
    @Test void freshProcessesRecoverTheExactFrozenSnapshotAtCaptureBoundaries()throws Exception {
        for(String mode:List.of("halt","kill"))for(String point:List.of("CAPTURE_INTENT_PREFIX_WRITTEN","CAPTURE_INTENT_FORCED",
                "SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_PACKET_FORCED","BASIS_WRITTEN","BASIS_FORCED","GRANT_BEFORE_RETURN")) {
            var f=fixture(mode+"-"+point);var self=f.request.targets().getFirst();
            Files.copy(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE),f.raw.resolve("frozen.gspr"));
            Path log=f.raw.resolve("worker.log");
            var child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                    V53PeerRetentionSourceWorker.class.getName(),self.replicaDirectory().toString(),self.materialization().directory().toString(),mode,point)
                    .redirectErrorStream(true).redirectOutput(log.toFile()).start();
            try {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
                while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));
                assertFalse(Files.readString(log).contains("RESPONSE"));
                if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(self,"live-lock-probe"));child.destroyForcibly();}
                assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                V53JournalApplicationTest.copy(self.replicaDirectory(),f.raw.resolve("interrupted"));
                try(var owner=f.open(self,"recover")) {
                    var source=owner.originalSource();var frozen=MembershipPeerRetentionSource.read(source);
                    assertArrayEquals(Files.readAllBytes(f.raw.resolve("frozen.gspr")),frozen.localBytes());
                    assertEquals(0,frozen.state().revision());
                    Files.write(f.raw.resolve("promise.gsr"),owner.promised().orElseThrow().bytes());
                    Files.write(f.raw.resolve("basis.gsr"),source.basis.bytes());Files.write(f.raw.resolve("source.gscp"),source.capsule.packet.bytes());
                    assertEquals(source.basis.digest(),owner.prepareCurrent(object(source.basis.value().get("ballot"))).digest());
                    V53JournalApplicationTest.copy(self.replicaDirectory(),f.raw.resolve("recovered"));
                    assertEquals(1,owner.reconcilePeerRetention(List.of()).revision());
                    assertArrayEquals(frozen.localBytes(),MembershipPeerRetentionSource.read(owner.originalSource()).localBytes());
                    V53JournalApplicationTest.copy(self.replicaDirectory(),f.raw.resolve("updated"));
                }
                Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","mode",mode,"cut",point,"exit",(long)child.exitValue(),"events",f.calls),1024*1024));
                assertEquals(0,f.resources.usage().leases());System.out.println("v53PeerRetentionSourceCrash="+mode+":"+point+" PASS");
            }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
        }
    }
}
