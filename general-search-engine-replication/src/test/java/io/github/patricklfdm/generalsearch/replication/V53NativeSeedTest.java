package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.durability.DurableApplicationState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Small TCP seed integration; neither maximum-image nor complete joining qualification. */
class V53NativeSeedTest {
    @TempDir Path temp;
    static final long SEQUENCE=731;
    static final List<Doc> DOCUMENTS=List.of(new Doc(7,"imported"),new Doc(2,"你好"),new Doc(53,"seed-".repeat(173)));

    MembershipBootstrapRequest<Integer,Doc> request(int size,boolean backup)throws Exception {
        Path source=null;
        if(backup) {
            source=temp.resolve("backup-"+UUID.randomUUID());
            var state=new DurableApplicationState<>(V53BootstrapSeedTest.IMPORTED,SEQUENCE,DOCUMENTS,builder().configuration().indexes());
            MembershipApplicationImage.capture(builder().configuration(),storage(temp.resolve("source-"+UUID.randomUUID()),2),state,source);
        }
        var helper=new V53BootstrapSeedTest();
        return helper.request(temp.resolve("group-"+UUID.randomUUID()),size,source);
    }

    @Test void endpointRebindingPreservesExplicitAdmissionInputs()throws Exception {
        var original=request(5,true);var bound=V53OwnedCrossViewTest.networkRequest(original);
        assertEquals(original.groupId(),bound.groupId());assertEquals(original.configurationId(),bound.configurationId());
        assertEquals(original.source(),bound.source());assertEquals(original.sourcePath(),bound.sourcePath());
        assertEquals(original.operationDirectory(),bound.operationDirectory());
        assertEquals(original.maxSourceBytes(),bound.maxSourceBytes());assertEquals(original.maxOperationBytes(),bound.maxOperationBytes());
        var endpoints=new HashSet<ReplicationEndpoint>();
        for(int i=0;i<5;i++) {
            var before=original.targets().get(i);var after=bound.targets().get(i);
            assertEquals(before.identity().nodeId(),after.identity().nodeId());assertEquals(before.identity().storageId(),after.identity().storageId());
            assertEquals(before.replicaDirectory(),after.replicaDirectory());assertSame(before.materialization(),after.materialization());
            assertTrue(endpoints.add(after.identity().endpoint()));
        }
        V53BootstrapSeedTest.absent(original);
    }

    @Test void verifiedSeedSurvivesNativeBarrierAndReleasesResources()throws Exception {
        verifySeed(V53NativeResourceProfile.SMALL_FIXTURE,V53WireArchive.Layout.JSON);
    }
    @Test void defaultStagingSeedSurvivesNativeBarrierWithExplicitResourceTraces()throws Exception {
        String key="v53.resource.transitions",before=System.getProperty(key);
        try {
            System.setProperty(key,"true");
            verifySeed(V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING,V53WireArchive.Layout.SEGMENTED_BACKUP);
        }finally {if(before==null)System.clearProperty(key);else System.setProperty(key,before);}
    }
    private void verifySeed(V53NativeResourceProfile profile,V53WireArchive.Layout layout)throws Exception {
        var request=request(5,true);var original=V53ReplayFilesTest.files(request.sourcePath().orElseThrow());
        var helper=new V53NativeDispatchTest();helper.temp=temp;var driver=new V53RoundDriverTest();driver.temp=temp;
        var prepared=new AtomicBoolean();
        var n=helper.new Network(request,driver.controlBounds(),V53NativeDispatchTest.BUDGET,f->{
            assertEquals(SEQUENCE,f.result.applicationSequence());prepared.set(true);
        },true,false,layout,profile);
        try(n;var round=driver.driver(n,MembershipRoundDriver.Events.NONE)) {
            assertEquals(profile,n.f.resourceProfile);
            assertInstanceOf(V53EvidenceSpool.class,n.events);
            assertTrue(prepared.get());assertEquals(MembershipBootstrapSource.VERIFIED_DURABLE_BACKUP,n.f.request.source());
            assertNotEquals(V53BootstrapSeedTest.IMPORTED,n.f.result.root().historyId());
            assertEquals(SEQUENCE,n.f.result.applicationSequence());
            assertEquals("PUBLISH_ACK",round.start().kind());assertEquals(MembershipRoundDriver.State.READY,round.state());
            for(int i:n.voters) {
                var copy=n.owners.get(i).floorCopyCurrent();var target=n.f.request.targets().get(i);
                assertEquals(1L,copy.capsule.context.cut.get("index"));
                assertEquals(SEQUENCE,copy.capsule.context.catalog.get("applicationSequence"));
                byte[] image=copy.fileBytes(copy.capsule.terminal().application()+".image");
                assertArrayEquals(n.f.original.seed.application(),image);
                var state=MembershipApplicationImage.read(builder().configuration(),target.materialization(),image,temp.resolve("typed-"+i));
                assertEquals(n.f.result.root().historyId(),state.history());assertEquals(SEQUENCE,state.sequence());assertEquals(DOCUMENTS,state.documents());
            }
        }
        assertEquals(original,V53ReplayFilesTest.files(request.sourcePath().orElseThrow()));
        for(var resources:n.resources) {
            assertEquals(0,resources.usage().leases());
            if(profile==V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING)
                assertEquals(profile.stagingBytes,resources.observations().stagingLimit());
        }
        var result=new TreeMap<String,Object>(Map.of("status","PASS","source","VERIFIED_DURABLE_BACKUP",
                "size",5,"applicationSequence",SEQUENCE,"documents",DOCUMENTS.size(),"slots",1,"leasesAfterClose",0,
                "fullJoiningQualified",false,"maximumImageQualified",false));
        if(profile!=V53NativeResourceProfile.SMALL_FIXTURE) {
            result.put("resourceProfile",profile.name());result.put("stagingLimit",profile.stagingBytes);
        }
        Files.write(n.f.raw.resolve("seed-result.json"),canonical(result,4096));
    }

    @Test void defaultNetworkStillAdmitsEmptySource()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            assertFalse(n.events instanceof V53EvidenceSpool);
            assertEquals(MembershipBootstrapSource.EMPTY,n.f.request.source());assertTrue(n.f.request.sourcePath().isEmpty());
            assertEquals(0,n.f.result.applicationSequence());
            var target=n.f.request.targets().getFirst();
            var state=MembershipApplicationImage.read(builder().configuration(),target.materialization(),n.f.original.seed.application(),temp.resolve("empty"));
            assertTrue(state.documents().isEmpty());
        }
    }

    @Test void inadmissibleSeedFailsBeforePreparationOrNetworkActors()throws Exception {
        var original=request(5,true);var prepared=new AtomicBoolean();
        var limited=new MembershipBootstrapRequest<>(original.groupId(),original.configurationId(),original.source(),original.sourcePath(),
                original.targets(),original.operationDirectory(),1,original.maxOperationBytes());
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        var rejected=assertThrows(ReplicationException.class,()->helper.new Network(limited,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET,
                f->prepared.set(true),true,false));
        assertEquals("inventory exceeds retained bytes",rejected.getMessage());
        assertFalse(prepared.get());V53BootstrapSeedTest.absent(original);
    }

    @Test void requiredFourBackupHookRejectsEmptyAndWrongSizeBeforeExecution()throws Exception {
        var joining=new V53JoiningIntentExportTest();joining.temp=temp;
        var empty=request(5,false);var small=request(3,true);
        assertThrows(AssertionError.class,()->joining.requiredFourFromVerifiedBackup(empty));
        assertThrows(AssertionError.class,()->joining.requiredFourFromVerifiedBackup(small));
        V53BootstrapSeedTest.absent(empty);V53BootstrapSeedTest.absent(small);
    }
}
