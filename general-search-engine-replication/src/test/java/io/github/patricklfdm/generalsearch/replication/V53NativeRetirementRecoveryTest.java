package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Native automatic-entry recovery, with original bootstrap provenance and floor. */
class V53NativeRetirementRecoveryTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture interrupted(String point)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("store-"+UUID.randomUUID())),
                Files.createDirectory(temp.resolve("raw-"+UUID.randomUUID())),4,false);f.ownedHistory=true;
        for(var t:f.request.targets())try(var owner=f.open(t,"initialize-retention")){owner.initializePeerRetention();owner.initializeFutureRetention();}
        f.campaign(1);
        f.observer=(t,operation,event)->{if(operation.equals("round-2-settled-maintain") && event.equals(point))throw new IOException("original interruption");};
        assertEquals("original interruption",assertThrows(IOException.class,()->f.campaign(2)).getMessage());
        f.observer=(t,operation,event)->{};assertEquals(0,f.resources.usage().leases());return f;
    }
    MembershipGrantJournal reopen(V53BootstrapPublicationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        var t=f.request.targets().getFirst();
        return MembershipGrantJournal.openRetainingFuturePeers(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),
                f.resources,MembershipGrantJournal.MAXIMUM,event->{V53RetirementImagesTest.bounded(f.resources);cut.at(event);});
    }
    static String inactive(Path path)throws Exception {
        var selector=decode(Files.readAllBytes(path.resolve("selector.gsr")),"records","SELECTOR");
        return "generations/"+(selector.value().get("generation").equals("a")?"b":"a")+"/";
    }
    static Map<String,String> protectedBytes(Path path)throws Exception {
        String inactive=inactive(path);var result=new TreeMap<String,String>();
        try(var files=Files.walk(path)) {for(Path p:files.filter(Files::isRegularFile).toList()) {
            String name=path.relativize(p).toString();if(!name.startsWith("retirement/") && !name.startsWith(inactive))result.put(name,hash(Files.readAllBytes(p)));
        }}return result;
    }
    @ParameterizedTest @ValueSource(strings={"RETIREMENT_BORROW_PREFIX_WRITTEN","RETIREMENT_AUTHORITY_FORCED",
            "RETIREMENT_FILE_DELETED","RETIREMENT_AUTHORITY_CLEARED"})
    void automaticEntryCompletesOnlyTheInterruptedRetirement(String point)throws Exception {
        var f=interrupted(point);Path path=f.request.targets().getFirst().replicaDirectory();
        var before=protectedBytes(path);var events=new ArrayList<String>();
        // Explicit component opens still expose pending maintenance for diagnosis.
        try(var owner=f.open(f.request.targets().getFirst(),"component-inspection")) {
            assertTrue(Files.isDirectory(path.resolve("retirement")));
        }
        try(var owner=reopen(f,events::add)) {
            assertFalse(Files.exists(path.resolve("retirement")));assertTrue(owner.retireInactive().isEmpty());
            assertTrue(owner.nativeGenerationMaintenanceRequired(),"original floor remains for normal maintenance");
            assertTrue(owner.governingFloor().isPresent());
        }
        assertEquals(before,protectedBytes(path));assertEquals(0,f.resources.usage().leases());
        assertTrue(events.contains("RETIREMENT_BEFORE_RETURN") || events.contains("RETIREMENT_CLEARED"));
    }
    @Test void interruptedAutomaticRecoveryReleasesOwnerAndResumesTheSameDecision()throws Exception {
        var f=interrupted("RETIREMENT_FILE_DELETED");Path path=f.request.targets().getFirst().replicaDirectory();
        byte[] decision=Files.readAllBytes(path.resolve("retirement/retirement.gsr"));
        assertEquals("second interruption",assertThrows(IOException.class,()->{
            try(var owner=reopen(f,event->{if(event.equals("RETIREMENT_AUTHORITY_RESEALED"))throw new IOException("second interruption");})){}
        }).getMessage());
        assertEquals(0,f.resources.usage().leases());assertArrayEquals(decision,Files.readAllBytes(path.resolve("retirement/retirement.gsr")));
        try(var owner=reopen(f,event->{})){assertFalse(Files.exists(path.resolve("retirement")));assertTrue(owner.governingFloor().isPresent());}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void alteredPartialBindingCannotAuthorizeAutomaticDeletion()throws Exception {
        var f=interrupted("RETIREMENT_BORROW_PREFIX_WRITTEN");Path path=f.request.targets().getFirst().replicaDirectory();
        Path binding=path.resolve("retirement/"+MembershipRetirementImages.FILE);byte[] bytes=Files.readAllBytes(binding);
        bytes[bytes.length-1]^=1;Files.write(binding,bytes);var before=V53ReplayFilesTest.files(path);
        assertThrows(Exception.class,()->{try(var owner=reopen(f,event->{})) {}});
        assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(0,f.resources.usage().leases());
        assertTrue(Files.exists(path.resolve(inactive(path)+"generation.gsr")));
    }
    @Test void requiredRetentionOriginalsAreCheckedBeforeResumingDeletion()throws Exception {
        var f=interrupted("RETIREMENT_BORROW_PREFIX_WRITTEN");Path path=f.request.targets().getFirst().replicaDirectory();
        for(String name:List.of(MembershipPeerRetentionFiles.FILE,MembershipFutureRetentionFiles.FILE)) {
            Path ledger=path.resolve(name);byte[] original=Files.readAllBytes(ledger);Files.delete(ledger);
            var before=V53ReplayFilesTest.files(path);
            assertThrows(Exception.class,()->{try(var owner=reopen(f,event->{})) {}});
            assertEquals(before,V53ReplayFilesTest.files(path));assertEquals(0,f.resources.usage().leases());
            Files.write(ledger,original);
        }
        try(var owner=reopen(f,event->{})){assertFalse(Files.exists(path.resolve("retirement")));}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void completeRetainedFloorContinuesWithoutAnotherReceivingCohort()throws Exception {
        var f=interrupted("RETIREMENT_BORROW_PREFIX_WRITTEN");Path path=f.request.targets().getFirst().replicaDirectory();
        try(var owner=reopen(f,event->{})) {
            assertTrue(owner.governingFloor().isPresent());
            var protectedBefore=protectedBytes(path);long started=System.nanoTime();
            try(var maintenance=MembershipGenerationMaintenance.beforeGrant(owner,f.resources,ReplicationBounds.defaults(),
                    (peer,request,kind,deadline)->{throw new AssertionError("complete retained floor must not reacquire remote copies");},
                    ()->{},Files.createDirectory(temp.resolve("maintenance")),System::nanoTime,started,TimeUnit.SECONDS.toNanos(60))) {
                maintenance.run();
            }
            assertFalse(owner.governingFloor().isPresent());assertFalse(owner.nativeGenerationMaintenanceRequired());
            // Normal source retirement may compact its journal; no current
            // generation or admission bytes may change during maintenance.
            var after=protectedBytes(path);
            for(var entry:protectedBefore.entrySet())if(!entry.getKey().startsWith("floor-copies/") &&
                    !entry.getKey().startsWith("sources/") && !entry.getKey().equals("grants.gsr"))
                assertEquals(entry.getValue(),after.get(entry.getKey()),entry.getKey());
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
