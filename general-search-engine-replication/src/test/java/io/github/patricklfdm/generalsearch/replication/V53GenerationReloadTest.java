package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53GenerationReloadTest {
    @TempDir Path temp;

    @Test void completeReadersCommitWithoutSpareSlotAndPreserveUnrelatedWork()throws Exception {
        var budget=new MembershipResources(64*MIB+6);var pressure=new ArrayList<MembershipResources.Lease>();
        var executor=Executors.newSingleThreadExecutor();
        try(var misc=budget.reserve(Unit.MISC,"current-authority",2*MIB);
            var a=budget.reserve(Unit.GENERATION,"a",10);var b=budget.reserve(Unit.GENERATION,"b",20);
            var image=budget.reserve(Unit.APPLICATION,"generation-b:image",64*MIB)) {
            for(int i=0;i<6;i++)pressure.add(budget.reserve(Unit.APPLICATION,"receiving-"+i,1));
            var original=budget.usage();
            try(var reload=budget.prepareGenerationReload(Set.of(misc,a,b,image))) {
                var nextMisc=reload.claim(Unit.MISC,"current-authority",2*MIB);
                var nextB=reload.claim(Unit.GENERATION,"b",20);var nextImage=reload.claim(Unit.APPLICATION,"generation-b:image",100);
                assertEquals(original,budget.usage());
                executor.submit(()->{
                    assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.GENERATION,"receiver",1));
                    assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.APPLICATION,"receiver",1));
                }).get(5,TimeUnit.SECONDS);
                assertThrows(IllegalArgumentException.class,()->nextImage.reserveApplicationMaximum());
                var nextA=reload.claim(Unit.GENERATION,"a",10);
                try(var control=budget.reserve(Unit.CONTROL,"in-flight",17)) {
                    reload.commit();misc.close();a.close();b.close();image.close();
                    assertEquals(106,budget.usage().staging());assertEquals(17,budget.usage().queued());
                    assertEquals(2,budget.usage().counts().get(Unit.GENERATION));
                    List.of(nextMisc,nextA,nextB,nextImage).forEach(MembershipResources.Lease::close);
                    assertEquals(6,budget.usage().staging());assertEquals(17,budget.usage().queued());
                }
            }
        }finally{pressure.forEach(MembershipResources.Lease::close);executor.shutdownNow();}
        assertEquals(0,budget.usage().leases());
    }
    @Test void partialReaderCloseAbortsWholeHandoffWithoutReleasingOriginals() {
        var budget=new MembershipResources(512*MIB);
        try(var misc=budget.reserve(Unit.MISC,"current-authority",2*MIB);var a=budget.reserve(Unit.GENERATION,"a",10)) {
            var before=budget.usage();
            try(var reload=budget.prepareGenerationReload(Set.of(misc,a))) {
                var next=reload.claim(Unit.GENERATION,"a",10);assertThrows(IllegalArgumentException.class,reload::commit);
                assertThrows(IllegalArgumentException.class,()->reload.claim(Unit.GENERATION,"a",10));
                assertThrows(IllegalArgumentException.class,()->reload.claim(Unit.MISC,"current-authority",2*MIB+1));
                next.close();assertEquals(before,budget.usage());
                assertThrows(IllegalArgumentException.class,()->reload.claim(Unit.MISC,"current-authority",2*MIB));
                assertThrows(IllegalArgumentException.class,reload::commit);
            }
            assertEquals(before,budget.usage());a.reserveStorage(11);assertEquals(before.metadata()+1,budget.usage().metadata());
        }
        assertEquals(0,budget.usage().leases());
    }
    @Test void changedOrClosedOriginalCannotBeReplacedByPreparedReaders() {
        for(boolean close:List.of(false,true)) {
            var budget=new MembershipResources(512*MIB);
            try(var misc=budget.reserve(Unit.MISC,"current-authority",2*MIB);var a=budget.reserve(Unit.GENERATION,"a",10);
                var reload=budget.prepareGenerationReload(Set.of(misc,a))) {
                var nextMisc=reload.claim(Unit.MISC,"current-authority",2*MIB);var nextA=reload.claim(Unit.GENERATION,"a",10);
                if(close)a.close();else a.reserveStorage(11);
                var changed=budget.usage();assertThrows(IllegalArgumentException.class,reload::commit);
                nextMisc.close();nextA.close();assertEquals(changed,budget.usage());
            }
            assertEquals(0,budget.usage().leases());
        }
    }
    @Test void reloadRequiresEveryOriginalGenerationHandleAndNoForeignHandle() {
        var budget=new MembershipResources(512*MIB);var foreign=new MembershipResources(512*MIB);
        try(var misc=budget.reserve(Unit.MISC,"current-authority",2*MIB);var a=budget.reserve(Unit.GENERATION,"a",10);
            var other=foreign.reserve(Unit.GENERATION,"a",10);var source=budget.reserve(Unit.SOURCE,"source",10)) {
            var before=budget.usage();
            for(var members:List.of(Set.of(misc),Set.of(a),Set.of(misc,other),Set.of(misc,a,source)))
                assertThrows(IllegalArgumentException.class,()->budget.prepareGenerationReload(members));
            assertEquals(before,budget.usage());
        }
        assertEquals(0,budget.usage().leases());assertEquals(0,foreign.usage().leases());
    }
    @Test void nativeBarrierAndDataKeepBothGenerationsChargedThroughoutReaderValidation()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-generation-reload/publication-"+UUID.randomUUID()));
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);f.ownedHistory=true;f.nativeApplication=true;
        var rows=new ArrayList<Map<String,Object>>();var before=new HashMap<String,Usage>();
        try {
            f.campaign(1);
            f.observer=(target,operation,event)->{
                if(!operation.startsWith("publish-"))return;
                String key=target.identity().nodeId().value()+":"+operation;
                if(event.equals("INSTALL_PARENT_FORCED"))before.put(key,f.resources.usage());
                if(event.startsWith("CURRENT_") && before.containsKey(key)) {
                    rows.add(Map.of("owner",key,"event",event,"usage",V53PublicationReservationTest.usage(f.resources.usage())));
                    assertEquals(before.get(key),f.resources.usage());
                    assertEquals(2,f.resources.usage().counts().get(Unit.GENERATION));
                    assertThrows(IllegalArgumentException.class,()->f.resources.reserve(Unit.GENERATION,"competitor",1));
                }
            };
            f.publish(1,false);f.publish(2,true);assertEquals(30,rows.size());
        }finally {V53NativeApplicationTest.save(f);Files.write(raw.resolve("observations.json"),canonical(rows,65536));}
        assertEquals(0,f.resources.usage().leases());System.out.println("v53GenerationReloadEvidence="+raw.toAbsolutePath());
    }
    @Test void nativeReloadInterruptionPreservesBothOwnersUntilCloseAndRecoversOriginalFiles()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-generation-reload/refusal-"+UUID.randomUUID()));
        var f=V53NativeApplicationTest.certified(temp,raw);var acks=new ArrayList<Decoded>();var ends=new HashSet<MembershipContext.Owned>();
        var applied=new HashMap<String,MembershipGrantJournal.Applied>();
        for(var target:f.request.targets())try(var owner=f.open(target,"apply-original")) {
            var value=owner.applyCurrent(builder().configuration(),target.materialization());
            applied.put(target.identity().nodeId().value(),value);acks.add(value.endorsement().acknowledgement());ends.add(value.endorsement().owned());
        }
        var target=f.request.targets().getFirst();var before=new Usage[1];var original=new ArrayList<Map<String,String>>();
        var fired=new AtomicBoolean();
        try(var owner=f.open(target,"publish-interrupted")) {
            f.observer=(node,operation,event)->{
                if(event.equals("INSTALL_PARENT_FORCED")){before[0]=f.resources.usage();original.add(V53ReplayFilesTest.files(target.replicaDirectory()));}
                if(event.equals("CURRENT_FILES_FORCED")){fired.set(true);throw new IOException("reader reload interrupted");}
            };
            assertEquals("reader reload interrupted",assertThrows(IOException.class,
                ()->owner.publishCurrent(applied.get(target.identity().nodeId().value()),acks,ends,List.of())).getMessage());
            assertTrue(fired.get());assertEquals(before[0],f.resources.usage());
            assertEquals(original.getFirst(),V53ReplayFilesTest.files(target.replicaDirectory()));
            Files.write(raw.resolve("interrupted.json"),canonical(V53PublicationReservationTest.usage(f.resources.usage()),65536));
        }finally {f.observer=(node,operation,event)->{};V53NativeApplicationTest.save(f);}
        assertEquals(0,f.resources.usage().leases());
        try(var owner=f.open(target,"recover-original")) {
            owner.publishCurrent(applied.get(target.identity().nodeId().value()),acks,ends,List.of());
            assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
        }
        assertEquals(0,f.resources.usage().leases());System.out.println("v53GenerationReloadEvidence="+raw.toAbsolutePath());
    }
}
