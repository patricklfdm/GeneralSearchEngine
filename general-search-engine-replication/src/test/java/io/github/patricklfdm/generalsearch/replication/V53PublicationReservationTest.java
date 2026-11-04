package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Real native owners and original votes; calls are explicitly orchestrated,
 * not a TCP or whole-transition simultaneous-peak qualification. */
class V53PublicationReservationTest {
    @TempDir Path temp;

    static void unchangedImageReservation(Usage before,Usage after) {
        assertEquals(before.staging(),after.staging(),"candidate must inherit the complete reserved image without release/reacquire");
        assertEquals(before.counts().get(Unit.APPLICATION),after.counts().get(Unit.APPLICATION));
    }
    @Test void fullImageCountAndWaitingReceiverCannotStealTransferredCompletion()throws Exception {
        var budget=new MembershipResources(HEADROOM+10,64*MIB+6,100);
        var pressure=new ArrayList<MembershipResources.Lease>();var pool=Executors.newSingleThreadExecutor();
        try(var completion=budget.reserve(Unit.APPLICATION,"publication-completion",64*MIB)) {
            for(int i=0;i<6;i++)pressure.add(budget.reserve(Unit.APPLICATION,"original-"+i,1));
            var before=budget.usage();var ready=new CountDownLatch(1);Future<?> competitor;
            var image=new StorageReservation(Unit.APPLICATION,"generation-b:image",100);
            List<MembershipResources.Lease> acquired;
            synchronized(budget) {
                competitor=pool.submit(()->{ready.countDown();assertEquals("resource ownership/count",
                    assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.APPLICATION,"receiver",1)).getMessage());});
                assertTrue(ready.await(5,TimeUnit.SECONDS));
                acquired=budget.extendGeneration(Map.of(),List.of(new StorageReservation(Unit.GENERATION,"b",10),image),completion,image);
                unchangedImageReservation(before,budget.usage());
            }
            competitor.get(5,TimeUnit.SECONDS);completion.close();
            unchangedImageReservation(before,budget.usage());
            assertThrows(IllegalArgumentException.class,()->completion.reserveApplicationMaximum());
            acquired.forEach(MembershipResources.Lease::close);
            assertEquals(6,budget.usage().staging());assertEquals(0,budget.usage().metadata());
        }finally {pressure.forEach(MembershipResources.Lease::close);pool.shutdownNow();}
        assertEquals(0,budget.usage().leases());
    }
    @Test void failedHandoffRestoresGrowthAndPreservesOriginalCompletion() {
        var budget=new MembershipResources(HEADROOM+50,64*MIB,100);
        try(var completion=budget.reserve(Unit.APPLICATION,"publication-completion",64*MIB);
            var metadata=budget.reserve(Unit.GENERATION,"a",10)) {
            var before=budget.usage();var image=new StorageReservation(Unit.APPLICATION,"generation-b:image",100);
            for(var excess:List.of(new StorageReservation(Unit.GENERATION,"b",31),new StorageReservation(Unit.APPLICATION,"excess",1),
                    new StorageReservation(Unit.APPLICATION,"generation-b:image",101))) {
                assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(metadata,20L),List.of(image,excess),completion,image));
                assertEquals(before,budget.usage());completion.reserveApplicationMaximum();
            }
            // A target-name collision must not consume the old maximum or leave
            // any of the newly acquired metadata handles behind.
            var acquired=budget.extendGeneration(Map.of(metadata,20L),List.of(image),completion,image);
            assertEquals(64*MIB,budget.usage().staging());acquired.forEach(MembershipResources.Lease::close);
            assertEquals(20,budget.usage().metadata());
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void otherCandidateImagesStillRequireIndependentAdmission() {
        var budget=new MembershipResources(64*MIB+20);
        try(var completion=budget.reserve(Unit.APPLICATION,"publication-completion",64*MIB)) {
            var image=new StorageReservation(Unit.APPLICATION,"generation-b:first",10);
            var extra=new StorageReservation(Unit.APPLICATION,"generation-b:second",20);
            var before=budget.usage();
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(),
                List.of(image,extra,new StorageReservation(Unit.APPLICATION,"generation-b:third",1)),completion,image));
            assertEquals(before,budget.usage());
            var acquired=budget.extendGeneration(Map.of(),List.of(new StorageReservation(Unit.GENERATION,"b",10),image,extra),completion,image);
            assertEquals(64*MIB+20,budget.usage().staging());assertEquals(2,budget.usage().counts().get(Unit.APPLICATION));
            completion.close();assertEquals(64*MIB+20,budget.usage().staging());
            acquired.forEach(MembershipResources.Lease::close);
        }
        assertEquals(0,budget.usage().leases());
        // Leave enough bytes for a differently sized duplicate target to be
        // admitted first. The final handoff must reject that collision and
        // restore the original group, rather than merely failing capacity.
        var collision=new MembershipResources(64*MIB+200);
        try(var completion=collision.reserve(Unit.APPLICATION,"publication-completion",64*MIB)) {
            var image=new StorageReservation(Unit.APPLICATION,"generation-b:image",100);
            var before=collision.usage();
            assertEquals("generation completion target occupied",assertThrows(IllegalArgumentException.class,
                ()->collision.extendGeneration(Map.of(),List.of(new StorageReservation(Unit.GENERATION,"b",10),image,
                    new StorageReservation(Unit.APPLICATION,image.owner(),101)),completion,image)).getMessage());
            assertEquals(before,collision.usage());completion.reserveApplicationMaximum();
        }
        assertEquals(0,collision.usage().leases());
    }
    @Test void completionHandoffRejectsForeignClosedUndersizedAndWrongTargets() {
        var budget=new MembershipResources(512*MIB);var foreign=new MembershipResources(512*MIB);
        try(var completion=budget.reserve(Unit.APPLICATION,"publication-completion",64*MIB);
            var small=budget.reserve(Unit.APPLICATION,"small",1);
            var other=foreign.reserve(Unit.APPLICATION,"other",64*MIB)) {
            var before=budget.usage();var image=new StorageReservation(Unit.APPLICATION,"generation-b:image",100);
            for(var invalid:List.of(small,other)) {
                assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(),List.of(image),invalid,image));
                assertEquals(before,budget.usage());
            }
            var closed=budget.reserve(Unit.APPLICATION,"closed",64*MIB);closed.close();
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(),List.of(image),closed,image));
            for(var invalid:List.of(new StorageReservation(Unit.SOURCE,"wrong",1),new StorageReservation(Unit.APPLICATION,"small",1),
                    new StorageReservation(Unit.APPLICATION,"publication-completion",1),new StorageReservation(Unit.APPLICATION,"",1))) {
                assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(),List.of(invalid),completion,invalid));
                assertEquals(before,budget.usage());
            }
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(completion,64*MIB),List.of(image),completion,image));
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(),List.of(image,image),completion,image));
            assertThrows(IllegalArgumentException.class,()->budget.extendGeneration(Map.of(),List.of(),completion,image));
            assertEquals(before,budget.usage());
        }
        assertEquals(0,budget.usage().leases());assertEquals(0,foreign.usage().leases());
    }
    @Test void nativePublicationMetadataRefusalKeepsCompletionAndOriginalBytes()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-publication-reservation/refusal-"+UUID.randomUUID()));
        System.out.println("v53PublicationReservationEvidence="+raw.toAbsolutePath());
        var f=V53NativeApplicationTest.certified(temp,raw);var acks=new ArrayList<Decoded>();var ends=new HashSet<MembershipContext.Owned>();
        var applied=new HashMap<String,MembershipGrantJournal.Applied>();
        for(var target:f.request.targets())try(var owner=f.open(target,"apply-original")) {
            var value=owner.applyCurrent(builder().configuration(),target.materialization());
            applied.put(target.identity().nodeId().value(),value);acks.add(value.endorsement().acknowledgement());ends.add(value.endorsement().owned());
        }
        var target=f.request.targets().getFirst();long metadata;
        try(var owner=f.open(target,"count-original")){metadata=f.resources.usage().metadata();}
        var budget=new MembershipResources(metadata+2*MIB,512*MIB,QUEUE_LIMIT);
        var original=V53ReplayFilesTest.files(target.replicaDirectory());
        try(var owner=MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),
                f.result.root(),target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{})) {
            var before=budget.usage();
            assertEquals("completion headroom",assertThrows(IllegalArgumentException.class,
                ()->owner.publishCurrent(applied.get(target.identity().nodeId().value()),acks,ends,List.of())).getMessage());
            Files.write(raw.resolve("refusal.json"),canonical(Map.of("before",usage(before),"after",usage(budget.usage())),65536));
            assertEquals(before,budget.usage());assertEquals(original,V53ReplayFilesTest.files(target.replicaDirectory()));
        }finally {V53NativeApplicationTest.save(f);}
        assertEquals(0,budget.usage().leases());
        try(var owner=f.open(target,"resume-original")) {
            owner.publishCurrent(applied.get(target.identity().nodeId().value()),acks,ends,List.of());
            assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
        }
        f.snapshot("completed-after-refusal");assertEquals(0,f.resources.usage().leases());
    }
    @Test void nativeBarrierAndDataKeepCompletionImageThroughCandidateReservation()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-publication-reservation/publication-"+UUID.randomUUID()));
        System.out.println("v53PublicationReservationEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);f.ownedHistory=true;f.nativeApplication=true;
        var rows=new ArrayList<Map<String,Object>>();var before=new HashMap<String,Usage>();var reserved=new HashSet<String>();
        try {
            f.campaign(1);
            f.observer=(target,operation,event)->{
                if(!operation.startsWith("publish-"))return;
                String key=target.identity().nodeId().value()+":"+operation;
                if(event.equals("PUBLICATION_VALIDATED") && !reserved.contains(key))before.put(key,f.resources.usage());
                if(event.equals("INSTALL_RESERVED")) {
                    rows.add(Map.of("owner",key,"before",usage(before.get(key)),"after",V53CombinedReceiveResourcesTest.usage(f.resources)));
                    unchangedImageReservation(before.get(key),f.resources.usage());assertTrue(reserved.add(key));
                }
            };
            f.publish(1,false);f.publish(2,true);assertEquals(6,reserved.size());
        }finally {
            V53NativeApplicationTest.save(f);Files.write(raw.resolve("reservations.json"),canonical(rows,65536));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void carriedNativeCertificateInstallationInheritsTheReservedImage()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-publication-reservation/carried-"+UUID.randomUUID()));
        System.out.println("v53PublicationReservationEvidence="+raw.toAbsolutePath());
        var f=V53NativeApplicationTest.certified(temp,raw);var rows=new ArrayList<Map<String,Object>>();
        try {
            var selected=V53DistinctMinorityTest.campaign(f,3,f.request.targets(),false);
            for(var target:f.request.targets())try(var owner=f.open(target,"carried-install")) {
                var before=f.resources.usage();var seen=new boolean[1];
                f.observer=(node,operation,event)->{
                    if(event.equals("INSTALL_RESERVED")) {
                        rows.add(Map.of("owner",target.identity().nodeId().value(),"before",usage(before),"after",V53CombinedReceiveResourcesTest.usage(f.resources)));
                        unchangedImageReservation(before,f.resources.usage());seen[0]=true;
                    }
                };
                var installed=owner.installCurrent(selected.sources(),List.of(),selected.images());
                assertTrue(seen[0]);assertArrayEquals(installed.bytes(),owner.installCurrent(selected.sources(),List.of(),selected.images()).bytes());
                assertTrue(owner.currentCertificate().isPresent());
                f.observer=(node,operation,event)->{};
            }
            f.snapshot("reserved-carried-install");
        }finally {
            V53NativeApplicationTest.save(f);Files.write(raw.resolve("reservations.json"),canonical(rows,65536));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    static Map<String,Object> usage(Usage value) {
        var counts=new TreeMap<String,Object>();value.counts().forEach((unit,count)->counts.put(unit.name(),count));
        return Map.of("metadata",value.metadata(),"staging",value.staging(),"queued",value.queued(),"leases",value.leases(),"counts",counts);
    }
}
